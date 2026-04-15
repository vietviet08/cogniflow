import uuid
from sqlalchemy.orm import Session
from app.storage.models import Organization
from app.storage.repositories.base import BaseRepository

class OrganizationRepository(BaseRepository[Organization]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, *, name: str, slug: str | None = None) -> Organization:
        org = Organization(name=name, slug=slug)
        self.db.add(org)
        self.db.commit()
        self.db.refresh(org)
        return org

    def get_by_id(self, organization_id: uuid.UUID) -> Organization | None:
        return self.db.query(Organization).filter(Organization.id == organization_id).one_or_none()
