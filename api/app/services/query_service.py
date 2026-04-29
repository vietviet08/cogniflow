from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

import google.genai as genai
from openai import OpenAI
from sqlalchemy.orm import Session

from app.services.chroma_service import get_retrieval_collection
from app.services.citation_service import hydrate_citations
from app.services.embedding_service import (
    LOCAL_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_PROVIDER,
    embed_texts_with_local_model,
)
from app.services.provider_settings_service import (
    ProviderSettingsError,
    normalize_provider,
    resolve_chat_provider_config,
)
from app.storage.models import Chunk, Document, QueryRun, Source


@dataclass
class EvidenceRecord:
    id: str
    document: str
    metadata: dict[str, Any]
    semantic_rank: int | None = None
    lexical_rank: int | None = None
    lexical_score: float = 0.0
    fused_score: float = 0.0


@dataclass
class RetrievalResult:
    records: list[EvidenceRecord]
    diagnostics: dict[str, Any]


class QueryError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "QUERY_FAILED",
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


def search_knowledge_base(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    provider: str,
    top_k: int,
    filters: dict[str, Any] | None = None,
    conversation_context: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    try:
        answer_provider = normalize_provider(provider)
    except ProviderSettingsError as exc:
        raise QueryError(str(exc)) from exc

    try:
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise QueryError(str(exc)) from exc

    retrieval = retrieve_hybrid_evidence(
        db,
        project_id=project_id,
        query=query,
        top_k=top_k,
        filters=filters,
    )
    documents = [record.document for record in retrieval.records]
    metadatas = [record.metadata for record in retrieval.records]
    ids = [record.id for record in retrieval.records]

    if not retrieval.records:
        answer = "I don't know based on the indexed documents."
        run = _store_query_run(db, project_id, query, top_k, filters, answer)
        return {
            "answer": answer,
            "citations": [],
            "run_id": str(run.id),
            "provider": answer_provider,
            "model": generation_config["chat_model"],
            "retrieval": retrieval.diagnostics,
        }

    citations = hydrate_citations(db, [
        {
            "citation_id": metadata.get("chunk_id", chunk_id),
            "source_id": metadata.get("source_id"),
            "source_type": metadata.get("source_type"),
            "document_id": metadata.get("document_id"),
            "chunk_id": metadata.get("chunk_id", chunk_id),
            "title": metadata.get("title", ""),
            "url": metadata.get("url", ""),
            "page_number": metadata.get("page_number"),
            "quote": document,
        }
        for chunk_id, metadata, document in zip(ids, metadatas, documents, strict=False)
    ])
    answer = _generate_answer(
        query,
        documents,
        metadatas,
        provider=answer_provider,
        api_key=generation_config["api_key"],
        base_url=generation_config.get("base_url"),
        model=generation_config["chat_model"],
        conversation_context=conversation_context,
    )
    run = _store_query_run(db, project_id, query, top_k, filters, answer)
    return {
        "answer": answer,
        "citations": citations,
        "run_id": str(run.id),
        "provider": answer_provider,
        "model": generation_config["chat_model"],
        "retrieval": retrieval.diagnostics,
    }


def retrieve_hybrid_evidence(
    db: Session,
    *,
    project_id: uuid.UUID,
    query: str,
    top_k: int,
    filters: dict[str, Any] | None = None,
) -> RetrievalResult:
    effective_top_k = max(top_k, 1)
    semantic_limit = min(max(effective_top_k * 3, effective_top_k), 50)
    lexical_limit = min(max(effective_top_k * 3, effective_top_k), 50)
    retrieval_error: Exception | None = None
    semantic_records: list[EvidenceRecord] = []

    try:
        query_embedding = embed_texts_with_local_model(
            [query],
            model_name=LOCAL_EMBEDDING_MODEL,
        )[0]
        collection = get_retrieval_collection(LOCAL_EMBEDDING_MODEL)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=semantic_limit,
            where=_build_where_clause(project_id, filters),
        )
        semantic_records = _records_from_vector_result(result)
    except Exception as exc:
        retrieval_error = exc

    if retrieval_error is not None and db is None:
        raise QueryError(
            "Local embedding backend is unavailable during retrieval.",
            code="QUERY_RETRIEVAL_ERROR",
            status_code=503,
            details={
                "provider": LOCAL_EMBEDDING_PROVIDER,
                "stage": "retrieval",
                "model": LOCAL_EMBEDDING_MODEL,
                "reason": _sanitize_exception_reason(retrieval_error)
                or "Local embedding backend failed.",
            },
        ) from retrieval_error

    has_non_local_chunks = False
    if not semantic_records and retrieval_error is None:
        has_non_local_chunks = _project_has_non_local_chunks(db, project_id)
        if has_non_local_chunks:
            raise QueryError(
                "This project must be reprocessed to use the local multilingual embedding backend.",
                code="QUERY_REINDEX_REQUIRED",
                status_code=409,
                details={
                    "provider": LOCAL_EMBEDDING_PROVIDER,
                    "stage": "retrieval",
                    "model": LOCAL_EMBEDDING_MODEL,
                },
            )

    lexical_records = _load_chunk_lexical_records(
        db,
        project_id=project_id,
        query=query,
        limit=lexical_limit,
        filters=filters,
    )
    records = _fuse_evidence_records(
        semantic_records=semantic_records,
        lexical_records=lexical_records,
        top_k=effective_top_k,
    )

    fallback_used = False
    if not records:
        fallback_records = _load_document_fallback_records(
            db,
            project_id=project_id,
            query=query,
            top_k=effective_top_k,
            filters=filters,
        )
        if fallback_records:
            fallback_used = True
            records = fallback_records

    if not records and retrieval_error is not None:
        raise QueryError(
            "Failed to retrieve context from the vector store.",
            code="QUERY_RETRIEVAL_ERROR",
            status_code=503,
            details={
                "provider": LOCAL_EMBEDDING_PROVIDER,
                "stage": "retrieval",
                "model": LOCAL_EMBEDDING_MODEL,
                "reason": _sanitize_exception_reason(retrieval_error)
                or "Vector store unavailable.",
            },
        ) from retrieval_error

    if not records and (has_non_local_chunks or _project_has_non_local_chunks(db, project_id)):
        raise QueryError(
            "This project must be reprocessed to use the local multilingual embedding backend.",
            code="QUERY_REINDEX_REQUIRED",
            status_code=409,
            details={
                "provider": LOCAL_EMBEDDING_PROVIDER,
                "stage": "retrieval",
                "model": LOCAL_EMBEDDING_MODEL,
            },
        )

    diagnostics = {
        "mode": "hybrid",
        "embedding_model": LOCAL_EMBEDDING_MODEL,
        "semantic_candidates": len(semantic_records),
        "lexical_candidates": len(lexical_records),
        "returned": len(records),
        "reranker": "reciprocal_rank_fusion",
        "fallback": "document_keyword" if fallback_used else None,
        "semantic_error": _sanitize_exception_reason(retrieval_error)
        if retrieval_error is not None
        else None,
    }
    return RetrievalResult(records=records, diagnostics=diagnostics)


