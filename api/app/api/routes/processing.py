import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.services.processing_service import ProcessingError, process_sources
from app.storage.models import User
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.project_repository import ProjectRepository
from app.storage.repositories.source_repository import SourceRepository

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
    current_user: User = Depends(require_current_user),
):
    require_project_role(
        db,
        project_id=payload.project_id,
        user=current_user,
        minimum_role="editor",
    )
    project_repo = ProjectRepository(db)
    if not project_repo.get(payload.project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    source_repo = SourceRepository(db)
    sources = source_repo.list_by_ids(payload.project_id, payload.source_ids)
    if len(sources) != len(payload.source_ids):
        return error_response(
            request,
            code="SOURCE_NOT_FOUND",
            message="One or more source IDs do not exist in the project.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    job_repo = JobRepository(db)
    job = job_repo.create(
        project_id=payload.project_id,
        job_type="processing",
        status="running",
        progress=0,
    )

    try:
        result = process_sources(
            db=db,
            project_id=payload.project_id,
            job_id=job.id,
            sources=sources,
            chunk_size=payload.options.chunk_size,
            chunk_overlap=payload.options.chunk_overlap,
        )
    except (ProcessingError, ValueError) as exc:
        job_repo.update_status(job, status="failed", progress=0)
        return error_response(
            request,
            code="PROCESSING_FAILED",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except Exception as exc:
        job_repo.update_status(job, status="failed", progress=0)
        return error_response(
            request,
            code="PROCESSING_INTERNAL_ERROR",
            message="Unexpected processing failure.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"reason": str(exc)},
        )

    job = job_repo.update_status(job, status="completed", progress=100)

    return success_response(
        request,
        {
            "job_id": str(job.id),
            "run_id": result["run_id"],
            "status": job.status,
            "documents_created": result["documents_created"],
            "chunks_created": result["chunks_created"],
        },
        status_code=201,
    )
