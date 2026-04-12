import uuid

from app.api.routes import processing as processing_route_module
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.source_repository import SourceRepository


def test_start_processing_queues_worker_job(client, db_session, monkeypatch):
    project = _create_project(client)
    source_repo = SourceRepository(db_session)
    file_source = source_repo.create(
        project_id=uuid.UUID(project["id"]),
        source_type="file",
        original_uri="paper.pdf",
        storage_path="data/uploads/paper.pdf",
        checksum="checksum-1",
        status="completed",
    )
    url_source = source_repo.create(
        project_id=uuid.UUID(project["id"]),
        source_type="arxiv",
        original_uri="https://arxiv.org/abs/1234.5678",
        storage_path="data/uploads/source.json",
        checksum="checksum-2",
        status="completed",
    )

    scheduled_jobs: list[str] = []
    monkeypatch.setattr(
        processing_route_module,
        "run_job",
        lambda job_id: scheduled_jobs.append(job_id),
    )

    response = client.post(
        "/api/v1/jobs/processing",
        json={
            "project_id": project["id"],
            "source_ids": [str(file_source.id), str(url_source.id)],
            "options": {"chunk_size": 800, "chunk_overlap": 120},
        },
    )

    assert response.status_code == 202
    body = response.json()

    assert body["data"]["status"] == "queued"
    assert "job_id" in body["data"]
    assert scheduled_jobs == [body["data"]["job_id"]]

    job = JobRepository(db_session).get(uuid.UUID(body["data"]["job_id"]))
    assert job is not None
    assert job.queue_name == "processing"
    assert job.job_payload["source_ids"] == [str(file_source.id), str(url_source.id)]


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Processing {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
