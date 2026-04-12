import uuid

from sqlalchemy.orm import Session

from app.storage.models import Source
from app.storage.repositories.base import BaseRepository


class SourceRepository(BaseRepository[Source]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(
        self,
        project_id: uuid.UUID,
        source_type: str,
        original_uri: str | None,
        storage_path: str | None = None,
        checksum: str | None = None,
        source_metadata: dict | None = None,
        status: str = "queued",
    ) -> Source:
        source = Source(
            project_id=project_id,
            type=source_type,
            original_uri=original_uri,
            storage_path=storage_path,
            checksum=checksum,
            source_metadata=source_metadata,
            status=status,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def get(self, source_id: uuid.UUID) -> Source | None:
        return self.db.get(Source, source_id)

    def list_by_project(self, project_id: uuid.UUID) -> list[Source]:
        return list(
            self.db.query(Source)
            .filter(Source.project_id == project_id)
            .order_by(Source.created_at.asc())
        )

    def list_by_ids(self, project_id: uuid.UUID, source_ids: list[uuid.UUID]) -> list[Source]:
        if not source_ids:
            return []

        return list(
            self.db.query(Source)
            .filter(Source.project_id == project_id, Source.id.in_(source_ids))
            .order_by(Source.created_at.asc())
        )

    def find_by_checksum(
        self,
        *,
        project_id: uuid.UUID,
        checksum: str,
        exclude_source_id: uuid.UUID | None = None,
    ) -> Source | None:
        query = self.db.query(Source).filter(
            Source.project_id == project_id,
            Source.checksum == checksum,
        )
        if exclude_source_id is not None:
            query = query.filter(Source.id != exclude_source_id)
        return query.order_by(Source.created_at.desc()).first()

    def next_version(
        self,
        *,
        project_id: uuid.UUID,
        original_uri: str | None,
        exclude_source_id: uuid.UUID | None = None,
    ) -> int:
        if not original_uri:
            return 1
        query = self.db.query(Source).filter(
            Source.project_id == project_id,
            Source.original_uri == original_uri,
        )
        if exclude_source_id is not None:
            query = query.filter(Source.id != exclude_source_id)

        latest = query.order_by(Source.created_at.desc()).first()
        if latest is None:
            return 1
        metadata = latest.source_metadata if isinstance(latest.source_metadata, dict) else {}
        try:
            previous_version = int(metadata.get("version", 1))
        except (TypeError, ValueError):
            previous_version = 1
        return max(previous_version + 1, 1)
