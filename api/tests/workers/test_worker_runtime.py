import uuid

from app.observability.telemetry import get_metrics_snapshot, reset_metrics
from app.storage.models import Job, Project
from app.storage.repositories.job_repository import JobRepository
from app.workers import tasks as worker_tasks


def test_run_job_records_completion_metrics(db_session, monkeypatch):
    reset_metrics()

    project = Project(name="Worker metrics", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    job = Job(
        project_id=project.id,
        job_type="processing",
        status="queued",
        queue_name="processing",
        job_payload={"request_id": "req-worker-1"},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    monkeypatch.setattr(worker_tasks, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(
        worker_tasks,
        "register_worker_tasks",
        lambda: {"processing": lambda _job: {"ok": True, "job_id": str(_job.id)}},
    )

    worker_tasks.run_job(str(job.id))

    db_session.expire_all()
    refreshed = JobRepository(db_session).get(uuid.UUID(str(job.id)))
    assert refreshed is not None
    assert refreshed.status == "completed"
    assert refreshed.attempt_count == 1
    assert refreshed.result_payload == {"ok": True, "job_id": str(job.id)}

    metrics = get_metrics_snapshot()
    assert metrics["job_runs_total"]["processing:completed"] >= 1
