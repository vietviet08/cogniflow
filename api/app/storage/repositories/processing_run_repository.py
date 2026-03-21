import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.storage.models import ProcessingRun
from app.storage.repositories.base import BaseRepository


class ProcessingRunRepository(BaseRepository[ProcessingRun]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(
        self,
        project_id: uuid.UUID,
        job_id: uuid.UUID | None,
        run_type: str,
        model_id: str | None,
        prompt_hash: str | None,
        config_hash: str | None,
        retrieval_config: dict | None,
        run_metadata: dict | None,
        parent_run_id: uuid.UUID | None = None,
    ) -> ProcessingRun:
        run = ProcessingRun(
            project_id=project_id,
            job_id=job_id,
            run_type=run_type,
            model_id=model_id,
            prompt_hash=prompt_hash,
            config_hash=config_hash,
            retrieval_config=retrieval_config,
            run_metadata=run_metadata,
            parent_run_id=parent_run_id,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def update_metadata(self, run: ProcessingRun, run_metadata: dict | None) -> ProcessingRun:
        run.run_metadata = run_metadata
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def list_by_project(self, project_id: uuid.UUID) -> list[ProcessingRun]:
        return (
            self.db.query(ProcessingRun)
            .filter(ProcessingRun.project_id == project_id)
            .order_by(desc(ProcessingRun.created_at))
            .all()
        )
