import uuid
import hashlib
import hmac
import secrets

from fastapi import Depends, Header, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import APIError
from app.storage.models import User
from app.storage.repositories.auth_token_repository import AuthTokenRepository
from app.storage.repositories.project_membership_repository import ProjectMembershipRepository
from app.storage.repositories.user_repository import UserRepository
from app.storage.repositories.organization_membership_repository import OrganizationMembershipRepository

ROLE_ORDER = {"viewer": 10, "editor": 20, "admin": 30}
ORG_ROLE_ORDER = {"member": 10, "admin": 20, "owner": 30}
PASSWORD_HASH_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, rounds_raw, salt, digest = stored_hash.split("$", maxsplit=3)
        if algorithm != "pbkdf2_sha256":
            return False
        rounds = int(rounds_raw)
    except (ValueError, TypeError):
        return False

    computed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        rounds,
    ).hex()
    return hmac.compare_digest(computed, digest)


def require_bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise APIError(
            code="AUTH_REQUIRED",
            message="Missing bearer token.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return authorization.split(" ", maxsplit=1)[1]


def require_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    raw_token = require_bearer_token(authorization)
    token = AuthTokenRepository(db).resolve(raw_token)
    if token is None:
        raise APIError(
            code="AUTH_INVALID_TOKEN",
            message="Bearer token is invalid or revoked.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    user = UserRepository(db).get(token.user_id)
    if user is None or not user.is_active:
        raise APIError(
            code="AUTH_USER_INACTIVE",
            message="Authenticated user is unavailable.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return user


def require_project_role(
    db: Session,
    *,
    project_id: uuid.UUID,
    user: User,
    minimum_role: str = "viewer",
) -> None:
    membership = ProjectMembershipRepository(db).get_membership(
        project_id=project_id,
        user_id=user.id,
    )
    if membership is None:
        raise APIError(
            code="PROJECT_FORBIDDEN",
            message="You do not have access to this project.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if ROLE_ORDER.get(membership.role, 0) < ROLE_ORDER.get(minimum_role, 0):
        raise APIError(
            code="PROJECT_ROLE_FORBIDDEN",
            message=f"This operation requires project role '{minimum_role}' or higher.",
            status_code=status.HTTP_403_FORBIDDEN,
        )

def require_organization_role(
    db: Session,
    *,
    organization_id: uuid.UUID,
    user: User,
    minimum_role: str = "member",
) -> None:
    membership = OrganizationMembershipRepository(db).get_membership(
        organization_id=organization_id,
        user_id=user.id,
    )
    # Give full access if user is superadmin (system-wide)
    if user.role == "admin":
        return
        
    if membership is None:
        raise APIError(
            code="ORGANIZATION_FORBIDDEN",
            message="You do not have access to this organization.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    if ORG_ROLE_ORDER.get(membership.role, 0) < ORG_ROLE_ORDER.get(minimum_role, 0):
        raise APIError(
            code="ORGANIZATION_ROLE_FORBIDDEN",
            message=f"This operation requires organization role '{minimum_role}' or higher.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
