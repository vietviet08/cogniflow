from app.services import processing_service
from app.storage.models import Chunk, Document, Job, ProcessingRun, Project, Source


class FakeCollection:
    def __init__(self):
        self.added_ids: list[str] = []
        self.deleted_ids: list[str] = []

    def add(self, ids, documents, embeddings, metadatas):
        self.added_ids.extend(ids)
        assert len(ids) == len(documents) == len(embeddings) == len(metadatas)

    def delete(self, ids):
        self.deleted_ids.extend(ids)


def test_process_sources_persists_run_and_replaces_existing_chunks(
    db_session,
    monkeypatch,
    tmp_path,
):
    project = Project(name="Phase 2", description="processing")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source_path = tmp_path / "notes.txt"
    source_path.write_text(
        "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu.",
        encoding="utf-8",
    )

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="notes.txt",
        storage_path=str(source_path),
        checksum="checksum-source",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    fake_collection = FakeCollection()
    monkeypatch.setattr(
        processing_service,
        "get_retrieval_collection",
        lambda embedding_model: fake_collection,
    )
    monkeypatch.setattr(
        processing_service,
        "embed_texts_with_local_model",
        lambda texts, model_name=None: [[float(index + 1)] * 3 for index, _ in enumerate(texts)],
    )

    first_job = Job(
        project_id=project.id,
        source_id=source.id,
        job_type="processing",
        status="running",
        progress=0,
    )
    db_session.add(first_job)
    db_session.commit()
    db_session.refresh(first_job)

    first_result = processing_service.process_sources(
        db=db_session,
        project_id=project.id,
        job_id=first_job.id,
        sources=[source],
        chunk_size=12,
        chunk_overlap=2,
    )

    first_chunk_ids = [
        chunk.chroma_id for chunk in db_session.query(Chunk).all() if chunk.chroma_id
    ]

    second_job = Job(
        project_id=project.id,
        source_id=source.id,
        job_type="processing",
        status="running",
        progress=0,
    )
    db_session.add(second_job)
    db_session.commit()
    db_session.refresh(second_job)

    second_result = processing_service.process_sources(
        db=db_session,
        project_id=project.id,
        job_id=second_job.id,
        sources=[source],
        chunk_size=12,
        chunk_overlap=2,
    )

    assert first_result["documents_created"] == 1
    assert second_result["documents_created"] == 1
    assert first_result["run_id"] != second_result["run_id"]
    assert db_session.query(Document).count() == 1
    assert db_session.query(Chunk).count() > 0
    assert fake_collection.deleted_ids == first_chunk_ids

    runs = db_session.query(ProcessingRun).order_by(ProcessingRun.created_at.asc()).all()
    assert len(runs) == 2
    assert runs[-1].run_metadata["documents_created"] == 1
    assert runs[-1].run_metadata["chunks_created"] == db_session.query(Chunk).count()


def test_process_pdf_sources_store_page_number_metadata(
    db_session,
    monkeypatch,
    tmp_path,
):
    project = Project(name="PDF pages", description="processing")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source_path = tmp_path / "paper.pdf"
    source_path.write_text("placeholder", encoding="utf-8")

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="paper.pdf",
        storage_path=str(source_path),
        checksum="checksum-pdf",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    fake_collection = FakeCollection()
    monkeypatch.setattr(
        processing_service,
        "get_retrieval_collection",
        lambda embedding_model: fake_collection,
    )
    monkeypatch.setattr(
        processing_service,
        "embed_texts_with_local_model",
        lambda texts, model_name=None: [[float(index + 1)] * 3 for index, _ in enumerate(texts)],
    )
    monkeypatch.setattr(
        processing_service,
        "_extract_pdf_pages",
        lambda path: ["Page one text", "Page two text"],
    )

    job = Job(
        project_id=project.id,
        source_id=source.id,
        job_type="processing",
        status="running",
        progress=0,
    )
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)

    processing_service.process_sources(
        db=db_session,
        project_id=project.id,
        job_id=job.id,
        sources=[source],
        chunk_size=64,
        chunk_overlap=0,
    )

    page_numbers = {
        chunk.chunk_metadata["page_number"] for chunk in db_session.query(Chunk).all()
    }
    assert page_numbers == {1, 2}
