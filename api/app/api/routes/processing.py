import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.storage.models import User
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.project_repository import ProjectRepository
from app.storage.repositories.source_repository import SourceRepository
from app.workers.tasks import run_job

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
    background_tasks: BackgroundTasks,
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

    for source in sources:
        source.status = "queued"
        db.add(source)
    db.commit()

    job = JobRepository(db).create(
        project_id=payload.project_id,
        job_type="processing",
        status="queued",
        progress=0,
        queue_name="processing",
        job_payload={
            "project_id": str(payload.project_id),
            "source_ids": [str(source_id) for source_id in payload.source_ids],
            "chunk_size": payload.options.chunk_size,
            "chunk_overlap": payload.options.chunk_overlap,
            "request_id": request.state.request_id,
        },
    )
    background_tasks.add_task(run_job, str(job.id))

    return success_response(
        request,
        {
            "job_id": str(job.id),
            "status": job.status,
        },
        status_code=202,
    )
