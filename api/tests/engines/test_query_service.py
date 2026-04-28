from app.services import query_service
from app.services.embedding_service import LOCAL_EMBEDDING_MODEL, LOCAL_EMBEDDING_PROVIDER


def test_search_knowledge_base_surfaces_local_embedding_failure(monkeypatch):
    monkeypatch.setattr(query_service, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        query_service,
        "resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
        },
    )

    def fake_embed_texts_with_local_model(texts, model_name=LOCAL_EMBEDDING_MODEL):
        raise RuntimeError("model files are missing")

    monkeypatch.setattr(
        query_service,
        "embed_texts_with_local_model",
        fake_embed_texts_with_local_model,
    )

    try:
        query_service.search_knowledge_base(
            db=None,
            project_id="project-1",
            query="What happened?",
            provider="openai",
            top_k=5,
        )
        raise AssertionError("Expected QueryError")
    except query_service.QueryError as exc:
        assert exc.code == "QUERY_RETRIEVAL_ERROR"
        assert exc.status_code == 503
        assert exc.details["provider"] == LOCAL_EMBEDDING_PROVIDER
        assert exc.details["stage"] == "retrieval"
        assert exc.details["model"] == LOCAL_EMBEDDING_MODEL


def test_search_knowledge_base_requires_reindex_for_old_embedding_chunks(
    db_session,
    monkeypatch,
):
    from app.storage.models import Chunk, Document, Project, Source

    project = Project(name="Legacy vectors", description="reindex")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="legacy.txt",
        storage_path="/tmp/legacy.txt",
        checksum="legacy",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Legacy",
        raw_path="/tmp/legacy.txt",
        clean_text="legacy content",
        token_count=2,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="legacy content",
        chroma_id="legacy-chunk",
        embedding_model="text-embedding-3-small",
        chunk_metadata={},
    )
    db_session.add(chunk)
    db_session.commit()

    class FakeCollection:
        def query(self, query_embeddings, n_results, where):
            return {"documents": [[]], "metadatas": [[]], "ids": [[]]}

    monkeypatch.setattr(query_service, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        query_service,
        "resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
        },
    )
    monkeypatch.setattr(
        query_service,
        "embed_texts_with_local_model",
        lambda texts, model_name=LOCAL_EMBEDDING_MODEL: [[0.1, 0.2, 0.3]],
    )
    monkeypatch.setattr(
        query_service,
        "get_retrieval_collection",
        lambda embedding_model: FakeCollection(),
    )

    try:
        query_service.search_knowledge_base(
            db=db_session,
            project_id=project.id,
            query="What happened?",
            provider="openai",
            top_k=5,
        )
        raise AssertionError("Expected QueryError")
    except query_service.QueryError as exc:
        assert exc.code == "QUERY_REINDEX_REQUIRED"
        assert exc.status_code == 409
        assert exc.details["provider"] == LOCAL_EMBEDDING_PROVIDER
        assert exc.details["model"] == LOCAL_EMBEDDING_MODEL


def test_hybrid_retrieval_fuses_semantic_and_lexical_candidates(db_session, monkeypatch):
    from app.storage.models import Chunk, Document, Project, Source

    project = Project(name="Hybrid retrieval", description="rrf")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="pricing-notes.txt",
        storage_path="/tmp/pricing-notes.txt",
        checksum="hybrid",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Pricing Notes",
        raw_path="/tmp/pricing-notes.txt",
        clean_text="Competitor pricing changed. Enterprise discount language moved.",
        token_count=8,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    lexical_chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="Competitor pricing changed for enterprise discount tiers.",
        chroma_id="lexical-chunk",
        embedding_model=LOCAL_EMBEDDING_MODEL,
        chunk_metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    semantic_chunk = Chunk(
        document_id=document.id,
        chunk_index=1,
        content="Packaging language was updated for annual plans.",
        chroma_id="semantic-chunk",
        embedding_model=LOCAL_EMBEDDING_MODEL,
        chunk_metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    db_session.add_all([lexical_chunk, semantic_chunk])
    db_session.commit()
    db_session.refresh(lexical_chunk)
    db_session.refresh(semantic_chunk)

    class FakeCollection:
        def query(self, query_embeddings, n_results, where):
            return {
                "documents": [[semantic_chunk.content]],
                "metadatas": [[
                    {
                        "source_id": str(source.id),
                        "document_id": str(document.id),
                        "chunk_id": str(semantic_chunk.id),
                        "title": "Pricing Notes",
                    }
                ]],
                "ids": [[str(semantic_chunk.id)]],
            }

    monkeypatch.setattr(
        query_service,
        "embed_texts_with_local_model",
        lambda texts, model_name=LOCAL_EMBEDDING_MODEL: [[0.1, 0.2, 0.3]],
    )
    monkeypatch.setattr(
        query_service,
        "get_retrieval_collection",
        lambda embedding_model: FakeCollection(),
    )

    result = query_service.retrieve_hybrid_evidence(
        db_session,
        project_id=project.id,
        query="competitor pricing discount",
        top_k=2,
    )

    returned_ids = {record.metadata["chunk_id"] for record in result.records}
    assert str(semantic_chunk.id) in returned_ids
    assert str(lexical_chunk.id) in returned_ids
    assert result.diagnostics["mode"] == "hybrid"
    assert result.diagnostics["reranker"] == "reciprocal_rank_fusion"
    assert result.diagnostics["semantic_candidates"] == 1
    assert result.diagnostics["lexical_candidates"] >= 1
