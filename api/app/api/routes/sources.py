import uuid

import requests
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.services.ingestion_service import IngestionError, ingest_remote_source, save_uploaded_file
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.project_repository import ProjectRepository
from app.storage.repositories.source_repository import SourceRepository

router = APIRouter(prefix="/sources")


class IngestUrlRequest(BaseModel):
    project_id: uuid.UUID
    url: str


@router.post("/files")
async def upload_file_source(
    request: Request,
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        project_uuid = uuid.UUID(project_id)
    except ValueError:
        return error_response(
            request,
            code="INVALID_PROJECT_ID",
            message="project_id must be a valid UUID",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    project_repo = ProjectRepository(db)
    if not project_repo.get(project_uuid):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    source_repo = SourceRepository(db)
    source = source_repo.create(
        project_id=project_uuid,
        source_type="file",
        original_uri=file.filename,
    )

    try:
        storage_path, checksum = save_uploaded_file(source.id, file)
    except OSError as exc:
        return error_response(
            request,
            code="FILE_PERSISTENCE_FAILED",
            message="Failed to persist uploaded file.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"reason": str(exc)},
        )

    source.storage_path = storage_path
    source.checksum = checksum
    source.status = "completed"
    db.add(source)
    db.commit()
    db.refresh(source)

    job = JobRepository(db).create(
        project_id=project_uuid,
        source_id=source.id,
        job_type="ingestion",
        status="completed",
        progress=100,
    )

    return success_response(
        request,
        {
            "source_id": str(source.id),
            "job_id": str(job.id),
            "status": job.status,
            "source_type": source.type,
            "filename": file.filename,
        },
        status_code=201,
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
    source = source_repo.create(
        project_id=payload.project_id,
        source_type="url",
        original_uri=payload.url,
    )

    try:
        storage_path, checksum, source_type = ingest_remote_source(source.id, payload.url)
    except IngestionError as exc:
        return error_response(
            request,
            code="INGESTION_FAILED",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except requests.RequestException as exc:
        return error_response(
            request,
            code="REMOTE_FETCH_FAILED",
            message="Failed to fetch remote source.",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={"reason": str(exc)},
        )

    source.type = source_type
    source.storage_path = storage_path
    source.checksum = checksum
    source.status = "completed"
    db.add(source)
    db.commit()
    db.refresh(source)

    job = JobRepository(db).create(
        project_id=payload.project_id,
        source_id=source.id,
        job_type="ingestion",
        status="completed",
        progress=100,
    )

    return success_response(
        request,
        {
            "source_id": str(source.id),
            "job_id": str(job.id),
            "status": job.status,
            "source_type": source.type,
        },
        status_code=201,
    )