def _records_from_vector_result(result: dict[str, Any]) -> list[EvidenceRecord]:
    documents = result.get("documents", [[]])[0] or []
    metadatas = result.get("metadatas", [[]])[0] or []
    ids = result.get("ids", [[]])[0] or []
    records: list[EvidenceRecord] = []
    for rank, (chunk_id, metadata, document) in enumerate(
        zip(ids, metadatas, documents, strict=False),
        start=1,
    ):
        if not isinstance(metadata, dict):
            metadata = {}
        records.append(
            EvidenceRecord(
                id=str(chunk_id),
                document=str(document or ""),
                metadata=dict(metadata),
                semantic_rank=rank,
            )
        )
    return records


def _fuse_evidence_records(
    *,
    semantic_records: list[EvidenceRecord],
    lexical_records: list[EvidenceRecord],
    top_k: int,
) -> list[EvidenceRecord]:
    rank_constant = 60
    fused: dict[str, EvidenceRecord] = {}

    def record_key(record: EvidenceRecord) -> str:
        return str(record.metadata.get("chunk_id") or record.id)

    for record in semantic_records:
        key = record_key(record)
        stored = fused.get(key)
        score = 1 / (rank_constant + (record.semantic_rank or len(semantic_records) + 1))
        if stored is None:
            record.fused_score = score
            fused[key] = record
        else:
            stored.semantic_rank = record.semantic_rank
            stored.fused_score += score
            if not stored.document and record.document:
                stored.document = record.document

    for record in lexical_records:
        key = record_key(record)
        stored = fused.get(key)
        score = 1 / (rank_constant + (record.lexical_rank or len(lexical_records) + 1))
        if stored is None:
            record.fused_score = score
            fused[key] = record
        else:
            stored.lexical_rank = record.lexical_rank
            stored.lexical_score = record.lexical_score
            stored.fused_score += score
            if not stored.document and record.document:
                stored.document = record.document
            stored.metadata = {**record.metadata, **stored.metadata}

    return sorted(
        fused.values(),
        key=lambda item: (
            item.fused_score,
            item.lexical_score,
            -(item.semantic_rank or 9999),
        ),
        reverse=True,
    )[:top_k]


