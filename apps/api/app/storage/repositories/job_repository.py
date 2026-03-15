import uuid

from sqlalchemy.orm import Session

from app.storage.models import Job
from app.storage.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    def __init__(self, db: Session):
        super().__init__(db)

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.get(Job, job_id)
