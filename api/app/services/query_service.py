from __future__ import annotations

import uuid
from typing import Any

import google.genai as genai
from openai import OpenAI
from sqlalchemy.orm import Session

from app.services.chroma_service import get_collection
from app.services.embedding_service import embed_texts_with_config
from app.services.provider_settings_service import (
    ProviderSettingsError,
    normalize_provider,
    resolve_chat_provider_config,
    resolve_embedding_provider_config,
)
from app.storage.models import QueryRun


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
) -> dict[str, Any]:
    try:
        answer_provider = normalize_provider(provider)
    except ProviderSettingsError as exc:
        raise QueryError(str(exc)) from exc

    try:
        openai_embedding_config = resolve_embedding_provider_config(db, project_id, "openai")
    except ProviderSettingsError as exc:
        if answer_provider == "gemini":
            raise QueryError(
                "OpenAI API key is still required for retrieval because this project "
                "is indexed with OpenAI embeddings.",
            ) from exc
        raise QueryError(str(exc)) from exc

    try:
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise QueryError(str(exc)) from exc

    try:
        query_embedding = embed_texts_with_config(
            [query],
            api_key=openai_embedding_config["api_key"],
            model=openai_embedding_config["embedding_model"],
            base_url=openai_embedding_config.get("base_url"),
        )[0]
    except Exception as exc:
        raise _provider_query_error(
            provider="openai",
            stage="retrieval",
            exc=exc,
        ) from exc
    collection = get_collection()
    try:
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=_build_where_clause(project_id, filters),
        )
    except Exception as exc:
        raise QueryError(
            "Failed to retrieve context from the vector store.",
            code="QUERY_RETRIEVAL_ERROR",
            status_code=503,
            details={"stage": "retrieval"},
        ) from exc

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    ids = result.get("ids", [[]])[0]
    if not documents:
        answer = "I don't know based on the indexed documents."
        run = _store_query_run(db, project_id, query, top_k, filters, answer)
        return {
            "answer": answer,
            "citations": [],
            "run_id": str(run.id),
            "provider": answer_provider,
            "model": generation_config["chat_model"],
        }

    citations = [
        {
            "citation_id": metadata.get("chunk_id", chunk_id),
            "source_id": metadata.get("source_id"),
            "document_id": metadata.get("document_id"),
            "chunk_id": metadata.get("chunk_id", chunk_id),
            "title": metadata.get("title", ""),
            "url": metadata.get("url", ""),
        }
        for chunk_id, metadata in zip(ids, metadatas, strict=False)
    ]
    answer = _generate_answer(
        query,
        documents,
        metadatas,
        provider=answer_provider,
        api_key=generation_config["api_key"],
        base_url=generation_config.get("base_url"),
        model=generation_config["chat_model"],
    )
    run = _store_query_run(db, project_id, query, top_k, filters, answer)
    return {
        "answer": answer,
        "citations": citations,
        "run_id": str(run.id),
        "provider": answer_provider,
        "model": generation_config["chat_model"],
    }


def _generate_answer(
    query: str,
    documents: list[str],
    metadatas: list[dict[str, Any]],
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str,
) -> str:
    if provider == "gemini":
        return _generate_answer_with_gemini(
            query,
            documents,
            metadatas,
            api_key=api_key,
            model=model,
        )
    return _generate_answer_with_openai(
        query,
        documents,
        metadatas,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )


def _generate_answer_with_openai(
    query: str,
    documents: list[str],
    metadatas: list[dict[str, Any]],
    api_key: str,
    base_url: str | None,
    model: str,
) -> str:
    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    context_blocks: list[str] = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas, strict=False), start=1):
        title = metadata.get("title", f"Source {index}")
        context_blocks.append(f"[{index}] {title}\n{document}")

    prompt = (
        "Answer based only on the context below. "
        "If the answer is not supported, say you don't know.\n\n"
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
) -> str:
    context_blocks: list[str] = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas, strict=False), start=1):
        title = metadata.get("title", f"Source {index}")
        context_blocks.append(f"[{index}] {title}\n{document}")

    prompt = (
        "Answer based only on the context below. "
        "If the answer is not supported, say you don't know.\n\n"
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
