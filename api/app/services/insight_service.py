"""Insight service: synthesise multi-document evidence into structured findings."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import google.genai as genai
from openai import OpenAI
from sqlalchemy.orm import Session

from app.services.citation_service import hydrate_citations
from app.services.embedding_service import LOCAL_EMBEDDING_MODEL
from app.services.provider_settings_service import (
    ProviderSettingsError,
    normalize_provider,
    resolve_chat_provider_config,
)
from app.services.query_service import QueryError, retrieve_hybrid_evidence
from app.storage.repositories.insight_repository import InsightRepository
from app.storage.repositories.processing_run_repository import ProcessingRunRepository


class InsightError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "INSIGHT_FAILED",
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYNTHESIS_PROMPT_TEMPLATE = """\
You are a research analyst. Based ONLY on the evidence below, produce a structured analysis.

Return a JSON object with EXACTLY this shape:
{{
  "summary": "<2-3 sentence overall summary>",
  "findings": [
    {{
      "theme": "<theme title>",
      "points": ["<finding 1>", "<finding 2>", ...]
    }}
  ]
}}

Rules:
- Use only information from the evidence. Do not add outside knowledge.
- Produce 2-5 themes. Each theme should have 2-4 bullet points.
- If the evidence is insufficient, set summary to "Insufficient evidence" and findings to [].

Research question: {query}

Evidence:
{context}
"""


def generate_insight(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    provider: str,
    max_sources: int = 20,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Generate a structured insight from evidence retrieved from the knowledge base."""
    try:
        answer_provider = normalize_provider(provider)
    except ProviderSettingsError as exc:
        raise InsightError(str(exc)) from exc

    try:
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise InsightError(str(exc)) from exc

    try:
        retrieval = retrieve_hybrid_evidence(
            db,
            project_id=project_id,
            query=query,
            top_k=min(max_sources, 20),
        )
    except QueryError as exc:
        raise InsightError(
            exc.message,
            code="INSIGHT_RETRIEVAL_ERROR",
            status_code=exc.status_code,
            details=exc.details,
        ) from exc
    except Exception as exc:
        raise InsightError(
            "Failed to retrieve evidence for insight generation.",
            code="INSIGHT_RETRIEVAL_ERROR",
            status_code=503,
            details={"stage": "retrieval", "reason": str(exc)[:240]},
        ) from exc

    documents = [record.document for record in retrieval.records]
    metadatas = [record.metadata for record in retrieval.records]
    ids = [record.id for record in retrieval.records]

    if not retrieval.records:
        return _persist_insight(
            db,
            project_id=project_id,
            query=query,
            summary="No indexed documents found for this project.",
            findings=[],
            citations=[],
            provider=answer_provider,
            model_id=generation_config["chat_model"],
            prompt_template=_SYNTHESIS_PROMPT_TEMPLATE,
            max_sources=max_sources,
            parent_run_id=parent_run_id,
            retrieval_diagnostics=retrieval.diagnostics,
        )

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

    context_blocks: list[str] = []
    for index, (document, metadata) in enumerate(zip(documents, metadatas, strict=False), start=1):
        title = metadata.get("title", f"Source {index}")
        context_blocks.append(f"[{index}] {title}\n{document}")
    context = "\n\n".join(context_blocks)

    prompt = _SYNTHESIS_PROMPT_TEMPLATE.format(query=query, context=context)

    # --- Generate structured findings ---
    raw = _call_llm(
        prompt=prompt,
        provider=answer_provider,
        api_key=generation_config["api_key"],
        base_url=generation_config.get("base_url"),
        model=generation_config["chat_model"],
    )
    parsed = _parse_synthesis_response(raw)

    return _persist_insight(
        db,
        project_id=project_id,
        query=query,
        summary=parsed.get("summary", ""),
        findings=parsed.get("findings", []),
        citations=citations,
        provider=answer_provider,
        model_id=generation_config["chat_model"],
        prompt_template=_SYNTHESIS_PROMPT_TEMPLATE,
        max_sources=max_sources,
        parent_run_id=parent_run_id,
        retrieval_diagnostics=retrieval.diagnostics,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _call_llm(
    prompt: str,
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str,
) -> str:
    if provider == "gemini":
        return _call_gemini(prompt, api_key=api_key, model=model)
    return _call_openai(prompt, api_key=api_key, base_url=base_url, model=model)


def _call_openai(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
    kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return content.strip() if content else "{}"
    except Exception as exc:
        raise InsightError(
            "OpenAI request failed during insight generation.",
            code="INSIGHT_UPSTREAM_ERROR",
            status_code=502,
            details={"provider": "openai", "reason": str(exc)[:240]},
        ) from exc


def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        content = getattr(response, "text", None)
        return content.strip() if content else "{}"
    except Exception as exc:
        raise InsightError(
            "Gemini request failed during insight generation.",
            code="INSIGHT_UPSTREAM_ERROR",
            status_code=502,
            details={"provider": "gemini", "reason": str(exc)[:240]},
        ) from exc
    finally:
        client.close()


def _parse_synthesis_response(raw: str) -> dict[str, Any]:
    """Parse LLM JSON response; fall back gracefully on malformed output."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except ValueError:
        pass
    return {"summary": raw[:500], "findings": []}


def _persist_insight(
    db: Session,
    *,
    project_id: uuid.UUID,
    query: str,
    summary: str,
    findings: list,
    citations: list[dict],
    provider: str,
    model_id: str,
    prompt_template: str,
    max_sources: int,
    parent_run_id: uuid.UUID | None = None,
    retrieval_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt_hash = hashlib.sha256(prompt_template.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{provider}:{model_id}".encode()).hexdigest()[:16]

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="insight",
        model_id=model_id,
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config={
            "embedding_model": LOCAL_EMBEDDING_MODEL,
            **(retrieval_diagnostics or {}),
        },
        run_metadata={
            "query": query,
            "provider": provider,
            "max_sources": max_sources,
            "sources_used": len(citations),
        },
        parent_run_id=parent_run_id,
    )

    repo = InsightRepository(db)
    insight = repo.create(
        project_id=project_id,
        query=query,
        summary=summary,
        findings=findings,
        provider=provider,
        model_id=model_id,
        run_id=run.id,
    )
    if citations:
        repo.add_citations(insight, citations)

    return {
        "insight_id": str(insight.id),
        "query": query,
        "summary": summary,
        "findings": findings,
        "citations": citations,
        "run_id": str(run.id),
        "provider": provider,
        "model": model_id,
        "retrieval": retrieval_diagnostics or {},
    }
