from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.chroma_service import get_collection
from app.services.embedding_service import chunk_text, count_tokens, embed_texts
from app.storage.models import Chunk, Document, Source


class ProcessingError(Exception):
    pass


def process_sources(
    db: Session,
    sources: list[Source],
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, int]:
    documents_created = 0
    chunks_created = 0

    for source in sources:
        title, text, source_url = _extract_source_content(source)
        document = Document(
            source_id=source.id,
            title=title,
            raw_path=source.storage_path,
            clean_text=text,
            token_count=count_tokens(text),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        documents_created += 1

        chunk_payloads = _build_chunk_payloads(
            source=source,
            document=document,
            text=text,
            source_url=source_url,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        vectors = embed_texts([item["content"] for item in chunk_payloads])
        collection = get_collection()

        collection.add(
            ids=[item["chroma_id"] for item in chunk_payloads],
            documents=[item["content"] for item in chunk_payloads],
            embeddings=vectors,
            metadatas=[item["metadata"] for item in chunk_payloads],
        )

        for item in chunk_payloads:
            db.add(
                Chunk(
                    document_id=document.id,
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                    chroma_id=item["chroma_id"],
                    embedding_model=get_settings().embedding_model,
                    metadata=item["metadata"],
                )
            )
            chunks_created += 1

        db.commit()

    return {"documents_created": documents_created, "chunks_created": chunks_created}


def _extract_source_content(source: Source) -> tuple[str, str, str]:
    if not source.storage_path:
        raise ProcessingError(f"Source '{source.id}' does not have a stored artifact.")

    storage_path = Path(source.storage_path)
    if not storage_path.exists():
        raise ProcessingError(f"Stored artifact '{storage_path}' does not exist.")

    if source.type == "file":
        return _extract_file_content(storage_path)
    if source.type in {"url", "arxiv"}:
        return _extract_remote_payload(storage_path)
    raise ProcessingError(f"Unsupported source type '{source.type}'.")


def _extract_file_content(path: Path) -> tuple[str, str, str]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _extract_pdf_text(path)
    else:
        text = path.read_text(encoding="utf-8")

    clean_text = text.strip()
    if not clean_text:
        raise ProcessingError(f"No readable text found in '{path.name}'.")

    return path.name, clean_text, ""


def _extract_pdf_text(path: Path) -> str:
    extracted_pages: list[str] = []

    with fitz.open(path) as document:
        for page in document:
            extracted_pages.append(page.get_text("text"))

    text = "\n".join(page.strip() for page in extracted_pages if page.strip())
    if text.strip():
        return text

    with pdfplumber.open(path) as pdf:
        plumber_pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(page.strip() for page in plumber_pages if page.strip())


def _extract_remote_payload(path: Path) -> tuple[str, str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    title = str(payload.get("title") or path.name)
    content = str(payload.get("content") or "").strip()
    source_url = str(payload.get("url") or payload.get("ingested_from") or "")
    if not content:
        raise ProcessingError(f"No readable content found in '{path.name}'.")
    return title, content, source_url


def _build_chunk_payloads(
    source: Source,
    document: Document,
    text: str,
    source_url: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[dict[str, Any]]:
    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    payloads: list[dict[str, Any]] = []

    for index, chunk in enumerate(chunks):
        chunk_id = f"{document.id}:{index}"
        payloads.append(
            {
                "chroma_id": chunk_id,
                "chunk_index": index,
                "content": chunk,
                "metadata": {
                    "project_id": str(source.project_id),
                    "source_id": str(source.id),
                    "document_id": str(document.id),
                    "chunk_index": index,
                    "source_type": source.type,
                    "title": document.title or "",
                    "url": source_url,
                },
            }
        )

    return payloads