def _generate_answer(
    query: str,
    documents: list[str],
    metadatas: list[dict[str, Any]],
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> str:
    if provider == "gemini":
        return _generate_answer_with_gemini(
            query,
            documents,
            metadatas,
            api_key=api_key,
            model=model,
            conversation_context=conversation_context,
        )
    return _generate_answer_with_openai(
        query,
        documents,
        metadatas,
        api_key=api_key,
        base_url=base_url,
        model=model,
        conversation_context=conversation_context,
    )


def _generate_answer_with_openai(
    query: str,
    documents: list[str],
    metadatas: list[dict[str, Any]],
    api_key: str,
    base_url: str | None,
    model: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> str:
    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client_kwargs["max_retries"] = 0
    client = OpenAI(**client_kwargs)
    context_blocks: list[str] = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas, strict=False), start=1):
        title = metadata.get("title", f"Source {index}")
        context_blocks.append(f"[{index}] {title}\n{document}")

    conversation_block = _format_conversation_context(conversation_context)
    prompt = (
        "Answer based only on the context below. "
        "If the answer is not supported, say you don't know. "
        "Use the conversation only to resolve follow-up wording; do not introduce facts from it.\n\n"
        f"{conversation_block}"
        f"Context:\n{'\n\n'.join(context_blocks)}\n\nQuestion:\n{query}"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = response.choices[0].message.content
        if content:
            return content.strip()
    except Exception as exc:
        raise _provider_query_error(
            provider="openai",
            stage="generation",
            exc=exc,
        ) from exc

    raise QueryError("OpenAI returned an empty answer.")


def _generate_answer_with_gemini(
    query: str,
    documents: list[str],
    metadatas: list[dict[str, Any]],
    api_key: str,
    model: str,
    conversation_context: list[dict[str, str]] | None = None,
) -> str:
    context_blocks: list[str] = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas, strict=False), start=1):
        title = metadata.get("title", f"Source {index}")
        context_blocks.append(f"[{index}] {title}\n{document}")

    conversation_block = _format_conversation_context(conversation_context)
    prompt = (
        "Answer based only on the context below. "
        "If the answer is not supported, say you don't know. "
        "Use the conversation only to resolve follow-up wording; do not introduce facts from it.\n\n"
        f"{conversation_block}"
        f"Context:\n{'\n\n'.join(context_blocks)}\n\nQuestion:\n{query}"
    )

    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
    except Exception as exc:
        raise _provider_query_error(
            provider="gemini",
            stage="generation",
            exc=exc,
        ) from exc
    finally:
        client.close()

    content = getattr(response, "text", None)
    if content:
        return content.strip()

    raise QueryError("Gemini returned an empty answer.")


