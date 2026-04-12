from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.storage.db import SessionLocal
from app.storage.repositories.job_repository import JobRepository
from app.workers.tasks import run_job

logger = logging.getLogger("app.worker.runtime")


def run_worker_loop() -> None:
    settings = get_settings()
    poll_interval = max(settings.worker_poll_interval_seconds, 0.1)

    logger.info(
        "worker_runtime_started",
        extra={"poll_interval_seconds": poll_interval, "queue_name": settings.worker_queue_name},
    )

    while True:
        job_id: str | None = None
        db = SessionLocal()
        try:
            job = next(
                iter(
                    JobRepository(db).list_queued(
                        limit=1,
                        queue_name=settings.worker_queue_name,
                    )
                ),
                None,
            )
            if job is not None:
                job_id = str(job.id)
        except Exception:
            logger.exception("worker_runtime_poll_failed")
        finally:
            db.close()

        if job_id is None:
            time.sleep(poll_interval)
            continue

        try:
            run_job(job_id)
        except Exception:
            logger.exception("worker_runtime_job_failed", extra={"job_id": job_id})


def main() -> None:
    try:
        run_worker_loop()
    except KeyboardInterrupt:
        logger.info("worker_runtime_stopped")


if __name__ == "__main__":
    main()
