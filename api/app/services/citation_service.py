from __future__ import annotations

import re
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
from sqlalchemy.orm import Session

from app.storage.models import Chunk, Document, Source


def hydrate_citations(db: Session, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not citations:
        return []

    chunk_ids = _collect_chunk_ids(citations)
    chunk_map = _load_chunk_records(db, chunk_ids)
    hydrated: list[dict[str, Any]] = []
    chunks_updated = False

    for raw_citation in citations:
        citation = dict(raw_citation)
        chunk_id = _coerce_uuid(
            citation.get("chunk_id") or citation.get("citation_id"),
        )
        record = chunk_map.get(chunk_id) if chunk_id else None
        if not record:
            hydrated.append(_finalize_citation(citation))
            continue

        chunk, document, source = record
        metadata = dict(chunk.chunk_metadata or {})
        raw_quote = citation.get("quote") if isinstance(citation.get("quote"), str) else ""
        page_number = (
            citation.get("page_number")
            or metadata.get("page_number")
            or _infer_page_number(source, chunk.content)
        )
        quote = _build_quote(raw_quote) or metadata.get("quote") or _build_quote(chunk.content)

        chunk_changed = False
        if page_number and metadata.get("page_number") != page_number:
            metadata["page_number"] = page_number
            chunk_changed = True
        if quote and metadata.get("quote") != quote:
            metadata["quote"] = quote
            chunk_changed = True
        if chunk_changed:
            chunk.chunk_metadata = metadata
            chunks_updated = True

        hydrated.append(
            _finalize_citation(
                {
                    "citation_id": citation.get("citation_id") or str(chunk.id),
                    "source_id": citation.get("source_id") or str(source.id),
                    "source_type": citation.get("source_type") or source.type,
                    "document_id": citation.get("document_id") or str(document.id),
                    "chunk_id": citation.get("chunk_id") or str(chunk.id),
                    "title": citation.get("title") or document.title or source.original_uri or "",
                    "url": citation.get("url")
                    or (source.original_uri if source.type in {"url", "arxiv"} else ""),
                    "page_number": page_number,
                    "quote": quote,
                }
            )
        )

    if chunks_updated:
        db.commit()

    return hydrated


def hydrate_report_payload_citations(
    db: Session,
    payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload

    hydrated_payload = dict(payload)
    if isinstance(hydrated_payload.get("citations"), list):
        hydrated_payload["citations"] = hydrate_citations(db, hydrated_payload["citations"])

    if isinstance(hydrated_payload.get("items"), list):
        normalized_items: list[dict[str, Any]] = []
        for item in hydrated_payload["items"]:
            if not isinstance(item, dict):
                continue
            normalized_item = dict(item)
            if isinstance(normalized_item.get("citations"), list):
                normalized_item["citations"] = hydrate_citations(db, normalized_item["citations"])
            normalized_items.append(normalized_item)
        hydrated_payload["items"] = normalized_items

    return hydrated_payload


def _collect_chunk_ids(citations: list[dict[str, Any]]) -> list[uuid.UUID]:
    chunk_ids: list[uuid.UUID] = []
    for citation in citations:
        chunk_id = _coerce_uuid(citation.get("chunk_id") or citation.get("citation_id"))
        if chunk_id:
            chunk_ids.append(chunk_id)
    return list(dict.fromkeys(chunk_ids))


def _load_chunk_records(
    db: Session,
    chunk_ids: list[uuid.UUID],
) -> dict[uuid.UUID, tuple[Chunk, Document, Source]]:
    if not chunk_ids:
        return {}

    rows = (
        db.query(Chunk, Document, Source)
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .filter(Chunk.id.in_(chunk_ids))
        .all()
    )
    return {chunk.id: (chunk, document, source) for chunk, document, source in rows}


def _infer_page_number(source: Source, chunk_content: str) -> int | None:
    if source.type != "file" or not source.storage_path:
        return None

    path = Path(source.storage_path)
    if path.suffix.lower() != ".pdf" or not path.exists():
        return None

    normalized_pages = [_normalize_text(page) for page in _load_pdf_pages(str(path))]
    normalized_chunk = _normalize_text(chunk_content)
    if not normalized_chunk:
        return None

    for page_number, page_text in enumerate(normalized_pages, start=1):
        if normalized_chunk in page_text:
            return page_number

    for candidate in _candidate_chunk_windows(chunk_content):
        normalized_candidate = _normalize_text(candidate)
        if not normalized_candidate:
            continue
        for page_number, page_text in enumerate(normalized_pages, start=1):
            if normalized_candidate in page_text:
                return page_number

    return None


@lru_cache(maxsize=64)
def _load_pdf_pages(path: str) -> tuple[str, ...]:
    extracted_pages: list[str] = []

    with fitz.open(path) as document:
        for page in document:
            extracted_pages.append(page.get_text("text"))

    if any(page.strip() for page in extracted_pages):
        return tuple(page.strip() for page in extracted_pages)

    with pdfplumber.open(path) as pdf:
        plumber_pages = [page.extract_text() or "" for page in pdf.pages]
    return tuple(page.strip() for page in plumber_pages)


def _candidate_chunk_windows(chunk_content: str) -> list[str]:
    cleaned = " ".join(chunk_content.split())
    if len(cleaned) <= 260:
        return [cleaned]

    midpoint = len(cleaned) // 2
    return [
        cleaned[:260],
        cleaned[max(0, midpoint - 130) : midpoint + 130],
        cleaned[-260:],
    ]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _build_quote(text: str, *, max_length: int = 280) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_length:
        return cleaned
    return cleaned[: max_length - 1].rstrip() + "…"


def _coerce_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


def _finalize_citation(citation: dict[str, Any]) -> dict[str, Any]:
    return {
        "citation_id": citation.get("citation_id") or citation.get("chunk_id") or "",
        "source_id": citation.get("source_id") or "",
        "source_type": citation.get("source_type"),
        "document_id": citation.get("document_id") or "",
        "chunk_id": citation.get("chunk_id") or citation.get("citation_id") or "",
        "title": citation.get("title") or "",
        "url": citation.get("url") or "",
        "page_number": citation.get("page_number"),
        "quote": _build_quote(citation.get("quote") or ""),
    }
