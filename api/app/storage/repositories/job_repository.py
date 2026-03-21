import uuid

from sqlalchemy.orm import Session

from app.storage.models import Job
from app.storage.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    def __init__(self, db: Session):
        super().__init__(db)

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.get(Job, job_id)

    def create(
        self,
        project_id: uuid.UUID,
        job_type: str,
        status: str,
        source_id: uuid.UUID | None = None,
        progress: int = 0,
    ) -> Job:
        job = Job(
            project_id=project_id,
            source_id=source_id,
            job_type=job_type,
            status=status,
            progress=progress,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_status(self, job: Job, status: str, progress: int | None = None) -> Job:
        job.status = status
        if progress is not None:
            job.progress = progress
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
