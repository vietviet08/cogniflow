import uuid

from sqlalchemy.orm import Session

from app.storage.models import Report
from app.storage.repositories.base import BaseRepository


class ReportRepository(BaseRepository[Report]):
    def __init__(self, db: Session):
        super().__init__(db)

    def get(self, report_id: uuid.UUID) -> Report | None:
        return self.db.get(Report, report_id)
