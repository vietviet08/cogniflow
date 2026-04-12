import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.storage.models import AuthToken
from app.storage.repositories.base import BaseRepository


def hash_bearer_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthTokenRepository(BaseRepository[AuthToken]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create_for_user(
        self,
        *,
        user_id: uuid.UUID,
        token_name: str = "default",
    ) -> tuple[AuthToken, str]:
        raw_token = secrets.token_urlsafe(32)
        row = AuthToken(
            user_id=user_id,
            token_name=token_name,
            token_hash=hash_bearer_token(raw_token),
            token_last_four=raw_token[-4:],
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row, raw_token

    def resolve(self, raw_token: str) -> AuthToken | None:
        token_hash = hash_bearer_token(raw_token)
        token = (
            self.db.query(AuthToken)
            .filter(AuthToken.token_hash == token_hash, AuthToken.revoked_at.is_(None))
            .one_or_none()
        )
        if token is not None:
            token.last_used_at = datetime.now(UTC)
            self.db.add(token)
            self.db.commit()
            self.db.refresh(token)
        return token
