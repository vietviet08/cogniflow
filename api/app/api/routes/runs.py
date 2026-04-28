import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.config import get_settings
from app.core.security import require_current_user, require_project_role
from app.storage.models import ProcessingRun, User
from app.storage.repositories.job_repository import JobRepository
from app.workers.tasks import run_job

router = APIRouter(prefix="/runs")


@router.post("/{run_id}/replay")
def replay_run(
    run_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    run = db.get(ProcessingRun, run_id)
    if run is None:
        return error_response(
            request,
            code="RUN_NOT_FOUND",
            message="Run does not exist.",
            status_code=404,
        )
    require_project_role(
        db,
        project_id=run.project_id,
        user=current_user,
        minimum_role="editor",
    )

    try:
        job = _create_replay_job(db, run=run, request_id=request.state.request_id)
    except ValueError as exc:
        return error_response(
            request,
            code="RUN_REPLAY_UNSUPPORTED",
            message=str(exc),
            status_code=422,
        )

    if get_settings().worker_inline_execution:
        background_tasks.add_task(run_job, str(job.id))

    return success_response(
        request,
        {
            "job_id": str(job.id),
            "status": job.status,
            "run_id": str(run.id),
            "run_type": run.run_type,
        },
        status_code=202,
    )


@router.get("/{left_run_id}/compare/{right_run_id}")
def compare_runs(
    left_run_id: uuid.UUID,
    right_run_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    left = db.get(ProcessingRun, left_run_id)
    right = db.get(ProcessingRun, right_run_id)
    if left is None or right is None:
        return error_response(
            request,
            code="RUN_NOT_FOUND",
            message="One or both runs do not exist.",
            status_code=404,
        )
    require_project_role(
        db,
        project_id=left.project_id,
        user=current_user,
        minimum_role="viewer",
    )
    require_project_role(
        db,
        project_id=right.project_id,
        user=current_user,
        minimum_role="viewer",
    )

    return success_response(
        request,
        {
            "left": _serialize_run_summary(left),
            "right": _serialize_run_summary(right),
            "same_project": left.project_id == right.project_id,
            "same_run_type": left.run_type == right.run_type,
            "diff": _build_run_diff(left, right),
        },
    )


def _create_replay_job(db: Session, *, run: ProcessingRun, request_id: str):
    metadata = run.run_metadata or {}
    base_payload: dict[str, Any] = {
        "project_id": str(run.project_id),
        "request_id": request_id,
        "replay_of_run_id": str(run.id),
    }

    if run.run_type == "processing":
        source_ids = metadata.get("source_ids")
        if not isinstance(source_ids, list) or not source_ids:
            raise ValueError("Processing replay requires source_ids in run metadata.")
        payload = {
            **base_payload,
            "source_ids": source_ids,
            "chunk_size": metadata.get("chunk_size", 800),
            "chunk_overlap": metadata.get("chunk_overlap", 120),
        }
        return JobRepository(db).create(
            project_id=run.project_id,
            job_type="processing",
            status="queued",
            queue_name="processing",
            job_payload=payload,
        )

    if run.run_type == "insight":
        query = metadata.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Insight replay requires query in run metadata.")
        payload = {
            **base_payload,
            "query": query,
            "provider": metadata.get("provider", "openai"),
            "max_sources": metadata.get("max_sources", 20),
        }
        return JobRepository(db).create(
            project_id=run.project_id,
            job_type="insight_generation",
            status="queued",
            queue_name="insight",
            job_payload=payload,
        )

    if run.run_type in {"report", "mesh"}:
        query = metadata.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Report replay requires query in run metadata.")
        report_type = metadata.get("report_type")
        if run.run_type == "mesh":
            report_type = "conflict_mesh"
        payload = {
            **base_payload,
            "query": query,
            "type": report_type or "research_brief",
            "format": metadata.get("format", "markdown"),
            "provider": metadata.get("provider", "openai"),
        }
        return JobRepository(db).create(
            project_id=run.project_id,
            job_type="report_generation",
            status="queued",
            queue_name="report",
            job_payload=payload,
        )

    raise ValueError(f"Replay is not supported for run type '{run.run_type}'.")


def _serialize_run_summary(run: ProcessingRun) -> dict[str, Any]:
    return {
        "run_id": str(run.id),
        "project_id": str(run.project_id),
        "run_type": run.run_type,
        "model_id": run.model_id,
        "prompt_hash": run.prompt_hash,
        "config_hash": run.config_hash,
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "run_metadata": run.run_metadata or {},
    }


def _build_run_diff(left: ProcessingRun, right: ProcessingRun) -> dict[str, Any]:
    metadata_keys = sorted(set((left.run_metadata or {}).keys()) | set((right.run_metadata or {}).keys()))
    changed_metadata = [
        key
        for key in metadata_keys
        if (left.run_metadata or {}).get(key) != (right.run_metadata or {}).get(key)
    ]
    return {
        "model_changed": left.model_id != right.model_id,
        "prompt_changed": left.prompt_hash != right.prompt_hash,
        "config_changed": left.config_hash != right.config_hash,
        "retrieval_config_changed": left.retrieval_config != right.retrieval_config,
        "metadata_changed": changed_metadata,
    }
