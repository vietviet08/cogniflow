from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.storage.models import User
from app.storage.repositories.auth_token_repository import AuthTokenRepository
from app.storage.repositories.user_repository import UserRepository


class AuthServiceError(Exception):
    def __init__(self, message: str, *, code: str = "AUTH_FAILED", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def bootstrap_user(
    db: Session,
    *,
    email: str,
    display_name: str,
    password: str,
    role: str = "admin",
) -> dict:
    user_repo = UserRepository(db)
    if user_repo.count() > 0:
        raise AuthServiceError(
            "Bootstrap is only available before the first user exists.",
            code="AUTH_BOOTSTRAP_DISABLED",
            status_code=409,
        )

    normalized_password = password.strip()
    if len(normalized_password) < 3:
        raise AuthServiceError(
            "Password must be at least 3 characters.",
            code="AUTH_INVALID_PASSWORD",
            status_code=422,
        )

    existing = user_repo.get_by_email(email)
    if existing is not None:
        raise AuthServiceError(
            "A user with this email already exists.",
            code="AUTH_USER_EXISTS",
            status_code=409,
        )

    user = user_repo.create(
        email=email,
        display_name=display_name,
        password_hash=hash_password(normalized_password),
        role=role,
    )
    token_row, raw_token = AuthTokenRepository(db).create_for_user(
        user_id=user.id,
        token_name="bootstrap",
    )
    return serialize_auth_user(
        user,
        raw_token=raw_token,
        token_last_four=token_row.token_last_four,
    )


def login_user(
    db: Session,
    *,
    email: str,
    password: str,
    token_name: str = "default",
) -> dict:
    user_repo = UserRepository(db)
    user = user_repo.get_by_email(email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise AuthServiceError(
            "Invalid email or password.",
            code="AUTH_INVALID_CREDENTIALS",
            status_code=401,
        )

    token_row, raw_token = AuthTokenRepository(db).create_for_user(
        user_id=user.id,
        token_name=token_name,
    )
    return serialize_auth_user(
        user,
        raw_token=raw_token,
        token_last_four=token_row.token_last_four,
    )


def issue_token_for_user(db: Session, *, user: User, token_name: str) -> dict:
    token_row, raw_token = AuthTokenRepository(db).create_for_user(
        user_id=user.id,
        token_name=token_name,
    )
    return serialize_auth_user(
        user,
        raw_token=raw_token,
        token_last_four=token_row.token_last_four,
    )


def serialize_auth_user(
    user: User,
    *,
    raw_token: str | None = None,
    token_last_four: str | None = None,
) -> dict:
    payload = {
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "role": user.role,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
    }
    if raw_token is not None:
        payload["token"] = raw_token
    if token_last_four is not None:
        payload["token_last_four"] = token_last_four
    return payload
