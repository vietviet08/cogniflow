import uuid
from pathlib import Path

import requests
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.services.ingestion_service import IngestionError, ingest_remote_source, save_uploaded_file
from app.storage.models import Job, Source, User
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
    current_user: User = Depends(require_current_user),
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
    require_project_role(db, project_id=project_uuid, user=current_user, minimum_role="editor")

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
    duplicate_of_source = _apply_source_versioning_and_dedup(
        source_repo,
        source,
        project_id=project_uuid,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    source_metadata = source.source_metadata if isinstance(source.source_metadata, dict) else {}

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
            "source_version": source_metadata.get("version", 1),
            "duplicate_of_source_id": str(duplicate_of_source.id) if duplicate_of_source else None,
        },
        status_code=201,
    )


@router.post("/urls")
def ingest_url(
    payload: IngestUrlRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    project_repo = ProjectRepository(db)
    if not project_repo.get(payload.project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(
        db,
        project_id=payload.project_id,
        user=current_user,
        minimum_role="editor",
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
    duplicate_of_source = _apply_source_versioning_and_dedup(
        source_repo,
        source,
        project_id=payload.project_id,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    source_metadata = source.source_metadata if isinstance(source.source_metadata, dict) else {}

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
            "source_version": source_metadata.get("version", 1),
            "duplicate_of_source_id": str(duplicate_of_source.id) if duplicate_of_source else None,
        },
        status_code=201,
    )


@router.get("/{source_id}/artifact")
def get_source_artifact(
    source_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    source = SourceRepository(db).get(source_id)
    if not source:
        return error_response(
            request,
            code="SOURCE_NOT_FOUND",
            message="Source does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=source.project_id, user=current_user, minimum_role="viewer")
    if source.type != "file" or not source.storage_path:
        return error_response(
            request,
            code="SOURCE_ARTIFACT_UNAVAILABLE",
            message="Source artifact is unavailable for this source type.",
            status_code=status.HTTP_409_CONFLICT,
        )

    artifact_path = source.storage_path
    if not artifact_path.lower().endswith(".pdf"):
        return error_response(
            request,
            code="SOURCE_ARTIFACT_UNSUPPORTED",
            message="Only PDF artifacts are supported by the built-in viewer.",
            status_code=status.HTTP_409_CONFLICT,
        )
    if not Path(artifact_path).exists():
        return error_response(
            request,
            code="SOURCE_ARTIFACT_MISSING",
            message="Stored PDF artifact does not exist.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return FileResponse(
        artifact_path,
        media_type="application/pdf",
        filename=source.original_uri or f"{source.id}.pdf",
    )


@router.get("/project/{project_id}")
def list_sources(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    # Return sources with their latest job status
    sources = (
        db.query(Source)
        .filter(Source.project_id == project_id)
        .order_by(Source.created_at.desc())
        .all()
    )
    
    items = []
    for s in sources:
        # get latest job status for this source
        latest_job = (
            db.query(Job)
            .filter(Job.source_id == s.id)
            .order_by(Job.created_at.desc())
            .first()
        )
        status = latest_job.status if latest_job else s.status
        items.append({
            "id": str(s.id),
            "file_name": s.original_uri,
            "type": s.type,
            "provider": (s.source_metadata or {}).get("provider"),
            "status": status,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
        
    return success_response(request, {"items": items, "total": len(items)})


class BulkDeleteSourceRequest(BaseModel):
    source_ids: list[str]


@router.delete("/bulk")
def bulk_delete_sources(
    payload: BulkDeleteSourceRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    try:
        source_uuids = [uuid.UUID(sid) for sid in payload.source_ids]
        sources = db.query(Source).filter(Source.id.in_(source_uuids)).all()
        for source in sources:
            require_project_role(
                db,
                project_id=source.project_id,
                user=current_user,
                minimum_role="editor",
            )
        # In a real app we'd need to cascade delete chunks, documents, jobs etc.
        # SQLite with no pragmas might leave orphans, but for prototype we just delete the Source 
        db.query(Source).filter(Source.id.in_(source_uuids)).delete(synchronize_session=False)
        db.commit()
        return success_response(request, {"success": True, "deleted_count": len(source_uuids)})
    except Exception as e:
        db.rollback()
        return error_response(request, "DELETE_FAILED", str(e), status_code=500)


def _apply_source_versioning_and_dedup(
    source_repo: SourceRepository,
    source: Source,
    *,
    project_id: uuid.UUID,
) -> Source | None:
    duplicate_of_source = None
    if source.checksum:
        duplicate_of_source = source_repo.find_by_checksum(
            project_id=project_id,
            checksum=source.checksum,
            exclude_source_id=source.id,
        )

    source_metadata = source.source_metadata if isinstance(source.source_metadata, dict) else {}
    source_metadata["version"] = source_repo.next_version(
        project_id=project_id,
        original_uri=source.original_uri,
        exclude_source_id=source.id,
    )
    source_metadata["ingestion_policy"] = {
        "dedup_key": "checksum",
        "is_duplicate": duplicate_of_source is not None,
    }
    if duplicate_of_source is not None:
        source_metadata["duplicate_of_source_id"] = str(duplicate_of_source.id)
    else:
        source_metadata.pop("duplicate_of_source_id", None)
    source.source_metadata = source_metadata
    return duplicate_of_source
