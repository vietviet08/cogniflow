import uuid

from app.services.citation_service import hydrate_citations
from app.storage.models import Chunk, Document, Project, Source


def test_hydrate_citations_infers_pdf_page_number_for_legacy_chunks(
    db_session,
    monkeypatch,
    tmp_path,
):
    project = Project(name="Citation hydration", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source_path = tmp_path / "resume.pdf"
    source_path.write_text("placeholder", encoding="utf-8")

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="resume.pdf",
        storage_path=str(source_path),
        checksum="resume-pdf",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Resume",
        raw_path=str(source_path),
        clean_text="Experience and education",
        token_count=3,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=0,
        content="Led platform migration and improved release reliability across teams.",
        chroma_id=str(uuid.uuid4()),
        embedding_model="local-test-model",
        chunk_metadata={},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    monkeypatch.setattr(
        "app.services.citation_service._load_pdf_pages",
        lambda path: (
            "Profile summary",
            "Led platform migration and improved release reliability across teams.",
        ),
    )

    citations = hydrate_citations(
        db_session,
        [
            {
                "citation_id": str(chunk.id),
                "source_id": str(source.id),
                "source_type": "file",
                "document_id": str(document.id),
                "chunk_id": str(chunk.id),
                "title": "resume.pdf",
                "url": "",
                "page_number": None,
            }
        ],
    )

    assert citations[0]["page_number"] == 2
    assert citations[0]["quote"] == chunk.content

    db_session.refresh(chunk)
    assert chunk.chunk_metadata["page_number"] == 2
    assert chunk.chunk_metadata["quote"] == chunk.content
