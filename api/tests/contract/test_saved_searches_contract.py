import uuid
from types import SimpleNamespace

from app.api.routes import saved_searches as saved_searches_route_module
from app.storage.models import Job, SavedSearch


def test_saved_search_can_be_created_listed_and_run(client, db_session, monkeypatch):
    project = _create_project(client)

    monkeypatch.setattr(
        saved_searches_route_module,
        "get_settings",
        lambda: SimpleNamespace(worker_inline_execution=False),
    )

    create_response = client.post(
        f"/api/v1/projects/{project['id']}/saved-searches",
        json={
            "name": "Weekly pricing changes",
            "query": "What changed in pricing this week?",
            "filters": {"language": "en", "tags": ["pricing"]},
            "report_type": "executive_brief",
            "provider": "openai",
            "schedule_interval_minutes": 10080,
        },
    )

    assert create_response.status_code == 201
    saved_search = create_response.json()["data"]
    assert saved_search["name"] == "Weekly pricing changes"
    assert saved_search["filters"]["tags"] == ["pricing"]
    assert saved_search["schedule_interval_minutes"] == 10080

    list_response = client.get(f"/api/v1/projects/{project['id']}/saved-searches")
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1

    run_response = client.post(
        f"/api/v1/projects/{project['id']}/saved-searches/{saved_search['saved_search_id']}/run"
    )

    assert run_response.status_code == 202
    body = run_response.json()["data"]
    assert body["status"] == "queued"
    assert body["saved_search"]["last_run_at"] is not None

    job = db_session.get(Job, uuid.UUID(body["job_id"]))
    assert job is not None
    assert job.job_type == "report_generation"
    assert job.job_payload["saved_search_id"] == saved_search["saved_search_id"]
    assert job.job_payload["query"] == "What changed in pricing this week?"
    assert job.job_payload["filters"]["tags"] == ["pricing"]

    row = db_session.get(SavedSearch, uuid.UUID(saved_search["saved_search_id"]))
    assert row is not None
    assert row.last_run_at is not None


def test_saved_search_rejects_too_frequent_schedule(client):
    project = _create_project(client)

    response = client.post(
        f"/api/v1/projects/{project['id']}/saved-searches",
        json={
            "name": "Too frequent",
            "query": "What changed?",
            "schedule_interval_minutes": 5,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "SAVED_SEARCH_SCHEDULE_INVALID"


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Saved Search {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
