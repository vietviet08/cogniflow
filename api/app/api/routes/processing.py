import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.storage.models import Job
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/jobs")


class ProcessingOptions(BaseModel):
    chunk_size: int = 800
    chunk_overlap: int = 120


class StartProcessingRequest(BaseModel):
    project_id: uuid.UUID
    source_ids: list[uuid.UUID]
    options: ProcessingOptions = ProcessingOptions()


@router.post("/processing")
def start_processing(
    payload: StartProcessingRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    project_repo = ProjectRepository(db)
    if not project_repo.get(payload.project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    job = Job(project_id=payload.project_id, job_type="processing", status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)

    return success_response(
        request,
        {"job_id": str(job.id), "status": job.status},
        status_code=201,
    )
