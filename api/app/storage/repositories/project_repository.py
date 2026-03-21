import uuid

from sqlalchemy.orm import Session

from app.storage.models import Project
from app.storage.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(self, name: str, description: str | None) -> Project:
        project = Project(name=name, description=description)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get(self, project_id: uuid.UUID) -> Project | None:
        return self.db.get(Project, project_id)
