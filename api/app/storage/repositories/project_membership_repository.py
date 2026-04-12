import uuid

from sqlalchemy.orm import Session

from app.storage.models import ProjectMembership
from app.storage.repositories.base import BaseRepository


class ProjectMembershipRepository(BaseRepository[ProjectMembership]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, *, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> ProjectMembership:
        membership = ProjectMembership(project_id=project_id, user_id=user_id, role=role)
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def get_membership(
        self,
        *,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ProjectMembership | None:
        return (
            self.db.query(ProjectMembership)
            .filter(
                ProjectMembership.project_id == project_id,
                ProjectMembership.user_id == user_id,
            )
            .one_or_none()
        )

    def list_project_ids_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return [
            membership.project_id
            for membership in self.db.query(ProjectMembership)
            .filter(ProjectMembership.user_id == user_id)
            .all()
        ]
