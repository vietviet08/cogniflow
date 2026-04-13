from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable

from app.core.logging import bind_request_id, clear_request_id
from app.observability.telemetry import emit_event, record_job_run
from app.services.intelligence_service import IntelligenceError, scan_project_sources
from app.services.insight_service import InsightError, generate_insight
from app.services.processing_service import ProcessingError, process_sources
from app.services.report_service import ReportError, generate_report
from app.storage.db import SessionLocal
from app.storage.models import Job, Source
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.source_repository import SourceRepository

WorkerHandler = Callable[[Job], dict[str, Any]]
logger = logging.getLogger("app.worker")


def register_worker_tasks() -> dict[str, WorkerHandler]:
    return {
        "processing": _run_processing_job,
        "insight_generation": _run_insight_job,
        "report_generation": _run_report_job,
        "intelligence_monitoring": _run_intelligence_monitoring_job,
    }


def run_job(job_id: str) -> None:
    db = SessionLocal()
    token = None
    started_at = time.perf_counter()
    try:
        job_repo = JobRepository(db)
        job = job_repo.get(uuid.UUID(job_id))
        if job is None:
            return
        if job.status != "queued":
            return
        request_id = str((job.job_payload or {}).get("request_id") or f"job:{job.id}")
        token = bind_request_id(request_id)

        job = job_repo.mark_running(job)
        emit_event(
            "job_started",
            {"job_id": str(job.id), "job_type": job.job_type, "queue_name": job.queue_name},
        )
        logger.info(
            "job_started",
            extra={
                "job_id": str(job.id),
                "job_type": job.job_type,
                "queue_name": job.queue_name,
            },
        )
        if job.cancel_requested_at is not None:
            job_repo.mark_cancelled(job)
            duration_ms = (time.perf_counter() - started_at) * 1000
            record_job_run(job_type=job.job_type, status="cancelled", duration_ms=duration_ms)
            emit_event(
                "job_cancelled",
                {
                    "job_id": str(job.id),
                    "job_type": job.job_type,
                    "duration_ms": round(duration_ms, 3),
                },
            )
            return

        handler = register_worker_tasks().get(job.job_type)
        if handler is None:
            _handle_retryable_failure(
                job_repo,
                job,
                code="JOB_HANDLER_MISSING",
                message=f"No worker handler registered for job type '{job.job_type}'.",
                started_at=started_at,
            )
            return

        result_payload = handler(job)
        job_repo.mark_completed(job, result_payload=result_payload)
        duration_ms = (time.perf_counter() - started_at) * 1000
        record_job_run(job_type=job.job_type, status="completed", duration_ms=duration_ms)
        emit_event(
            "job_completed",
            {
                "job_id": str(job.id),
                "job_type": job.job_type,
                "duration_ms": round(duration_ms, 3),
            },
        )
    except (ProcessingError, InsightError, ReportError, IntelligenceError, ValueError) as exc:
        if "job_repo" in locals() and "job" in locals():
            _handle_retryable_failure(
                job_repo,
                job,
                code=type(exc).__name__.upper(),
                message=str(exc),
                started_at=started_at,
            )
    except Exception as exc:
        if "job_repo" in locals() and "job" in locals():
            _handle_retryable_failure(
                job_repo,
                job,
                code="JOB_EXECUTION_ERROR",
                message=str(exc),
                started_at=started_at,
            )
            logger.exception(
                "job_failed",
                extra={"job_id": str(job.id), "job_type": job.job_type, "error": str(exc)},
            )
    finally:
        if token is not None:
            clear_request_id(token)
        db.close()


def _handle_retryable_failure(
    job_repo: JobRepository,
    job: Job,
    *,
    code: str,
    message: str,
    started_at: float,
) -> None:
    duration_ms = (time.perf_counter() - started_at) * 1000

    if job_repo.has_retry_budget(job):
        queued = job_repo.queue_retry(job)
        record_job_run(job_type=job.job_type, status="failed", duration_ms=duration_ms)
        emit_event(
            "job_retry_scheduled",
            {
                "job_id": str(queued.id),
                "job_type": queued.job_type,
                "attempt_count": queued.attempt_count,
                "max_retries": queued.max_retries,
                "error_code": code,
                "error": message,
            },
        )
        logger.warning(
            "job_retry_scheduled",
            extra={
                "job_id": str(queued.id),
                "job_type": queued.job_type,
                "attempt_count": queued.attempt_count,
                "max_retries": queued.max_retries,
                "error_code": code,
            },
        )
        return

    dead_letter = job_repo.mark_dead_letter(job, code=code, message=message)
    record_job_run(job_type=job.job_type, status="dead_letter", duration_ms=duration_ms)
    emit_event(
        "job_dead_lettered",
        {
            "job_id": str(dead_letter.id),
            "job_type": dead_letter.job_type,
            "attempt_count": dead_letter.attempt_count,
            "max_retries": dead_letter.max_retries,
            "error_code": code,
            "error": message,
        },
    )
    logger.error(
        "job_dead_lettered",
        extra={
            "job_id": str(dead_letter.id),
            "job_type": dead_letter.job_type,
            "attempt_count": dead_letter.attempt_count,
            "max_retries": dead_letter.max_retries,
            "error_code": code,
        },
    )


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


def _run_intelligence_monitoring_job(job: Job) -> dict[str, Any]:
    db = SessionLocal()
    try:
        payload = job.job_payload or {}
        source_ids = [uuid.UUID(value) for value in payload.get("source_ids", [])]
        return scan_project_sources(
            db,
            project_id=uuid.UUID(payload["project_id"]),
            source_ids=source_ids or None,
            threshold=str(payload.get("alert_threshold", "medium")),
        )
    finally:
        db.close()


def _update_sources_status(db, sources: list[Source], *, status: str) -> None:
    for source in sources:
        source.status = status
        db.add(source)
    db.commit()
