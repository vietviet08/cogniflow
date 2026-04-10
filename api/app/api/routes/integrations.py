import uuid

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from urllib.parse import urlencode

from app.api.deps import get_db
from app.core.config import get_settings
from app.contracts.common import error_response, success_response
from app.services.integration_service import (
    build_google_drive_oauth_start_url,
    complete_google_drive_oauth_callback,
    IntegrationError,
    delete_integration_connection,
    import_integration_source,
    list_integration_statuses,
    upsert_integration_connection,
)
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/projects/{project_id}/integrations")
oauth_router = APIRouter(prefix="/integrations")


class UpsertIntegrationConnectionRequest(BaseModel):
    access_token: str | None = None
    account_label: str | None = None
    base_url: str | None = None
    connection_metadata: dict | None = None


class ImportIntegrationSourceRequest(BaseModel):
    item_reference: str


@router.get("")
def list_project_integrations(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    if not ProjectRepository(db).get(project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return success_response(
        request,
        {"items": list_integration_statuses(db, project_id)},
    )


@router.put("/{provider}")
def save_project_integration_connection(
    project_id: uuid.UUID,
    provider: str,
    payload: UpsertIntegrationConnectionRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not ProjectRepository(db).get(project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        result = upsert_integration_connection(
            db=db,
            project_id=project_id,
            provider=provider,
            access_token=payload.access_token,
            account_label=payload.account_label,
            base_url=payload.base_url,
            connection_metadata=payload.connection_metadata,
        )
    except IntegrationError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
    return success_response(request, result)


@router.delete("/{provider}")
def remove_project_integration_connection(
    project_id: uuid.UUID,
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
):
    if not ProjectRepository(db).get(project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        result = delete_integration_connection(
            db=db,
            project_id=project_id,
            provider=provider,
        )
    except IntegrationError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
    return success_response(request, result)


@router.post("/{provider}/import")
def import_project_integration_source(
    project_id: uuid.UUID,
    provider: str,
    payload: ImportIntegrationSourceRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    if not ProjectRepository(db).get(project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        result = import_integration_source(
            db=db,
            project_id=project_id,
            provider=provider,
            item_reference=payload.item_reference,
        )
    except IntegrationError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result, status_code=201)


@router.get("/google_drive/oauth/start")
def start_google_drive_oauth(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    if not ProjectRepository(db).get(project_id):
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        redirect_url = build_google_drive_oauth_start_url(
            project_id=project_id,
            callback_url=str(request.url_for("google_drive_oauth_callback")),
        )
    except IntegrationError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return RedirectResponse(redirect_url, status_code=302)


@oauth_router.get("/google_drive/oauth/callback", name="google_drive_oauth_callback")
def google_drive_oauth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if error:
        return RedirectResponse(
            f"{settings.web_app_url.rstrip('/')}/sources?{urlencode({'integration': 'google_drive', 'status': 'error', 'message': error})}",
            status_code=302,
        )

    try:
        result = complete_google_drive_oauth_callback(
            db=db,
            code=code,
            state=state,
            callback_url=str(request.url_for("google_drive_oauth_callback")),
        )
    except IntegrationError as exc:
        return RedirectResponse(
            f"{settings.web_app_url.rstrip('/')}/sources?{urlencode({'integration': 'google_drive', 'status': 'error', 'message': exc.message})}",
            status_code=302,
        )

    return RedirectResponse(result.redirect_url, status_code=302)