def _store_query_run(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    top_k: int,
    filters: dict[str, Any] | None,
    answer: str,
) -> QueryRun:
    run = QueryRun(
        project_id=project_id,
        query_text=query,
        top_k=top_k,
        filters=filters,
        answer_text=answer,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _format_conversation_context(
    conversation_context: list[dict[str, str]] | None,
) -> str:
    if not conversation_context:
        return ""

    lines: list[str] = []
    for message in conversation_context[-8:]:
        role = str(message.get("role") or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = _compact_prompt_text(str(message.get("content") or ""), limit=600)
        if content:
            lines.append(f"[{role}] {content}")

    if not lines:
        return ""
    return f"Conversation so far:\n{'\n'.join(lines)}\n\n"


def _compact_prompt_text(value: str, *, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


def _build_where_clause(project_id: uuid.UUID, filters: dict[str, Any] | None) -> dict[str, Any]:
    where: dict[str, Any] = {"project_id": str(project_id)}
    if not filters:
        return where

    source_types = filters.get("source_types")
    if isinstance(source_types, list) and source_types:
        where["source_type"] = {"$in": source_types}
    return where


def _provider_query_error(provider: str, stage: str, exc: Exception) -> QueryError:
    details: dict[str, Any] = {
        "provider": provider,
        "stage": stage,
    }
    upstream_status = _extract_upstream_status(exc)
    if upstream_status is not None:
        details["upstream_status"] = upstream_status

    reason = _sanitize_exception_reason(exc)
    if reason:
        details["reason"] = reason

    provider_label = "OpenAI" if provider == "openai" else "Gemini"
    return QueryError(
        f"{provider_label} request failed during {stage}.",
        code="QUERY_UPSTREAM_ERROR",
        status_code=502,
        details=details,
    )


def _project_has_non_local_chunks(db: Session, project_id: uuid.UUID) -> bool:
    return (
        db.query(Chunk)
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .filter(
            Source.project_id == project_id,
            Chunk.embedding_model != LOCAL_EMBEDDING_MODEL,
        )
        .count()
        > 0
    )


def _extract_upstream_status(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status
    return None


def _sanitize_exception_reason(exc: Exception) -> str | None:
    raw = str(exc).strip()
    if not raw:
        return None

    lowered = raw.lower()
    if "<!doctype html" in lowered or "<html" in lowered:
        return "Upstream provider returned an HTML error page."

    compact = " ".join(raw.split())
    if len(compact) > 240:
        compact = f"{compact[:237]}..."
    return compact


def _load_document_fallback_records(
    db: Session,
    *,
    project_id: uuid.UUID,
    query: str,
    top_k: int,
    filters: dict[str, Any] | None = None,
) -> list[EvidenceRecord]:
    rows = (
        db.query(Document, Source)
        .join(Source, Document.source_id == Source.id)
        .filter(Source.project_id == project_id)
        .order_by(Document.created_at.desc())
        .all()
    )
    rows = _filter_source_rows(rows, filters)
    if not rows:
        return []

    terms = _tokenize_query(query)
    ranked: list[tuple[int, Document, Source, str]] = []
    for document, source in rows:
        clean_text = (document.clean_text or "").strip()
        if not clean_text:
            continue
        lowered = clean_text.lower()
        score = sum(1 for term in terms if term in lowered)
        ranked.append((score, document, source, clean_text[:2400]))

    if not ranked:
        return []

    ranked.sort(key=lambda item: (item[0], item[1].created_at), reverse=True)
    filtered = [item for item in ranked if item[0] > 0] or ranked
    selected = filtered[: max(top_k, 1)]

    records: list[EvidenceRecord] = []
    for rank, (_, document, source, content) in enumerate(selected, start=1):
        source_metadata = source.source_metadata if isinstance(source.source_metadata, dict) else {}
        records.append(
            EvidenceRecord(
                id=str(document.id),
                document=content,
                metadata={
                    "project_id": str(project_id),
                    "source_id": str(source.id),
                    "source_type": source.type,
                    "document_id": str(document.id),
                    "chunk_id": f"doc-{document.id}",
                    "chunk_index": 0,
                    "title": document.title or source.original_uri or "Imported source",
                    "url": str(source_metadata.get("external_url") or ""),
                },
                lexical_rank=rank,
                lexical_score=float(selected[rank - 1][0]),
            )
        )
    return records


def _load_chunk_lexical_records(
    db: Session,
    *,
    project_id: uuid.UUID,
    query: str,
    limit: int,
    filters: dict[str, Any] | None = None,
) -> list[EvidenceRecord]:
    rows = (
        db.query(Chunk, Document, Source)
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .filter(Source.project_id == project_id)
        .order_by(Document.created_at.desc(), Chunk.chunk_index.asc())
        .all()
    )
    source_types = _filter_source_types(filters)
    if source_types:
        rows = [row for row in rows if row[2].type in source_types]

    terms = _tokenize_query(query)
    ranked: list[tuple[float, Chunk, Document, Source]] = []
    for chunk, document, source in rows:
        content = (chunk.content or "").strip()
        if not content:
            continue
        haystack = " ".join(
            [
                content,
                document.title or "",
                source.original_uri or "",
                source.type or "",
            ]
        ).lower()
        score = _score_lexical_match(terms, haystack)
        if score > 0:
            ranked.append((score, chunk, document, source))

    ranked.sort(key=lambda item: (item[0], item[2].created_at), reverse=True)
    selected = ranked[: max(limit, 1)]

    records: list[EvidenceRecord] = []
    for rank, (score, chunk, document, source) in enumerate(selected, start=1):
        source_metadata = source.source_metadata if isinstance(source.source_metadata, dict) else {}
        chunk_metadata = chunk.chunk_metadata if isinstance(chunk.chunk_metadata, dict) else {}
        records.append(
            EvidenceRecord(
                id=str(chunk.id),
                document=chunk.content[:2400],
                metadata={
                    "project_id": str(project_id),
                    "source_id": str(chunk_metadata.get("source_id") or source.id),
                    "source_type": str(chunk_metadata.get("source_type") or source.type),
                    "document_id": str(chunk_metadata.get("document_id") or document.id),
                    "chunk_id": str(chunk_metadata.get("chunk_id") or chunk.id),
                    "chunk_index": chunk.chunk_index,
                    "title": str(
                        chunk_metadata.get("title")
                        or document.title
                        or source.original_uri
                        or "Imported source"
                    ),
                    "url": str(chunk_metadata.get("url") or source_metadata.get("external_url") or ""),
                    "page_number": chunk_metadata.get("page_number"),
                },
                lexical_rank=rank,
                lexical_score=score,
            )
        )
    return records


def _score_lexical_match(terms: list[str], haystack: str) -> float:
    if not terms:
        return 0.0
    score = 0.0
    for term in terms:
        occurrences = haystack.count(term)
        if occurrences:
            score += 1.0 + min(occurrences, 5) * 0.2
    phrase = " ".join(terms)
    if len(terms) > 1 and phrase in haystack:
        score += 2.0
    return score


def _filter_source_rows(
    rows: list[tuple[Document, Source]],
    filters: dict[str, Any] | None,
) -> list[tuple[Document, Source]]:
    source_types = _filter_source_types(filters)
    if not source_types:
        return rows
    return [row for row in rows if row[1].type in source_types]


def _filter_source_types(filters: dict[str, Any] | None) -> set[str]:
    if not filters:
        return set()
    source_types = filters.get("source_types")
    if not isinstance(source_types, list):
        return set()
    return {str(source_type) for source_type in source_types if str(source_type).strip()}


def _tokenize_query(query: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", query.lower()) if len(token) > 1]
