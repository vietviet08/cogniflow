import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.services.provider_settings_service import (
    ProviderSettingsError,
    delete_provider_key,
    list_provider_statuses,
    upsert_provider_key,
)
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/projects/{project_id}/providers")


class UpsertProviderKeyRequest(BaseModel):
    api_key: str
    base_url: str | None = None
    chat_model: str
    embedding_model: str | None = None


@router.get("")
def list_project_provider_settings(
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
        {"items": list_provider_statuses(db, project_id)},
    )


@router.put("/{provider}")
def save_project_provider_key(
    project_id: uuid.UUID,
    provider: str,
    payload: UpsertProviderKeyRequest,
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
        status_payload = upsert_provider_key(
            db=db,
            project_id=project_id,
            provider=provider,
            api_key=payload.api_key,
            base_url=payload.base_url,
            chat_model=payload.chat_model,
            embedding_model=payload.embedding_model,
        )
    except ProviderSettingsError as exc:
        return error_response(
            request,
            code="PROVIDER_SETTINGS_INVALID",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return success_response(request, status_payload)


@router.delete("/{provider}")
def remove_project_provider_key(
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
        status_payload = delete_provider_key(
            db=db,
            project_id=project_id,
            provider=provider,
        )
    except ProviderSettingsError as exc:
        return error_response(
            request,
            code="PROVIDER_SETTINGS_INVALID",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return success_response(request, status_payload)
