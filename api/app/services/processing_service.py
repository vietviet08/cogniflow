from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.chroma_service import get_collection
from app.services.embedding_service import chunk_text, count_tokens, embed_texts
from app.storage.models import Chunk, Document, Source
from app.storage.repositories.processing_run_repository import ProcessingRunRepository


class ProcessingError(Exception):
    pass


def process_sources(
    db: Session,
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    sources: list[Source],
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, int | str]:
    settings = get_settings()
    run_repo = ProcessingRunRepository(db)
    run_metadata = {
        "source_ids": [str(source.id) for source in sources],
        "source_count": len(sources),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }
    config_hash = hashlib.sha256(
        json.dumps(
            {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "embedding_model": settings.embedding_model,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    run = run_repo.create(
        project_id=project_id,
        job_id=job_id,
        run_type="processing",
        model_id=settings.embedding_model,
        prompt_hash=None,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata=run_metadata,
    )

    documents_created = 0
    chunks_created = 0

    for source in sources:
        _replace_source_documents(db, source)
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
        chunk_models: list[Chunk] = []
        for item in chunk_payloads:
            chunk_models.append(
                Chunk(
                    id=uuid.UUID(item["chunk_id"]),
                    document_id=document.id,
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                    chroma_id=item["chroma_id"],
                    embedding_model=get_settings().embedding_model,
                    metadata=item["metadata"],
                )
            )
        collection = get_collection()
        collection.add(
            ids=[chunk.chroma_id for chunk in chunk_models if chunk.chroma_id],
            documents=[chunk.content for chunk in chunk_models],
            embeddings=vectors,
            metadatas=[chunk.metadata for chunk in chunk_models],
        )

        for chunk in chunk_models:
            db.add(chunk)
            chunks_created += 1

        db.commit()

    run = run_repo.update_metadata(
        run,
        {
            **run_metadata,
            "documents_created": documents_created,
            "chunks_created": chunks_created,
        },
    )

    return {
        "run_id": str(run.id),
        "documents_created": documents_created,
        "chunks_created": chunks_created,
    }


def _replace_source_documents(db: Session, source: Source) -> None:
    existing_documents = db.query(Document).filter(Document.source_id == source.id).all()
    if not existing_documents:
        return

    document_ids = [document.id for document in existing_documents]
    existing_chunks = db.query(Chunk).filter(Chunk.document_id.in_(document_ids)).all()
    chroma_ids = [chunk.chroma_id for chunk in existing_chunks if chunk.chroma_id]
    if chroma_ids:
        get_collection().delete(ids=chroma_ids)

    for chunk in existing_chunks:
        db.delete(chunk)
    for document in existing_documents:
        db.delete(document)
    db.commit()


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
        chunk_uuid = str(uuid.uuid4())
        payloads.append(
            {
                "chunk_id": chunk_uuid,
                "chroma_id": chunk_uuid,
                "chunk_index": index,
                "content": chunk,
                "metadata": {
                    "project_id": str(source.project_id),
                    "source_id": str(source.id),
                    "document_id": str(document.id),
                    "chunk_id": chunk_uuid,
                    "chunk_index": index,
                    "source_type": source.type,
                    "title": document.title or "",
                    "url": source_url,
                },
            }
        )

    return payloads
