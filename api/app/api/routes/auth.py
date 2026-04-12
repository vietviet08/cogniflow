from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import success_response
from app.core.security import require_current_user
from app.services.auth_service import (
    AuthServiceError,
    bootstrap_user,
    issue_token_for_user,
    serialize_auth_user,
)
from app.storage.models import User

router = APIRouter(prefix="/auth")


class BootstrapAuthRequest(BaseModel):
    email: str
    display_name: str


class CreateTokenRequest(BaseModel):
    token_name: str = "default"


@router.post("/bootstrap")
def bootstrap_auth(payload: BootstrapAuthRequest, request: Request, db: Session = Depends(get_db)):
    try:
        result = bootstrap_user(db, email=payload.email, display_name=payload.display_name)
    except AuthServiceError as exc:
        from app.contracts.common import APIError

        raise APIError(code=exc.code, message=exc.message, status_code=exc.status_code) from exc
    return success_response(request, result, status_code=201)


@router.get("/me")
def get_me(
    request: Request,
    current_user: User = Depends(require_current_user),
):
    return success_response(request, serialize_auth_user(current_user))


@router.post("/tokens")
def create_token(
    payload: CreateTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    return success_response(
        request,
        issue_token_for_user(db, user=current_user, token_name=payload.token_name),
        status_code=201,
    )
