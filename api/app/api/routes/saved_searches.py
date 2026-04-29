import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.config import get_settings
from app.core.security import require_current_user, require_project_role
from app.storage.models import SavedSearch, User
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.project_repository import ProjectRepository
from app.workers.tasks import run_job

router = APIRouter(prefix="/projects/{project_id}/saved-searches")

DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]

_ALLOWED_REPORT_TYPES = {
    "research_brief",
    "summary",
    "comparison",
    "action_items",
    "risk_analysis",
    "executive_brief",
}


class CreateSavedSearchRequest(BaseModel):
    name: str
    query: str
    filters: dict[str, Any] | None = None
    report_type: str = "research_brief"
    provider: str = "openai"
    schedule_interval_minutes: int | None = None
    is_active: bool = True


class UpdateSavedSearchRequest(BaseModel):
    name: str | None = None
    query: str | None = None
    filters: dict[str, Any] | None = None
    report_type: str | None = None
    provider: str | None = None
    schedule_interval_minutes: int | None = None
    is_active: bool | None = None


@router.post("")
def create_saved_search(
    project_id: uuid.UUID,
    payload: CreateSavedSearchRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    error = _validate_saved_search_payload(request, payload.report_type, payload.schedule_interval_minutes)
    if error is not None:
        return error

    row = SavedSearch(
        project_id=project_id,
        name=payload.name.strip() or "Saved search",
        query=payload.query.strip(),
        filters=payload.filters,
        report_type=payload.report_type.strip(),
        provider=payload.provider.strip().lower() or "openai",
        schedule_interval_minutes=payload.schedule_interval_minutes,
        is_active=payload.is_active,
        created_by_user_id=current_user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return success_response(request, _serialize_saved_search(row), status_code=201)


@router.get("")
def list_saved_searches(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    rows = (
        db.query(SavedSearch)
        .filter(SavedSearch.project_id == project_id)
        .order_by(SavedSearch.created_at.desc())
        .all()
    )
    return success_response(
        request,
        {"items": [_serialize_saved_search(row) for row in rows], "total": len(rows)},
    )


@router.patch("/{saved_search_id}")
def update_saved_search(
    project_id: uuid.UUID,
    saved_search_id: uuid.UUID,
    payload: UpdateSavedSearchRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    row = _get_saved_search(db, project_id=project_id, saved_search_id=saved_search_id)
    if row is None:
        return error_response(
            request,
            code="SAVED_SEARCH_NOT_FOUND",
            message="Saved search does not exist.",
            status_code=404,
        )

    report_type = payload.report_type if payload.report_type is not None else row.report_type
    interval = (
        payload.schedule_interval_minutes
        if payload.schedule_interval_minutes is not None
        else row.schedule_interval_minutes
    )
    error = _validate_saved_search_payload(request, report_type, interval)
    if error is not None:
        return error

    if payload.name is not None:
        row.name = payload.name.strip() or row.name
    if payload.query is not None:
        row.query = payload.query.strip() or row.query
    if payload.filters is not None:
        row.filters = payload.filters
    if payload.report_type is not None:
        row.report_type = payload.report_type.strip()
    if payload.provider is not None:
        row.provider = payload.provider.strip().lower() or row.provider
    if payload.schedule_interval_minutes is not None:
        row.schedule_interval_minutes = payload.schedule_interval_minutes
    if payload.is_active is not None:
        row.is_active = payload.is_active
    db.add(row)
    db.commit()
    db.refresh(row)
    return success_response(request, _serialize_saved_search(row))


@router.post("/{saved_search_id}/run")
def run_saved_search(
    project_id: uuid.UUID,
    saved_search_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    row = _get_saved_search(db, project_id=project_id, saved_search_id=saved_search_id)
    if row is None:
        return error_response(
            request,
            code="SAVED_SEARCH_NOT_FOUND",
            message="Saved search does not exist.",
            status_code=404,
        )

    job = JobRepository(db).create(
        project_id=project_id,
        job_type="report_generation",
        status="queued",
        queue_name="report",
        job_payload={
            "project_id": str(project_id),
            "query": row.query,
            "type": row.report_type,
            "format": "markdown",
            "provider": row.provider,
            "filters": row.filters or {},
            "saved_search_id": str(row.id),
            "request_id": request.state.request_id,
        },
    )
    row.last_run_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)

    if get_settings().worker_inline_execution:
        background_tasks.add_task(run_job, str(job.id))

    return success_response(
        request,
        {
            "saved_search": _serialize_saved_search(row),
            "job_id": str(job.id),
            "status": job.status,
        },
        status_code=202,
    )


def _ensure_project_exists(db: Session, project_id: uuid.UUID, request: Request):
    if ProjectRepository(db).get(project_id):
        return None
    return error_response(
        request,
        code="PROJECT_NOT_FOUND",
        message="Project does not exist",
        status_code=404,
    )


def _get_saved_search(
    db: Session,
    *,
    project_id: uuid.UUID,
    saved_search_id: uuid.UUID,
) -> SavedSearch | None:
    return (
        db.query(SavedSearch)
        .filter(SavedSearch.id == saved_search_id, SavedSearch.project_id == project_id)
        .first()
    )


def _validate_saved_search_payload(
    request: Request,
    report_type: str,
    schedule_interval_minutes: int | None,
):
    if report_type.strip() not in _ALLOWED_REPORT_TYPES:
        return error_response(
            request,
            code="SAVED_SEARCH_REPORT_TYPE_INVALID",
            message="Saved search report type is invalid.",
            status_code=422,
            details={"allowed": sorted(_ALLOWED_REPORT_TYPES)},
        )
    if schedule_interval_minutes is not None and schedule_interval_minutes < 15:
        return error_response(
            request,
            code="SAVED_SEARCH_SCHEDULE_INVALID",
            message="Saved search schedule interval must be at least 15 minutes.",
            status_code=422,
        )
    return None


def _serialize_saved_search(row: SavedSearch) -> dict[str, Any]:
    return {
        "saved_search_id": str(row.id),
        "project_id": str(row.project_id),
        "name": row.name,
        "query": row.query,
        "filters": row.filters or {},
        "report_type": row.report_type,
        "provider": row.provider,
        "schedule_interval_minutes": row.schedule_interval_minutes,
        "is_active": row.is_active,
        "created_by_user_id": str(row.created_by_user_id) if row.created_by_user_id else None,
        "last_run_at": row.last_run_at.isoformat() if row.last_run_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
