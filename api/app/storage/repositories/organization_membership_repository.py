import uuid
from sqlalchemy.orm import Session
from app.storage.models import OrganizationMembership
from app.storage.repositories.base import BaseRepository

class OrganizationMembershipRepository(BaseRepository[OrganizationMembership]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, *, organization_id: uuid.UUID, user_id: uuid.UUID, role: str) -> OrganizationMembership:
        membership = OrganizationMembership(
            organization_id=organization_id, 
            user_id=user_id, 
            role=role
        )
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def get_membership(
        self,
        *,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> OrganizationMembership | None:
        return (
            self.db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user_id,
            )
            .one_or_none()
        )

    def list_organization_ids_for_user(self, user_id: uuid.UUID) -> list[uuid.UUID]:
        return [
            membership.organization_id
            for membership in self.db.query(OrganizationMembership)
            .filter(OrganizationMembership.user_id == user_id)
            .all()
        ]
