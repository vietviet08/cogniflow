import uuid
from types import SimpleNamespace

from app.api.routes import runs as runs_route_module
from app.storage.models import Job, ProcessingRun


def test_replay_processing_run_queues_worker_job(client, db_session, monkeypatch):
    project = _create_project(client)
    source_id = str(uuid.uuid4())
    run = ProcessingRun(
        project_id=uuid.UUID(project["id"]),
        run_type="processing",
        model_id="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        config_hash="config-a",
        run_metadata={
            "source_ids": [source_id],
            "chunk_size": 800,
            "chunk_overlap": 120,
        },
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    monkeypatch.setattr(
        runs_route_module,
        "get_settings",
        lambda: SimpleNamespace(worker_inline_execution=False),
    )

    response = client.post(f"/api/v1/runs/{run.id}/replay")

    assert response.status_code == 202
    body = response.json()["data"]
    assert body["status"] == "queued"
    assert body["run_id"] == str(run.id)
    assert body["run_type"] == "processing"

    job = db_session.get(Job, uuid.UUID(body["job_id"]))
    assert job is not None
    assert job.job_type == "processing"
    assert job.queue_name == "processing"
    assert job.job_payload["source_ids"] == [source_id]
    assert job.job_payload["replay_of_run_id"] == str(run.id)


def test_replay_report_run_queues_report_job(client, db_session, monkeypatch):
    project = _create_project(client)
    run = ProcessingRun(
        project_id=uuid.UUID(project["id"]),
        run_type="report",
        model_id="gpt-4o",
        prompt_hash="prompt-a",
        config_hash="config-a",
        run_metadata={
            "query": "What should the team do next?",
            "provider": "openai",
            "report_type": "action_items",
            "format": "markdown",
        },
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    monkeypatch.setattr(
        runs_route_module,
        "get_settings",
        lambda: SimpleNamespace(worker_inline_execution=False),
    )

    response = client.post(f"/api/v1/runs/{run.id}/replay")

    assert response.status_code == 202
    body = response.json()["data"]
    job = db_session.get(Job, uuid.UUID(body["job_id"]))
    assert job is not None
    assert job.job_type == "report_generation"
    assert job.queue_name == "report"
    assert job.job_payload["query"] == "What should the team do next?"
    assert job.job_payload["type"] == "action_items"
    assert job.job_payload["replay_of_run_id"] == str(run.id)


def test_compare_runs_returns_changed_fields(client, db_session):
    project = _create_project(client)
    left = ProcessingRun(
        project_id=uuid.UUID(project["id"]),
        run_type="report",
        model_id="gpt-4o",
        prompt_hash="prompt-a",
        config_hash="config-a",
        retrieval_config={"top_k": 5},
        run_metadata={"query": "Q", "provider": "openai", "format": "markdown"},
    )
    right = ProcessingRun(
        project_id=uuid.UUID(project["id"]),
        run_type="report",
        model_id="gpt-4.1-mini",
        prompt_hash="prompt-a",
        config_hash="config-b",
        retrieval_config={"top_k": 8},
        run_metadata={"query": "Q", "provider": "openai", "format": "json"},
    )
    db_session.add(left)
    db_session.add(right)
    db_session.commit()
    db_session.refresh(left)
    db_session.refresh(right)

    response = client.get(f"/api/v1/runs/{left.id}/compare/{right.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["same_project"] is True
    assert data["same_run_type"] is True
    assert data["diff"]["model_changed"] is True
    assert data["diff"]["config_changed"] is True
    assert data["diff"]["retrieval_config_changed"] is True
    assert data["diff"]["metadata_changed"] == ["format"]


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Runs {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
