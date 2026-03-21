import uuid

from app.api.routes import processing as processing_route_module
from app.storage.repositories.source_repository import SourceRepository


def test_start_processing_returns_completed_job_with_counts(client, db_session, monkeypatch):
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

    def fake_process_sources(db, sources, chunk_size, chunk_overlap):
        assert len(sources) == 2
        assert chunk_size == 800
        assert chunk_overlap == 120
        return {"documents_created": 2, "chunks_created": 6}

    monkeypatch.setattr(processing_route_module, "process_sources", fake_process_sources)

    response = client.post(
        "/api/v1/jobs/processing",
        json={
            "project_id": project["id"],
            "source_ids": [str(file_source.id), str(url_source.id)],
            "options": {"chunk_size": 800, "chunk_overlap": 120},
        },
    )

    assert response.status_code == 201
    body = response.json()

    assert body["data"]["status"] == "completed"
    assert body["data"]["documents_created"] == 2
    assert body["data"]["chunks_created"] == 6
    assert "job_id" in body["data"]


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Processing {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
