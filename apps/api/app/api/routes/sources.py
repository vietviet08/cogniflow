import uuid

from fastapi import APIRouter, Depends, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.storage.models import Job
from app.storage.repositories.project_repository import ProjectRepository
from app.storage.repositories.source_repository import SourceRepository

router = APIRouter(prefix="/sources")


class IngestUrlRequest(BaseModel):
    project_id: uuid.UUID
    url: str


@router.post("/files")
async def upload_file_source(file: UploadFile, request: Request):
    _ = file
    return error_response(
        request,
        code="NOT_IMPLEMENTED",
        message="File ingestion scaffold exists but file persistence is not implemented yet.",
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
    )


@router.post("/urls")
def ingest_url(payload: IngestUrlRequest, request: Request, db: Session = Depends(get_db)):
    project_repo = ProjectRepository(db)
    if not project_repo.get(payload.project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    source_repo = SourceRepository(db)
    source = source_repo.create_url_source(payload.project_id, payload.url)

    job = Job(
        project_id=payload.project_id,
        source_id=source.id,
        job_type="ingestion",
        status="queued",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return success_response(
        request,
        {
            "source_id": str(source.id),
            "job_id": str(job.id),
            "status": job.status,
        },
        status_code=201,
    )
