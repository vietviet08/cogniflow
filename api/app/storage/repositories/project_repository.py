import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.storage.models import Project, ProjectMembership, Report, Source
from app.storage.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(
        self, name: str, description: str | None, owner_user_id: uuid.UUID, organization_id: uuid.UUID | None = None
    ) -> Project:
        project = Project(name=name, description=description, organization_id=organization_id)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        membership = ProjectMembership(
            project_id=project.id, user_id=owner_user_id, role="owner"
        )
        self.db.add(membership)
        self.db.commit()
        return project

    def get(self, project_id: uuid.UUID) -> Project | None:
        return self.db.get(Project, project_id)

    def list_with_stats(self, user_id: uuid.UUID, organization_id: uuid.UUID | None = None) -> list[dict]:
        # Basic implementation: list projects with source count and report count
        query = (
            self.db.query(Project, ProjectMembership.role)
            .join(ProjectMembership, ProjectMembership.project_id == Project.id)
            .filter(ProjectMembership.user_id == user_id)
        )
        
        if organization_id:
            query = query.filter(Project.organization_id == organization_id)
            
        projects = (
            query.order_by(Project.created_at.desc())
            .all()
        )
        result = []
        for p, role in projects:
            source_count = (
                self.db.query(func.count(Source.id))
                .filter(Source.project_id == p.id)
                .scalar()
                or 0
            )
            report_count = (
                self.db.query(func.count(Report.id))
                .filter(Report.project_id == p.id)
                .scalar()
                or 0
            )
            result.append(
                {
                    "id": str(p.id),
                    "organization_id": str(p.organization_id) if p.organization_id else None,
                    "name": p.name,
                    "description": p.description,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "role": role,
                    "source_count": source_count,
                    "report_count": report_count,
                }
            )
        return result

    def update(
        self, project_id: uuid.UUID, name: str, description: str | None
    ) -> Project | None:
        project = self.get(project_id)
        if project:
            project.name = name
            if description is not None:
                project.description = description
            self.db.commit()
            self.db.refresh(project)
        return project

    def delete(self, project_id: uuid.UUID) -> bool:
        project = self.get(project_id)
        if not project:
            return False

        # In a real production system, you'd use cascade deletes or background jobs.
        # For this prototype, the repository still attempts a direct delete and
        # relies on the database constraints to reject invalid cascades.
        # This can fail in Postgres and in SQLite with PRAGMA foreign_keys=ON.
        # but SQLAlchemy defaults SQLite foreign keys off unless specified).
        self.db.delete(project)
        try:
            self.db.commit()
            return True
        except Exception:
            self.db.rollback()
            return False
