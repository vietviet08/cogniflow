from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.services.audit_service import log_audit_event
from app.services.intelligence_service import list_actions
from app.services.report_service import serialize_report
from app.storage.models import PublicLink, User
from app.storage.repositories.report_repository import ReportRepository

router = APIRouter(prefix="/projects/{project_id}/share-links")
public_router = APIRouter(prefix="/public/share")

_ALLOWED_TARGET_TYPES = {"report", "actions"}


class CreateShareLinkRequest(BaseModel):
    target_type: str
    target_id: str | None = None
    password: str | None = None
    expires_in_hours: int | None = None


class ResolveShareLinkRequest(BaseModel):
    password: str | None = None


DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]


@router.post("")
def create_share_link(
    project_id: uuid.UUID,
    payload: CreateShareLinkRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")

    target_type = payload.target_type.strip().lower()
    if target_type not in _ALLOWED_TARGET_TYPES:
        return error_response(
            request,
            code="SHARE_LINK_TARGET_INVALID",
            message="Share target type is invalid.",
            status_code=400,
            details={"allowed": sorted(_ALLOWED_TARGET_TYPES)},
        )

    if target_type == "report":
        if not payload.target_id:
            return error_response(
                request,
                code="SHARE_LINK_TARGET_MISSING",
                message="Report target id is required.",
                status_code=422,
            )
        report = ReportRepository(db).get(uuid.UUID(payload.target_id))
        if report is None or report.project_id != project_id:
            return error_response(
                request,
                code="REPORT_NOT_FOUND",
                message="Report does not exist for this project.",
                status_code=404,
            )

    expires_at = None
    if payload.expires_in_hours is not None:
        if payload.expires_in_hours <= 0:
            return error_response(
                request,
                code="SHARE_LINK_EXPIRY_INVALID",
                message="Expiry must be greater than zero.",
                status_code=422,
            )
        expires_at = datetime.now(UTC) + timedelta(hours=payload.expires_in_hours)

    password_hash = None
    if payload.password:
        password_hash = hashlib.sha256(payload.password.encode("utf-8")).hexdigest()

    row = PublicLink(
        project_id=project_id,
        target_type=target_type,
        target_id=(payload.target_id or "").strip() or "*",
        token=secrets.token_urlsafe(24),
        password_hash=password_hash,
        expires_at=expires_at,
        created_by_user_id=current_user.id,
    )
    db.add(row)
    log_audit_event(
        db,
        action="share_link.create",
        target_type="public_link",
        target_id=str(row.id),
        user_id=current_user.id,
        project_id=project_id,
        payload={"target_type": target_type, "target_id": row.target_id},
    )
    db.commit()
    db.refresh(row)

    return success_response(
        request,
        {
            "link_id": str(row.id),
            "project_id": str(row.project_id),
            "target_type": row.target_type,
            "target_id": row.target_id,
            "token": row.token,
            "url_path": f"/api/v1/public/share/{row.token}",
            "has_password": row.password_hash is not None,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "is_revoked": row.is_revoked,
        },
        status_code=201,
    )


@router.get("")
def list_share_links(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    rows = (
        db.query(PublicLink)
        .filter(PublicLink.project_id == project_id)
        .order_by(PublicLink.created_at.desc())
        .all()
    )
    return success_response(
        request,
        {
            "items": [
                {
                    "link_id": str(row.id),
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "token": row.token,
                    "url_path": f"/api/v1/public/share/{row.token}",
                    "has_password": row.password_hash is not None,
                    "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "is_revoked": row.is_revoked,
                }
                for row in rows
            ],
            "total": len(rows),
        },
    )


@router.delete("/{link_id}")
def revoke_share_link(
    project_id: uuid.UUID,
    link_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    row = (
        db.query(PublicLink)
        .filter(
            PublicLink.id == link_id,
            PublicLink.project_id == project_id,
        )
        .first()
    )
    if row is None:
        return error_response(
            request,
            code="SHARE_LINK_NOT_FOUND",
            message="Share link does not exist.",
            status_code=404,
        )

    row.is_revoked = True
    row.revoked_at = datetime.now(UTC)
    db.add(row)
    log_audit_event(
        db,
        action="share_link.revoke",
        target_type="public_link",
        target_id=str(row.id),
        user_id=current_user.id,
        project_id=project_id,
    )
    db.commit()

    return success_response(request, {"success": True})


@public_router.post("/{token}")
def resolve_share_link(
    token: str,
    payload: ResolveShareLinkRequest,
    request: Request,
    db: DBSession,
):
    row = (
        db.query(PublicLink)
        .filter(PublicLink.token == token)
        .first()
    )
    if row is None:
        return error_response(
            request,
            code="SHARE_LINK_NOT_FOUND",
            message="Share link does not exist.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    if row.is_revoked:
        return error_response(
            request,
            code="SHARE_LINK_REVOKED",
            message="Share link has been revoked.",
            status_code=status.HTTP_410_GONE,
        )

    if row.expires_at and row.expires_at < datetime.now(UTC):
        return error_response(
            request,
            code="SHARE_LINK_EXPIRED",
            message="Share link has expired.",
            status_code=status.HTTP_410_GONE,
        )

    if row.password_hash:
        candidate = (payload.password or "").encode("utf-8")
        if hashlib.sha256(candidate).hexdigest() != row.password_hash:
            return error_response(
                request,
                code="SHARE_LINK_PASSWORD_INVALID",
                message="Share link password is invalid.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )

    if row.target_type == "report":
        report = ReportRepository(db).get(uuid.UUID(row.target_id))
        if report is None:
            return error_response(
                request,
                code="REPORT_NOT_FOUND",
                message="Report does not exist.",
                status_code=status.HTTP_404_NOT_FOUND,
            )
        return success_response(
            request,
            {
                "target_type": "report",
                "target_id": row.target_id,
                "report": serialize_report(report, db),
            },
        )

    if row.target_type == "actions":
        return success_response(
            request,
            {
                "target_type": "actions",
                "target_id": row.target_id,
                "items": list_actions(db, project_id=row.project_id),
            },
        )

    return error_response(
        request,
        code="SHARE_LINK_TARGET_UNSUPPORTED",
        message="Share link target is unsupported.",
        status_code=422,
    )


@public_router.get("/{token}")
def resolve_share_link_get(
    token: str,
    request: Request,
    db: DBSession,
    password: str | None = None,
):
    return resolve_share_link(
        token=token,
        payload=ResolveShareLinkRequest(password=password),
        request=request,
        db=db,
    )
