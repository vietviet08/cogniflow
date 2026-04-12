from __future__ import annotations

import uuid
from typing import Any, Callable

from app.services.insight_service import InsightError, generate_insight
from app.services.processing_service import ProcessingError, process_sources
from app.services.report_service import ReportError, generate_report
from app.storage.db import SessionLocal
from app.storage.models import Job, Source
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.source_repository import SourceRepository

WorkerHandler = Callable[[Job], dict[str, Any]]


def register_worker_tasks() -> dict[str, WorkerHandler]:
    return {
        "processing": _run_processing_job,
        "insight_generation": _run_insight_job,
        "report_generation": _run_report_job,
    }


def run_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job_repo = JobRepository(db)
        job = job_repo.get(uuid.UUID(job_id))
        if job is None:
            return
        if job.status == "cancelled":
            return

        job = job_repo.mark_running(job)
        if job.cancel_requested_at is not None:
            job_repo.request_cancellation(job)
            return

        handler = register_worker_tasks().get(job.job_type)
        if handler is None:
            job_repo.mark_failed(
                job,
                code="JOB_HANDLER_MISSING",
                message=f"No worker handler registered for job type '{job.job_type}'.",
            )
            return

        result_payload = handler(job)
        job_repo.mark_completed(job, result_payload=result_payload)
    except (ProcessingError, InsightError, ReportError, ValueError) as exc:
        if "job_repo" in locals() and "job" in locals():
            job_repo.mark_failed(job, code=type(exc).__name__.upper(), message=str(exc))
    except Exception as exc:
        if "job_repo" in locals() and "job" in locals():
            job_repo.mark_failed(
                job,
                code="JOB_EXECUTION_ERROR",
                message=str(exc),
            )
    finally:
        db.close()


def _run_processing_job(job: Job) -> dict[str, Any]:
    db = SessionLocal()
    try:
        payload = job.job_payload or {}
        project_id = uuid.UUID(payload["project_id"])
        source_ids = [uuid.UUID(source_id) for source_id in payload["source_ids"]]
        chunk_size = int(payload.get("chunk_size", 800))
        chunk_overlap = int(payload.get("chunk_overlap", 120))

        source_repo = SourceRepository(db)
        sources = source_repo.list_by_ids(project_id, source_ids)
        if len(sources) != len(source_ids):
            raise ProcessingError("One or more source IDs do not exist in the project.")

        _update_sources_status(db, sources, status="processing")
        result = process_sources(
            db=db,
            project_id=project_id,
            job_id=job.id,
            sources=sources,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        _update_sources_status(db, sources, status="completed")
        return result
    except Exception:
        failed_sources = SourceRepository(db).list_by_ids(
            uuid.UUID((job.job_payload or {})["project_id"]),
            [uuid.UUID(source_id) for source_id in (job.job_payload or {}).get("source_ids", [])],
        )
        if failed_sources:
            _update_sources_status(db, failed_sources, status="failed")
        raise
    finally:
        db.close()


def _run_insight_job(job: Job) -> dict[str, Any]:
    db = SessionLocal()
    try:
        payload = job.job_payload or {}
        return generate_insight(
            db=db,
            project_id=uuid.UUID(payload["project_id"]),
            query=str(payload["query"]),
            provider=str(payload.get("provider", "openai")),
            max_sources=int(payload.get("max_sources", 20)),
        )
    finally:
        db.close()


def _run_report_job(job: Job) -> dict[str, Any]:
    db = SessionLocal()
    try:
        payload = job.job_payload or {}
        return generate_report(
            db=db,
            project_id=uuid.UUID(payload["project_id"]),
            query=str(payload["query"]),
            report_type=str(payload.get("type", "research_brief")),
            format=str(payload.get("format", "markdown")),
            provider=str(payload.get("provider", "openai")),
        )
    finally:
        db.close()


def _update_sources_status(db, sources: list[Source], *, status: str) -> None:
    for source in sources:
        source.status = status
        db.add(source)
    db.commit()
