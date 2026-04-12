import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.config import get_settings
from app.core.security import require_current_user, require_project_role
from app.storage.models import User
from app.storage.repositories.job_repository import JobRepository
from app.workers.tasks import run_job

router = APIRouter(prefix="/jobs")
JOB_NOT_FOUND_MESSAGE = "Job does not exist"

DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]


def _serialize_job(job) -> dict[str, object]:
    return {
        "job_id": str(job.id),
        "type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "attempt_count": job.attempt_count,
        "max_retries": job.max_retries,
        "queue_name": job.queue_name,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "error": {
            "code": job.error_code,
            "message": job.error_message,
        }
        if job.error_code or job.error_message
        else None,
        "result": job.result_payload,
    }


@router.get("/{job_id}")
def get_job(
    job_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    job = JobRepository(db).get(job_id)
    if not job:
        return error_response(
            request,
            code="JOB_NOT_FOUND",
            message=JOB_NOT_FOUND_MESSAGE,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=job.project_id, user=current_user, minimum_role="viewer")

    return success_response(request, _serialize_job(job))


@router.get("/project/{project_id}")
def list_project_jobs(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    limit: int = 100,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    jobs = JobRepository(db).list_by_project(project_id, limit=limit)
    return success_response(
        request,
        {
            "items": [_serialize_job(job) for job in jobs],
            "total": len(jobs),
        },
    )


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    job = JobRepository(db).get(job_id)
    if not job:
        return error_response(
            request,
            code="JOB_NOT_FOUND",
            message=JOB_NOT_FOUND_MESSAGE,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=job.project_id, user=current_user, minimum_role="editor")
    updated = JobRepository(db).request_cancellation(job)
    return success_response(
        request,
        {
            "job_id": str(updated.id),
            "status": updated.status,
            "cancel_requested_at": updated.cancel_requested_at.isoformat()
            if updated.cancel_requested_at
            else None,
        },
        status_code=202,
    )


@router.post("/{job_id}/retry")
def retry_job(
    job_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DBSession,
    current_user: CurrentUser,
):
    job = JobRepository(db).get(job_id)
    if not job:
        return error_response(
            request,
            code="JOB_NOT_FOUND",
            message=JOB_NOT_FOUND_MESSAGE,
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=job.project_id, user=current_user, minimum_role="editor")
    if job.status not in {"failed", "dead_letter", "cancelled"}:
        return error_response(
            request,
            code="JOB_RETRY_INVALID_STATE",
            message="Only failed, dead-letter, or cancelled jobs can be retried.",
            status_code=status.HTTP_409_CONFLICT,
        )

    job = JobRepository(db).queue_retry(job)
    if get_settings().worker_inline_execution:
        background_tasks.add_task(run_job, str(job.id))
    return success_response(
        request,
        {"job_id": str(job.id), "status": job.status},
        status_code=202,
    )
