import io
import uuid

from app.api.routes import sources as sources_route_module


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
    assert "source_id" in body["data"]
    assert "job_id" in body["data"]


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Phase 1 {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
