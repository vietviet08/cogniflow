import uuid

from app.services.embedding_service import LOCAL_EMBEDDING_MODEL
from app.storage.models import Chunk, Document, Job, ProcessingRun, Report, Source


def test_list_project_documents_returns_processed_inventory(client, db_session):
    project = _create_project(client)
    source, document, _, _ = _seed_processed_artifacts(db_session, uuid.UUID(project["id"]))

    response = client.get(f"/api/v1/projects/{project['id']}/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert item["document_id"] == str(document.id)
    assert item["source_id"] == str(source.id)
    assert item["chunk_count"] == 1
    assert item["source_type"] == "file"


def test_list_project_chunks_supports_document_filter(client, db_session):
    project = _create_project(client)
    source, document, chunk, _ = _seed_processed_artifacts(db_session, uuid.UUID(project["id"]))

    response = client.get(
        f"/api/v1/projects/{project['id']}/chunks",
        params={"document_id": str(document.id)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert item["chunk_id"] == str(chunk.id)
    assert item["document_id"] == str(document.id)
    assert item["source_id"] == str(source.id)
    assert item["metadata"]["source_id"] == str(source.id)


def test_list_processing_runs_returns_reproducibility_metadata(client, db_session):
    project = _create_project(client)
    _, _, _, run = _seed_processed_artifacts(db_session, uuid.UUID(project["id"]))

    response = client.get(f"/api/v1/projects/{project['id']}/processing-runs")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["total"] == 1
    item = body["data"]["items"][0]
    assert item["run_id"] == str(run.id)
    assert item["run_type"] == "processing"
    assert item["model_id"] == LOCAL_EMBEDDING_MODEL
    assert item["run_metadata"]["chunks_created"] == 1


def test_list_project_reports_includes_run_id_for_diff_view(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])
    run = ProcessingRun(
        project_id=project_id,
        run_type="report",
        model_id="gpt-test",
        config_hash="config-a",
        run_metadata={"query": "What changed?"},
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    report = Report(
        project_id=project_id,
        query="What changed?",
        title="Research Brief: Change",
        report_type="research_brief",
        format="markdown",
        content="# Change",
        structured_payload={},
        status="completed",
        run_id=run.id,
    )
    db_session.add(report)
    db_session.commit()

    response = client.get(f"/api/v1/projects/{project['id']}/reports")

    assert response.status_code == 200
    item = response.json()["data"]["items"][0]
    assert item["report_id"] == str(report.id)
    assert item["run_id"] == str(run.id)


def _seed_processed_artifacts(db_session, project_id):
    source = Source(
        project_id=project_id,
        type="file",
        original_uri="paper.pdf",
        storage_path="data/uploads/paper.pdf",
        checksum="checksum-1",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Paper A",
        raw_path=source.storage_path,
        clean_text="Clean text",
        token_count=42,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="chunk text",
        chroma_id=str(uuid.uuid4()),
        embedding_model=LOCAL_EMBEDDING_MODEL,
        chunk_metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    db_session.add(chunk)

    job = Job(
        project_id=project_id,
        source_id=source.id,
        job_type="processing",
        status="completed",
        progress=100,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    run = ProcessingRun(
        project_id=project_id,
        job_id=job.id,
        run_type="processing",
        model_id=LOCAL_EMBEDDING_MODEL,
        config_hash="config-hash",
        run_metadata={"documents_created": 1, "chunks_created": 1},
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    return source, document, chunk, run


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Inventory {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
