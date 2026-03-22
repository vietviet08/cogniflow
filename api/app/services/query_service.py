from __future__ import annotations

import uuid
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.chroma_service import get_collection
from app.services.embedding_service import embed_texts
from app.storage.models import QueryRun


class QueryError(Exception):
    pass


def search_knowledge_base(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    top_k: int,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise QueryError("OPENAI_API_KEY is required to search the knowledge base.")

    query_embedding = embed_texts([query])[0]
    collection = get_collection()
    result = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=_build_where_clause(project_id, filters),
    )

    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    ids = result.get("ids", [[]])[0]
    if not documents:
        answer = "I don't know based on the indexed documents."
        run = _store_query_run(db, project_id, query, top_k, filters, answer)
        return {"answer": answer, "citations": [], "run_id": str(run.id)}

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
    answer = _generate_answer(query, documents, metadatas)
    run = _store_query_run(db, project_id, query, top_k, filters, answer)
    return {"answer": answer, "citations": citations, "run_id": str(run.id)}


def _generate_answer(query: str, documents: list[str], metadatas: list[dict[str, Any]]) -> str:
    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)
    context_blocks: list[str] = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas, strict=False), start=1):
        title = metadata.get("title", f"Source {index}")
        context_blocks.append(f"[{index}] {title}\n{document}")

    prompt = (
        "Answer based only on the context below. "
        "If the answer is not supported, say you don't know.\n\n"
        f"Context:\n{'\n\n'.join(context_blocks)}\n\nQuestion:\n{query}"
    )

    for model in (settings.chat_model, settings.fallback_chat_model):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = response.choices[0].message.content
            if content:
                return content.strip()
        except Exception:
            continue

    raise QueryError("Failed to generate an answer from the retrieved context.")


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
