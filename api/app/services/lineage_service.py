from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.storage.models import (
    Chunk,
    Document,
    Insight,
    InsightCitation,
    ProcessingRun,
    Report,
    ReportInsight,
    Source,
)


def get_report_lineage(db: Session, report_id: uuid.UUID) -> dict[str, Any]:
    report = db.get(Report, report_id)
    links = db.query(ReportInsight).filter(ReportInsight.report_id == report_id).all()
    insight_ids = [link.insight_id for link in links]
    insights = _load_insights(db, insight_ids)
    citations = _load_citations_for_insights(db, insight_ids)
    return _build_lineage_payload(
        db,
        report=report,
        insights=insights,
        citations=citations,
        root_report_id=report_id,
    )


def get_insight_lineage(db: Session, insight_id: uuid.UUID) -> dict[str, Any]:
    insight = db.get(Insight, insight_id)
    insights = [insight] if insight is not None else []
    citations = _load_citations_for_insights(db, [insight_id])
    return _build_lineage_payload(
        db,
        report=None,
        insights=insights,
        citations=citations,
        root_insight_id=insight_id,
    )


def _build_lineage_payload(
    db: Session,
    *,
    report: Report | None,
    insights: list[Insight],
    citations: list[InsightCitation],
    root_report_id: uuid.UUID | None = None,
    root_insight_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    source_ids = _parse_uuid_list(citation.source_id for citation in citations)
    document_ids = _parse_uuid_list(citation.document_id for citation in citations)
    chunk_ids = _parse_uuid_list(citation.chunk_id for citation in citations)

    sources = _load_sources(db, source_ids)
    documents = _load_documents(db, document_ids)
    chunks = _load_chunks(db, chunk_ids)
    runs = _load_runs(
        db,
        [
            *(insight.run_id for insight in insights if insight.run_id),
            *([report.run_id] if report and report.run_id else []),
        ],
    )

    citation_items = [
        _serialize_citation(citation, chunks_by_id=chunks, documents_by_id=documents)
        for citation in citations
    ]
    source_items = _serialize_sources(
        sources=sources,
        documents=documents,
        chunks=chunks,
        citations=citation_items,
    )

    return {
        "report_id": str(root_report_id) if root_report_id else None,
        "insight_id": str(root_insight_id) if root_insight_id else None,
        "insight_ids": [str(insight.id) for insight in insights],
        "source_ids": [str(source_id) for source_id in source_ids],
        "run_id": str(report.run_id) if report and report.run_id else None,
        "report": _serialize_report_node(report),
        "insights": [_serialize_insight(insight) for insight in insights],
        "runs": [_serialize_run(run) for run in runs],
        "sources": source_items,
        "citations": citation_items,
        "summary": {
            "insight_count": len(insights),
            "source_count": len(source_items),
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "citation_count": len(citation_items),
            "run_count": len(runs),
        },
    }


def _load_insights(db: Session, insight_ids: list[uuid.UUID]) -> list[Insight]:
    if not insight_ids:
        return []
    return (
        db.query(Insight)
        .filter(Insight.id.in_(insight_ids))
        .order_by(Insight.created_at.asc())
        .all()
    )


def _load_citations_for_insights(
    db: Session,
    insight_ids: list[uuid.UUID],
) -> list[InsightCitation]:
    if not insight_ids:
        return []
    return (
        db.query(InsightCitation)
        .filter(InsightCitation.insight_id.in_(insight_ids))
        .order_by(InsightCitation.created_at.asc())
        .all()
    )


def _load_sources(db: Session, source_ids: list[uuid.UUID]) -> dict[uuid.UUID, Source]:
    if not source_ids:
        return {}
    rows = db.query(Source).filter(Source.id.in_(source_ids)).all()
    return {row.id: row for row in rows}


def _load_documents(db: Session, document_ids: list[uuid.UUID]) -> dict[uuid.UUID, Document]:
    if not document_ids:
        return {}
    rows = db.query(Document).filter(Document.id.in_(document_ids)).all()
    return {row.id: row for row in rows}


def _load_chunks(db: Session, chunk_ids: list[uuid.UUID]) -> dict[uuid.UUID, Chunk]:
    if not chunk_ids:
        return {}
    rows = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    return {row.id: row for row in rows}


def _load_runs(db: Session, run_ids: list[uuid.UUID]) -> list[ProcessingRun]:
    unique_run_ids = list(dict.fromkeys(run_ids))
    if not unique_run_ids:
        return []
    return (
        db.query(ProcessingRun)
        .filter(ProcessingRun.id.in_(unique_run_ids))
        .order_by(ProcessingRun.created_at.asc())
        .all()
    )


def _serialize_sources(
    *,
    sources: dict[uuid.UUID, Source],
    documents: dict[uuid.UUID, Document],
    chunks: dict[uuid.UUID, Chunk],
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    documents_by_source: dict[str, list[Document]] = defaultdict(list)
    chunks_by_document: dict[str, list[Chunk]] = defaultdict(list)
    citation_count_by_chunk: dict[str, int] = defaultdict(int)

    for document in documents.values():
        documents_by_source[str(document.source_id)].append(document)
    for chunk in chunks.values():
        chunks_by_document[str(chunk.document_id)].append(chunk)
    for citation in citations:
        chunk_id = citation.get("chunk_id")
        if chunk_id:
            citation_count_by_chunk[str(chunk_id)] += 1

    items: list[dict[str, Any]] = []
    for source in sorted(sources.values(), key=lambda item: item.created_at):
        source_metadata = source.source_metadata if isinstance(source.source_metadata, dict) else {}
        source_documents = sorted(
            documents_by_source.get(str(source.id), []),
            key=lambda item: item.created_at,
        )
        items.append(
            {
                "source_id": str(source.id),
                "type": source.type,
                "title": source.original_uri or source_metadata.get("title") or "Imported source",
                "original_uri": source.original_uri,
                "status": source.status,
                "provider": source_metadata.get("provider"),
                "external_url": source_metadata.get("external_url"),
                "created_at": source.created_at.isoformat() if source.created_at else None,
                "documents": [
                    {
                        "document_id": str(document.id),
                        "title": document.title or source.original_uri or "Untitled document",
                        "token_count": document.token_count,
                        "created_at": document.created_at.isoformat()
                        if document.created_at
                        else None,
                        "chunks": [
                            {
                                "chunk_id": str(chunk.id),
                                "chunk_index": chunk.chunk_index,
                                "embedding_model": chunk.embedding_model,
                                "preview": _preview(chunk.content),
                                "citation_count": citation_count_by_chunk.get(str(chunk.id), 0),
                            }
                            for chunk in sorted(
                                chunks_by_document.get(str(document.id), []),
                                key=lambda item: item.chunk_index,
                            )
                        ],
                    }
                    for document in source_documents
                ],
            }
        )
    return items


def _serialize_citation(
    citation: InsightCitation,
    *,
    chunks_by_id: dict[uuid.UUID, Chunk],
    documents_by_id: dict[uuid.UUID, Document],
) -> dict[str, Any]:
    chunk = chunks_by_id.get(_parse_uuid(citation.chunk_id or ""))
    document = documents_by_id.get(_parse_uuid(citation.document_id or ""))
    return {
        "citation_id": str(citation.id),
        "insight_id": str(citation.insight_id),
        "source_id": citation.source_id,
        "source_type": citation.source_type,
        "document_id": citation.document_id,
        "chunk_id": citation.chunk_id,
        "title": citation.title or (document.title if document else None),
        "url": citation.url,
        "page_number": citation.page_number,
        "quote": _preview(chunk.content) if chunk else None,
    }


def _serialize_insight(insight: Insight) -> dict[str, Any]:
    return {
        "insight_id": str(insight.id),
        "query": insight.query,
        "summary": insight.summary,
        "provider": insight.provider,
        "model": insight.model_id,
        "status": insight.status,
        "run_id": str(insight.run_id) if insight.run_id else None,
        "created_at": insight.created_at.isoformat() if insight.created_at else None,
    }


def _serialize_report_node(report: Report | None) -> dict[str, Any] | None:
    if report is None:
        return None
    return {
        "report_id": str(report.id),
        "query": report.query,
        "title": report.title,
        "type": report.report_type,
        "status": report.status,
        "run_id": str(report.run_id) if report.run_id else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def _serialize_run(run: ProcessingRun) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "run_type": run.run_type,
        "model_id": run.model_id,
        "prompt_hash": run.prompt_hash,
        "config_hash": run.config_hash,
        "retrieval_config": run.retrieval_config or {},
        "metadata": run.run_metadata or {},
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _parse_uuid_list(values: Any) -> list[uuid.UUID]:
    parsed: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    for value in values:
        parsed_value = _parse_uuid(str(value or ""))
        if parsed_value is not None and parsed_value not in seen:
            parsed.append(parsed_value)
            seen.add(parsed_value)
    return parsed


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (TypeError, ValueError):
        return None


def _preview(value: str | None, *, limit: int = 320) -> str:
    clean = " ".join((value or "").split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 3]}..."
