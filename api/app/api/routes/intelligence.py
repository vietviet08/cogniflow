import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.config import get_settings
from app.core.security import require_current_user, require_project_role
from app.services.intelligence_service import (
    IntelligenceError,
    acknowledge_event,
    create_action,
    create_output,
    create_source,
    dispatch_action,
    get_roi_dashboard,
    get_today_digest,
    list_actions,
    list_approvals,
    list_events,
    list_integration_statuses,
    list_outputs,
    list_sources,
    request_approval,
    review_approval,
    scan_project_sources,
    update_action,
    update_source,
)
from app.storage.models import User
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.project_repository import ProjectRepository
from app.workers.tasks import run_job

router = APIRouter(prefix="/projects/{project_id}/intelligence")

DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]


class CreateRadarSourceRequest(BaseModel):
    name: str
    source_url: str
    category: str = "general"
    poll_interval_minutes: int = 1440
    is_active: bool = True


class UpdateRadarSourceRequest(BaseModel):
    name: str | None = None
    source_url: str | None = None
    category: str | None = None
    poll_interval_minutes: int | None = None
    is_active: bool | None = None


class ScanRadarRequest(BaseModel):
    mode: str = "sync"
    source_ids: list[uuid.UUID] | None = None
    alert_threshold: str = "medium"


class CreateActionRequest(BaseModel):
    title: str
    description: str
    event_id: uuid.UUID | None = None
    owner: str | None = None
    due_date_suggested: str | None = None
    priority: str = "medium"


class UpdateActionRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    owner: str | None = None
    due_date_suggested: str | None = None
    priority: str | None = None
    status: str | None = None


class DispatchActionRequest(BaseModel):
    provider: str
    destination: str | None = None


class CreateOutputRequest(BaseModel):
    output_type: str
    event_id: uuid.UUID | None = None
    context: str | None = None


class CreateApprovalRequest(BaseModel):
    target_type: str
    target_id: str


class ReviewApprovalRequest(BaseModel):
    status: str
    review_notes: str | None = None


def _ensure_project_exists(db: Session, project_id: uuid.UUID, request: Request):
    if ProjectRepository(db).get(project_id):
        return None
    return error_response(
        request,
        code="PROJECT_NOT_FOUND",
        message="Project does not exist",
        status_code=status.HTTP_404_NOT_FOUND,
    )


@router.get("/sources")
def list_intelligence_sources(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    items = list_sources(db, project_id)
    return success_response(request, {"items": items, "total": len(items)})


@router.post("/sources")
def create_intelligence_source(
    project_id: uuid.UUID,
    payload: CreateRadarSourceRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        data = create_source(
            db,
            project_id=project_id,
            name=payload.name,
            source_url=payload.source_url,
            category=payload.category,
            poll_interval_minutes=payload.poll_interval_minutes,
            is_active=payload.is_active,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, data, status_code=201)


@router.put("/sources/{source_id}")
def update_intelligence_source(
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    payload: UpdateRadarSourceRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        data = update_source(db, project_id=project_id, source_id=source_id, patch=payload.model_dump())
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, data)


@router.post("/scan")
def trigger_intelligence_scan(
    project_id: uuid.UUID,
    payload: ScanRadarRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    if payload.mode == "async":
        job = JobRepository(db).create(
            project_id=project_id,
            job_type="intelligence_monitoring",
            status="queued",
            queue_name="monitoring",
            job_payload={
                "project_id": str(project_id),
                "source_ids": [str(value) for value in (payload.source_ids or [])],
                "alert_threshold": payload.alert_threshold,
                "request_id": request.state.request_id,
            },
        )
        if get_settings().worker_inline_execution:
            background_tasks.add_task(run_job, str(job.id))
        return success_response(
            request,
            {"job_id": str(job.id), "status": job.status, "mode": "async"},
            status_code=202,
        )

    try:
        result = scan_project_sources(
            db,
            project_id=project_id,
            source_ids=payload.source_ids,
            threshold=payload.alert_threshold,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result)


@router.get("/events")
def list_intelligence_events(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    since_hours: int = 24,
    minimum_severity: str = "low",
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        items = list_events(
            db,
            project_id=project_id,
            since_hours=since_hours,
            minimum_severity=minimum_severity,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, {"items": items, "total": len(items)})


@router.post("/events/{event_id}/ack")
def acknowledge_intelligence_event(
    project_id: uuid.UUID,
    event_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        result = acknowledge_event(db, project_id=project_id, event_id=event_id)
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result)


@router.get("/digest/today")
def get_intelligence_today_digest(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    return success_response(request, get_today_digest(db, project_id=project_id))


@router.post("/actions")
def create_intelligence_action(
    project_id: uuid.UUID,
    payload: CreateActionRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        result = create_action(
            db,
            project_id=project_id,
            title=payload.title,
            description=payload.description,
            event_id=payload.event_id,
            owner=payload.owner,
            due_date_suggested=payload.due_date_suggested,
            priority=payload.priority,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result, status_code=201)


@router.get("/actions")
def list_intelligence_actions(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    status: str | None = None,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    items = list_actions(db, project_id=project_id, status=status)
    return success_response(request, {"items": items, "total": len(items)})


@router.patch("/actions/{action_id}")
def update_intelligence_action(
    project_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: UpdateActionRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        result = update_action(
            db,
            project_id=project_id,
            action_id=action_id,
            patch=payload.model_dump(),
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result)


@router.post("/actions/{action_id}/dispatch")
def dispatch_intelligence_action(
    project_id: uuid.UUID,
    action_id: uuid.UUID,
    payload: DispatchActionRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        result = dispatch_action(
            db,
            project_id=project_id,
            action_id=action_id,
            provider=payload.provider,
            destination=payload.destination,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result)


@router.get("/integrations")
def get_intelligence_integration_status(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    result = list_integration_statuses(db, project_id=project_id)
    return success_response(request, result)


@router.post("/outputs")
def create_intelligence_output(
    project_id: uuid.UUID,
    payload: CreateOutputRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        result = create_output(
            db,
            project_id=project_id,
            output_type=payload.output_type,
            event_id=payload.event_id,
            context=payload.context,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result, status_code=201)


@router.get("/outputs")
def list_intelligence_outputs(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    items = list_outputs(db, project_id=project_id)
    return success_response(request, {"items": items, "total": len(items)})


@router.post("/approvals")
def create_intelligence_approval(
    project_id: uuid.UUID,
    payload: CreateApprovalRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        result = request_approval(
            db,
            project_id=project_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            requested_by_user_id=current_user.id,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result, status_code=201)


@router.post("/approvals/{approval_id}/review")
def review_intelligence_approval(
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
    payload: ReviewApprovalRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="owner")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        result = review_approval(
            db,
            project_id=project_id,
            approval_id=approval_id,
            status=payload.status,
            review_notes=payload.review_notes,
            reviewed_by_user_id=current_user.id,
        )
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result)


@router.get("/approvals")
def list_intelligence_approvals(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    status: str | None = None,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    try:
        items = list_approvals(db, project_id=project_id, status=status)
    except IntelligenceError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, {"items": items, "total": len(items)})


@router.get("/roi")
def get_intelligence_roi_dashboard(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    window_days: int = 30,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    result = get_roi_dashboard(db, project_id=project_id, window_days=window_days)
    return success_response(request, result)
