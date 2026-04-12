import uuid

from sqlalchemy.orm import Session

from app.storage.models import User
from app.storage.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: Session):
        super().__init__(db)

    def count(self) -> int:
        return self.db.query(User).count()

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().lower()
        return self.db.query(User).filter(User.email == normalized_email).one_or_none()

    def create(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        role: str = "admin",
    ) -> User:
        user = User(
            email=email.strip().lower(),
            display_name=display_name.strip(),
            password_hash=password_hash,
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
