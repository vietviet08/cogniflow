import uuid

from sqlalchemy.orm import Session

from app.storage.models import IntegrationConnection
from app.storage.repositories.base import BaseRepository


class IntegrationConnectionRepository(BaseRepository[IntegrationConnection]):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_project_and_provider(
        self,
        project_id: uuid.UUID,
        provider: str,
    ) -> IntegrationConnection | None:
        return (
            self.db.query(IntegrationConnection)
            .filter(
                IntegrationConnection.project_id == project_id,
                IntegrationConnection.provider == provider,
            )
            .first()
        )

    def list_by_project(self, project_id: uuid.UUID) -> list[IntegrationConnection]:
        return (
            self.db.query(IntegrationConnection)
            .filter(IntegrationConnection.project_id == project_id)
            .order_by(IntegrationConnection.provider.asc())
            .all()
        )

    def save(self, connection: IntegrationConnection) -> IntegrationConnection:
        self.db.add(connection)
        self.db.commit()
        self.db.refresh(connection)
        return connection

    def delete(self, connection: IntegrationConnection) -> None:
        self.db.delete(connection)
        self.db.commit()
