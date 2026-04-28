import io
import uuid
from types import SimpleNamespace

from app.api.routes import sources as sources_route_module
from app.storage.models import AuditLog, Chunk, Document, Source


def test_upload_file_source_persists_metadata(client, monkeypatch, tmp_path):
    project = _create_project(client)

    def fake_save_uploaded_file(source_id, upload):
        target = tmp_path / f"{source_id}.pdf"
        target.write_bytes(upload.file.read())
        return str(target), "checksum-file"

    monkeypatch.setattr(sources_route_module, "save_uploaded_file", fake_save_uploaded_file)

    response = client.post(
        "/api/v1/sources/files",
        data={"project_id": project["id"]},
        files={"file": ("paper.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
    )

    assert response.status_code == 201
    body = response.json()

    assert body["data"]["status"] == "completed"
    assert body["data"]["source_type"] == "file"
    assert body["data"]["filename"] == "paper.pdf"
    assert body["data"]["source_version"] == 1
    assert body["data"]["duplicate_of_source_id"] is None
    assert "source_id" in body["data"]
    assert "job_id" in body["data"]


def test_ingest_url_source_handles_arxiv_payload(client, monkeypatch, tmp_path):
    project = _create_project(client)

    def fake_ingest_remote_source(source_id, url):
        target = tmp_path / f"{source_id}.json"
        target.write_text(
            (
                '{"title":"Paper A","content":"Abstract text","source":"arxiv",'
                '"url":"https://arxiv.org/abs/1234.5678"}'
            ),
            encoding="utf-8",
        )
        return str(target), "checksum-url", "arxiv"

    monkeypatch.setattr(sources_route_module, "ingest_remote_source", fake_ingest_remote_source)

    response = client.post(
        "/api/v1/sources/urls",
        json={"project_id": project["id"], "url": "https://arxiv.org/abs/1234.5678"},
    )

    assert response.status_code == 201
    body = response.json()

    assert body["data"]["status"] == "completed"
    assert body["data"]["source_type"] == "arxiv"
    assert body["data"]["source_version"] == 1
    assert body["data"]["duplicate_of_source_id"] is None
    assert "source_id" in body["data"]
    assert "job_id" in body["data"]


def test_upload_file_source_tracks_version_and_duplicate(client, monkeypatch, tmp_path):
    project = _create_project(client)

    def fake_save_uploaded_file(source_id, upload):
        target = tmp_path / f"{source_id}.pdf"
        target.write_bytes(upload.file.read())
        return str(target), "checksum-shared"

    monkeypatch.setattr(sources_route_module, "save_uploaded_file", fake_save_uploaded_file)

    first_response = client.post(
        "/api/v1/sources/files",
        data={"project_id": project["id"]},
        files={"file": ("paper.pdf", io.BytesIO(b"first"), "application/pdf")},
    )
    assert first_response.status_code == 201
    first_body = first_response.json()["data"]

    second_response = client.post(
        "/api/v1/sources/files",
        data={"project_id": project["id"]},
        files={"file": ("paper.pdf", io.BytesIO(b"second"), "application/pdf")},
    )
    assert second_response.status_code == 201
    second_body = second_response.json()["data"]

    assert first_body["source_version"] == 1
    assert second_body["source_version"] == 2
    assert second_body["duplicate_of_source_id"] == first_body["source_id"]


def test_bulk_delete_sources_removes_graph_and_writes_audit(client, db_session, monkeypatch, tmp_path):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])
    artifact = tmp_path / "source.pdf"
    artifact.write_bytes(b"%PDF-1.4 fake")

    source = Source(
        project_id=project_id,
        type="file",
        original_uri="source.pdf",
        storage_path=str(artifact),
        checksum="delete-me",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Source",
        raw_path=str(artifact),
        clean_text="delete this evidence",
        token_count=3,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="delete this evidence",
        chroma_id="chunk-delete-me",
        embedding_model="local-test-model",
        chunk_metadata={},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)
    source_id = source.id
    document_id = document.id
    chunk_id = chunk.id

    deleted_vector_ids: list[str] = []

    class FakeCollection:
        def delete(self, ids):
            deleted_vector_ids.extend(ids)

    monkeypatch.setattr(
        sources_route_module,
        "get_settings",
        lambda: SimpleNamespace(upload_dir=str(tmp_path)),
    )
    monkeypatch.setattr(
        sources_route_module,
        "get_retrieval_collection",
        lambda embedding_model: FakeCollection(),
    )

    response = client.request(
        "DELETE",
        "/api/v1/sources/bulk",
        json={"source_ids": [str(source.id)]},
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["deleted_count"] == 1
    assert deleted_vector_ids == ["chunk-delete-me"]
    assert not artifact.exists()
    db_session.expire_all()
    assert db_session.get(Source, source_id) is None
    assert db_session.get(Document, document_id) is None
    assert db_session.get(Chunk, chunk_id) is None

    audit = db_session.query(AuditLog).filter(AuditLog.action == "source.delete").one()
    assert audit.target_id == str(source_id)
    assert audit.payload["documents_deleted"] == 1
    assert audit.payload["chunks_deleted"] == 1
    assert audit.payload["artifact_delete"]["deleted"] is True


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Phase 1 {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
