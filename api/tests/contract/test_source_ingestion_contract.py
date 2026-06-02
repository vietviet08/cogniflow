import io
import uuid
from types import SimpleNamespace

from app.api.routes import sources as sources_route_module
from app.storage.models import AuditLog, Chunk, Document, Job, Source


def test_upload_file_source_persists_metadata(client, db_session, monkeypatch, tmp_path):
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

    source = db_session.get(Source, uuid.UUID(body["data"]["source_id"]))
    assert source.source_metadata["source_quality"]["parser"] == "pdf_text"
    assert source.source_metadata["retrieval_filters"]["tags"] == ["upload", "pdf"]


def test_upload_pptx_source_persists_supported_metadata(client, db_session, monkeypatch, tmp_path):
    project = _create_project(client)

    def fake_save_uploaded_file(source_id, upload):
        target = tmp_path / f"{source_id}.pptx"
        target.write_bytes(upload.file.read())
        return str(target), "checksum-pptx"

    monkeypatch.setattr(sources_route_module, "save_uploaded_file", fake_save_uploaded_file)

    response = client.post(
        "/api/v1/sources/files",
        data={"project_id": project["id"]},
        files={
            "file": (
                "slides.pptx",
                io.BytesIO(b"pptx placeholder"),
                "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    source = db_session.get(Source, uuid.UUID(body["data"]["source_id"]))
    assert source.source_metadata["source_quality"]["parser"] == "pptx_text"
    assert source.source_metadata["retrieval_filters"]["tags"] == ["upload", "pptx"]


def test_upload_unsupported_file_source_is_rejected(client, db_session):
    project = _create_project(client)

    response = client.post(
        "/api/v1/sources/files",
        data={"project_id": project["id"]},
        files={"file": ("archive.zip", io.BytesIO(b"zip"), "application/zip")},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "UNSUPPORTED_FILE_FORMAT"
    assert ".pptx" in body["error"]["details"]["supported_extensions"]
    assert db_session.query(Source).filter(Source.original_uri == "archive.zip").count() == 0


def test_get_source_artifact_streams_s3_pdf_without_redirect(client, db_session, monkeypatch):
    project = _create_project(client)
    source = Source(
        project_id=uuid.UUID(project["id"]),
        type="file",
        original_uri="source.pdf",
        storage_path="s3://bucket/sources/source-id/source.pdf",
        checksum="s3-pdf",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    class FakeS3Storage:
        def exists(self, storage_path):
            return storage_path == source.storage_path

        def get_stream(self, storage_path, chunk_size=8192):
            yield b"%PDF-1.4 fake"

    monkeypatch.setattr(sources_route_module, "get_storage_backend", lambda: FakeS3Storage())

    response = client.get(f"/api/v1/sources/{source.id}/artifact")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert "location" not in response.headers
    assert response.content == b"%PDF-1.4 fake"


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
        return (
            str(target),
            "checksum-url",
            "arxiv",
            {
                "provider": "arxiv",
                "external_url": "https://arxiv.org/abs/1234.5678",
                "source_quality": {
                    "parser": "arxiv_atom",
                    "parser_warnings": [],
                    "ocr_confidence": None,
                    "freshness_score": 0.8,
                    "trust_score": 0.9,
                },
                "retrieval_filters": {
                    "author": "Ada Lovelace",
                    "published_at": "2026-01-01T00:00:00Z",
                    "language": "en",
                    "tags": ["arxiv"],
                },
            },
        )

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

    list_response = client.get(f"/api/v1/sources/project/{project['id']}")
    assert list_response.status_code == 200
    item = list_response.json()["data"]["items"][0]
    assert item["quality"]["trust_score"] == 0.9
    assert item["retrieval_filters"]["author"] == "Ada Lovelace"
    assert item["indexing"] == {
        "document_count": 0,
        "chunk_count": 0,
        "is_indexed": False,
    }


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

    job = Job(
        project_id=project_id,
        source_id=source.id,
        job_type="process_sources",
        status="completed",
        progress=100,
        job_payload={"source_ids": [str(source.id)]},
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    source_id = source.id
    document_id = document.id
    chunk_id = chunk.id
    job_id = job.id

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
    assert db_session.get(Job, job_id).source_id is None

    audit = db_session.query(AuditLog).filter(AuditLog.action == "source.delete").one()
    assert audit.target_id == str(source_id)
    assert audit.payload["documents_deleted"] == 1
    assert audit.payload["chunks_deleted"] == 1
    assert audit.payload["jobs_detached"] == 1
    assert audit.payload["artifact_delete"]["deleted"] is True


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Phase 1 {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
