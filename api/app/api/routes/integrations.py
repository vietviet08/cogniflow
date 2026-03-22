import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.services.integration_service import (
    IntegrationError,
    delete_integration_connection,
    import_integration_source,
    list_integration_statuses,
    upsert_integration_connection,
)
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/projects/{project_id}/integrations")


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
