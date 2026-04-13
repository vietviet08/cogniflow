from datetime import UTC, datetime, timedelta

from app.services.intelligence_service import enqueue_due_monitoring_jobs
from app.storage.models import Job, Project, RadarSource


def test_enqueue_due_monitoring_jobs_queues_due_project_once(db_session):
    project = Project(name="Radar Autoschedule", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source_a = RadarSource(
        project_id=project.id,
        name="Source A",
        source_url="https://example.com/a",
        category="general",
        poll_interval_minutes=30,
        is_active=True,
        last_checked_at=None,
    )
    source_b = RadarSource(
        project_id=project.id,
        name="Source B",
        source_url="https://example.com/b",
        category="general",
        poll_interval_minutes=30,
        is_active=True,
        last_checked_at=datetime.now(UTC) - timedelta(hours=1),
    )
    db_session.add(source_a)
    db_session.add(source_b)
    db_session.commit()

    first = enqueue_due_monitoring_jobs(
        db_session,
        queue_name="monitoring",
        alert_threshold="high",
        limit_projects=10,
    )
    assert first["queued_jobs"] == 1

    jobs = db_session.query(Job).filter(Job.project_id == project.id).all()
    assert len(jobs) == 1
    assert jobs[0].job_type == "intelligence_monitoring"
    assert jobs[0].queue_name == "monitoring"
    assert jobs[0].job_payload is not None
    assert len(jobs[0].job_payload.get("source_ids", [])) == 2

    second = enqueue_due_monitoring_jobs(
        db_session,
        queue_name="monitoring",
        alert_threshold="high",
        limit_projects=10,
    )
    assert second["queued_jobs"] == 0
