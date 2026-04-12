import uuid
from datetime import UTC, datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.storage.models import Job
from app.storage.repositories.base import BaseRepository


class JobRepository(BaseRepository[Job]):
    def __init__(self, db: Session):
        super().__init__(db)

    def get(self, job_id: uuid.UUID) -> Job | None:
        return self.db.get(Job, job_id)

    def list_by_project(self, project_id: uuid.UUID, *, limit: int = 100) -> list[Job]:
        effective_limit = max(1, min(limit, 500))
        return (
            self.db.query(Job)
            .filter(Job.project_id == project_id)
            .order_by(Job.created_at.desc())
            .limit(effective_limit)
            .all()
        )

    def list_queued(self, *, limit: int = 1, queue_name: str | None = None) -> list[Job]:
        effective_limit = max(1, min(limit, 100))
        query = self.db.query(Job).filter(and_(Job.status == "queued"))
        if queue_name:
            query = query.filter(Job.queue_name == queue_name)
        return query.order_by(Job.created_at.asc()).limit(effective_limit).all()

    def create(
        self,
        project_id: uuid.UUID,
        job_type: str,
        status: str,
        source_id: uuid.UUID | None = None,
        progress: int = 0,
        queue_name: str | None = None,
        max_retries: int = 3,
        job_payload: dict | None = None,
        idempotency_key: str | None = None,
    ) -> Job:
        job = Job(
            project_id=project_id,
            source_id=source_id,
            job_type=job_type,
            status=status,
            progress=progress,
            queue_name=queue_name,
            max_retries=max_retries,
            job_payload=job_payload,
            idempotency_key=idempotency_key,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def update_status(
        self,
        job: Job,
        status: str,
        progress: int | None = None,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        result_payload: dict | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> Job:
        job.status = status
        if progress is not None:
            job.progress = progress
        if error_code is not None:
            job.error_code = error_code
        if error_message is not None:
            job.error_message = error_message
        if result_payload is not None:
            job.result_payload = result_payload
        if started_at is not None:
            job.started_at = started_at
        if finished_at is not None:
            job.finished_at = finished_at
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_running(self, job: Job) -> Job:
        job.attempt_count += 1
        job.status = "running"
        job.started_at = datetime.now(UTC)
        job.finished_at = None
        job.error_code = None
        job.error_message = None
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_completed(self, job: Job, *, result_payload: dict | None = None) -> Job:
        return self.update_status(
            job,
            status="completed",
            progress=100,
            result_payload=result_payload,
            finished_at=datetime.now(UTC),
        )

    def mark_failed(self, job: Job, *, code: str, message: str) -> Job:
        return self.update_status(
            job,
            status="failed",
            error_code=code,
            error_message=message,
            finished_at=datetime.now(UTC),
        )

    def mark_dead_letter(self, job: Job, *, code: str, message: str) -> Job:
        return self.update_status(
            job,
            status="dead_letter",
            error_code=code,
            error_message=message,
            finished_at=datetime.now(UTC),
        )

    def mark_cancelled(self, job: Job) -> Job:
        return self.update_status(
            job,
            status="cancelled",
            finished_at=datetime.now(UTC),
        )

    def has_retry_budget(self, job: Job) -> bool:
        return job.attempt_count < max(job.max_retries, 0)

    def request_cancellation(self, job: Job) -> Job:
        job.cancel_requested_at = datetime.now(UTC)
        if job.status == "queued":
            job.status = "cancelled"
            job.finished_at = datetime.now(UTC)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def queue_retry(self, job: Job) -> Job:
        job.status = "queued"
        job.progress = 0
        job.error_code = None
        job.error_message = None
        job.finished_at = None
        job.cancel_requested_at = None
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job
