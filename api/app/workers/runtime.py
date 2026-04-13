from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.services.intelligence_service import enqueue_due_monitoring_jobs
from app.storage.db import SessionLocal
from app.storage.repositories.job_repository import JobRepository
from app.workers.tasks import run_job

logger = logging.getLogger("app.worker.runtime")


def run_worker_loop() -> None:
    settings = get_settings()
    poll_interval = max(settings.worker_poll_interval_seconds, 0.1)
    autoschedule_interval = max(settings.intelligence_autoschedule_interval_seconds, poll_interval)
    next_autoschedule_at = datetime.now(UTC)

    logger.info(
        "worker_runtime_started",
        extra={"poll_interval_seconds": poll_interval, "queue_name": settings.worker_queue_name},
    )

    while True:
        job_id: str | None = None
        db = SessionLocal()
        try:
            now = datetime.now(UTC)
            if settings.intelligence_autoschedule_enabled and now >= next_autoschedule_at:
                autoschedule_result = enqueue_due_monitoring_jobs(
                    db,
                    queue_name=settings.intelligence_monitoring_queue_name,
                    alert_threshold=settings.intelligence_default_alert_threshold,
                    limit_projects=settings.intelligence_autoschedule_batch_size,
                )
                if autoschedule_result["queued_jobs"] > 0:
                    logger.info(
                        "worker_runtime_autoscheduled_monitoring",
                        extra=autoschedule_result,
                    )
                next_autoschedule_at = now + timedelta(seconds=autoschedule_interval)

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
