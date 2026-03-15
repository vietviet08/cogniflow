import uuid

from sqlalchemy.orm import Session

from app.storage.models import Source
from app.storage.repositories.base import BaseRepository


class SourceRepository(BaseRepository[Source]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create_url_source(self, project_id: uuid.UUID, url: str) -> Source:
        source = Source(project_id=project_id, type="url", original_uri=url, status="queued")
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source
