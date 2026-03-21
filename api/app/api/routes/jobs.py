import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.storage.repositories.job_repository import JobRepository

router = APIRouter(prefix="/jobs")


@router.get("/{job_id}")
def get_job(job_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    job = JobRepository(db).get(job_id)
    if not job:
        return error_response(
            request,
            code="JOB_NOT_FOUND",
            message="Job does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return success_response(
        request,
        {
            "job_id": str(job.id),
            "type": job.job_type,
            "status": job.status,
            "progress": job.progress,
            "error": None,
        },
    )


@router.post("/{job_id}/cancel")
def cancel_job(job_id: uuid.UUID, request: Request):
    _ = job_id
    return success_response(request, {"status": "queued_for_cancellation"}, status_code=202)


@router.post("/{job_id}/retry")
def retry_job(job_id: uuid.UUID, request: Request):
    _ = job_id
    return success_response(request, {"status": "queued_for_retry"}, status_code=202)
