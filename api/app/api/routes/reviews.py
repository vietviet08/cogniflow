import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.services.intelligence_service import (
    IntelligenceError,
    list_approvals,
    request_approval,
    review_approval,
)
from app.storage.models import Insight, Report, User
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/projects/{project_id}/reviews")

DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]

_ALLOWED_TARGET_TYPES = {"insight", "report"}


class CreateReviewRequest(BaseModel):
    target_type: str
    target_id: uuid.UUID


class ReviewDecisionRequest(BaseModel):
    status: str
    review_notes: str | None = None


@router.post("")
def request_research_review(
    project_id: uuid.UUID,
    payload: CreateReviewRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    missing_project_response = _ensure_project_exists(db, project_id, request)
    if missing_project_response is not None:
        return missing_project_response

    target_type = payload.target_type.strip().lower()
    if target_type not in _ALLOWED_TARGET_TYPES:
        return error_response(
            request,
            code="REVIEW_TARGET_INVALID",
            message="Review target type is invalid.",
            status_code=422,
            details={"allowed": sorted(_ALLOWED_TARGET_TYPES)},
        )
    if not _target_exists(db, project_id=project_id, target_type=target_type, target_id=payload.target_id):
        return error_response(
            request,
            code="REVIEW_TARGET_NOT_FOUND",
            message="Review target does not exist for this project.",
            status_code=404,
        )

    try:
        result = request_approval(
            db,
            project_id=project_id,
            target_type=target_type,
            target_id=str(payload.target_id),
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


@router.get("")
def list_research_reviews(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    status: str | None = None,
    target_type: str | None = None,
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

    if target_type:
        normalized_type = target_type.strip().lower()
        if normalized_type not in _ALLOWED_TARGET_TYPES:
            return error_response(
                request,
                code="REVIEW_TARGET_INVALID",
                message="Review target type is invalid.",
                status_code=422,
                details={"allowed": sorted(_ALLOWED_TARGET_TYPES)},
            )
        items = [item for item in items if item["target_type"] == normalized_type]
    else:
        items = [item for item in items if item["target_type"] in _ALLOWED_TARGET_TYPES]

    return success_response(request, {"items": items, "total": len(items)})


@router.post("/{review_id}/decision")
def decide_research_review(
    project_id: uuid.UUID,
    review_id: uuid.UUID,
    payload: ReviewDecisionRequest,
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
            approval_id=review_id,
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


def _ensure_project_exists(db: Session, project_id: uuid.UUID, request: Request):
    if ProjectRepository(db).get(project_id):
        return None
    return error_response(
        request,
        code="PROJECT_NOT_FOUND",
        message="Project does not exist",
        status_code=404,
    )


def _target_exists(
    db: Session,
    *,
    project_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
) -> bool:
    model = Report if target_type == "report" else Insight
    row = db.get(model, target_id)
    return bool(row and row.project_id == project_id)
