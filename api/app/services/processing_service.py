from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz
import pdfplumber
from sqlalchemy.orm import Session

from app.services.chroma_service import get_retrieval_collection
from app.services.embedding_service import (
    LOCAL_EMBEDDING_MODEL,
    LOCAL_EMBEDDING_PROVIDER,
    chunk_text,
    count_tokens,
    embed_texts_with_local_model,
)
from app.storage.models import Chunk, Document, Source
from app.storage.repositories.processing_run_repository import ProcessingRunRepository


class ProcessingError(Exception):
    pass


@dataclass
class ExtractedSourceContent:
    title: str
    text: str
    source_url: str
    page_texts: list[str] | None = None


def process_sources(
    db: Session,
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    sources: list[Source],
    chunk_size: int,
    chunk_overlap: int,
) -> dict[str, int | str]:
    run_repo = ProcessingRunRepository(db)
    embedding_model = LOCAL_EMBEDDING_MODEL
    run_metadata = {
        "source_ids": [str(source.id) for source in sources],
        "source_count": len(sources),
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
        "provider": LOCAL_EMBEDDING_PROVIDER,
        "embedding_model": embedding_model,
    }
    config_hash = hashlib.sha256(
        json.dumps(
            {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "embedding_model": embedding_model,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    run = run_repo.create(
        project_id=project_id,
        job_id=job_id,
        run_type="processing",
        model_id=embedding_model,
        prompt_hash=None,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata=run_metadata,
    )

    documents_created = 0
    chunks_created = 0

    for source in sources:
        _replace_source_documents(db, source)
        extracted = _extract_source_content(source)
        document = Document(
            source_id=source.id,
            title=extracted.title,
            raw_path=source.storage_path,
            clean_text=extracted.text,
            token_count=count_tokens(extracted.text, model_name=embedding_model),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        documents_created += 1

        chunk_payloads = _build_chunk_payloads(
            source=source,
            document=document,
            text=extracted.text,
            source_url=extracted.source_url,
            page_texts=extracted.page_texts,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model,
        )
        vectors = embed_texts_with_local_model(
            [item["content"] for item in chunk_payloads],
            model_name=embedding_model,
        )
        chunk_models: list[Chunk] = []
        for item in chunk_payloads:
            chunk_models.append(
                Chunk(
                    id=uuid.UUID(item["chunk_id"]),
                    document_id=document.id,
                    chunk_index=item["chunk_index"],
                    content=item["content"],
                    chroma_id=item["chroma_id"],
                    embedding_model=embedding_model,
                    chunk_metadata=item["metadata"],
                )
            )
        collection = get_retrieval_collection(embedding_model)
        collection.add(
            ids=[chunk.chroma_id for chunk in chunk_models if chunk.chroma_id],
            documents=[chunk.content for chunk in chunk_models],
            embeddings=vectors,
            metadatas=[chunk.chunk_metadata for chunk in chunk_models],
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
        get_retrieval_collection(LOCAL_EMBEDDING_MODEL).delete(ids=chroma_ids)

    for chunk in existing_chunks:
        db.delete(chunk)
    for document in existing_documents:
        db.delete(document)
    db.commit()


def _extract_source_content(source: Source) -> ExtractedSourceContent:
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


def _extract_file_content(path: Path) -> ExtractedSourceContent:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        page_texts = _extract_pdf_pages(path)
        text = "\n".join(page.strip() for page in page_texts if page.strip())
        if not text.strip():
            raise ProcessingError(f"No readable text found in '{path.name}'.")
        return ExtractedSourceContent(
            title=path.name,
            text=text.strip(),
            source_url="",
            page_texts=page_texts,
        )
    else:
        text = path.read_text(encoding="utf-8")

    clean_text = text.strip()
    if not clean_text:
        raise ProcessingError(f"No readable text found in '{path.name}'.")

    return ExtractedSourceContent(title=path.name, text=clean_text, source_url="")


def _extract_pdf_pages(path: Path) -> list[str]:
    extracted_pages: list[str] = []

    with fitz.open(path) as document:
        for page in document:
            extracted_pages.append(page.get_text("text"))

    if any(page.strip() for page in extracted_pages):
        return [page.strip() for page in extracted_pages]

    with pdfplumber.open(path) as pdf:
        plumber_pages = [page.extract_text() or "" for page in pdf.pages]
    return [page.strip() for page in plumber_pages]


def _extract_remote_payload(path: Path) -> ExtractedSourceContent:
    payload = json.loads(path.read_text(encoding="utf-8"))
    title = str(payload.get("title") or path.name)
    content = str(payload.get("content") or "").strip()
    source_url = str(payload.get("url") or payload.get("ingested_from") or "")
    if not content:
        raise ProcessingError(f"No readable content found in '{path.name}'.")
    return ExtractedSourceContent(title=title, text=content, source_url=source_url)


def _build_chunk_payloads(
    source: Source,
    document: Document,
    text: str,
    source_url: str,
    page_texts: list[str] | None,
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> list[dict[str, Any]]:
    if page_texts:
        return _build_pdf_chunk_payloads(
            source=source,
            document=document,
            page_texts=page_texts,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            embedding_model=embedding_model,
        )

    chunks = chunk_text(
        text,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        model_name=embedding_model,
    )
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


def _build_pdf_chunk_payloads(
    *,
    source: Source,
    document: Document,
    page_texts: list[str],
    chunk_size: int,
    chunk_overlap: int,
    embedding_model: str,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    chunk_index = 0

    for page_number, page_text in enumerate(page_texts, start=1):
        if not page_text.strip():
            continue
        page_chunks = chunk_text(
            page_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            model_name=embedding_model,
        )
        for chunk in page_chunks:
            chunk_uuid = str(uuid.uuid4())
            payloads.append(
                {
                    "chunk_id": chunk_uuid,
                    "chroma_id": chunk_uuid,
                    "chunk_index": chunk_index,
                    "content": chunk,
                    "metadata": {
                        "project_id": str(source.project_id),
                        "source_id": str(source.id),
                        "document_id": str(document.id),
                        "chunk_id": chunk_uuid,
                        "chunk_index": chunk_index,
                        "source_type": source.type,
                        "title": document.title or "",
                        "url": "",
                        "page_number": page_number,
                    },
                }
            )
            chunk_index += 1

    return payloads
