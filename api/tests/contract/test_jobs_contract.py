import uuid
from types import SimpleNamespace

from app.api.routes import jobs as jobs_route_module
from app.storage.models import Job


def test_list_project_jobs_returns_recent_items(client, db_session):
    project = _create_project(client)

    first = Job(
        project_id=uuid.UUID(project["id"]),
        job_type="processing",
        status="completed",
        progress=100,
        queue_name="processing",
    )
    second = Job(
        project_id=uuid.UUID(project["id"]),
        job_type="report_generation",
        status="dead_letter",
        progress=40,
        attempt_count=3,
        max_retries=3,
        queue_name="report",
        error_code="REPORTERROR",
        error_message="Provider timeout",
    )
    db_session.add(first)
    db_session.add(second)
    db_session.commit()

    response = client.get(f"/api/v1/jobs/project/{project['id']}")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 2
    assert {item["status"] for item in payload["items"]} == {"completed", "dead_letter"}


def test_retry_job_rejects_invalid_state(client, db_session):
    project = _create_project(client)

    job = Job(
        project_id=uuid.UUID(project["id"]),
        job_type="processing",
        status="running",
        progress=10,
        queue_name="processing",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    response = client.post(f"/api/v1/jobs/{job.id}/retry")

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "JOB_RETRY_INVALID_STATE"


def test_retry_job_allows_dead_letter_and_requeues(client, db_session, monkeypatch):
    project = _create_project(client)

    job = Job(
        project_id=uuid.UUID(project["id"]),
        job_type="processing",
        status="dead_letter",
        progress=10,
        attempt_count=2,
        max_retries=2,
        queue_name="processing",
        error_code="PROCESSINGERROR",
        error_message="Failed",
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    monkeypatch.setattr(
        jobs_route_module,
        "get_settings",
        lambda: SimpleNamespace(worker_inline_execution=False),
    )

    response = client.post(f"/api/v1/jobs/{job.id}/retry")

    assert response.status_code == 202
    body = response.json()["data"]
    assert body["status"] == "queued"

    db_session.expire_all()
    refreshed = db_session.get(Job, job.id)
    assert refreshed is not None
    assert refreshed.status == "queued"
    assert refreshed.error_code is None
    assert refreshed.error_message is None


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Jobs {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
