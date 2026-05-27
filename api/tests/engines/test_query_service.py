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


def test_search_knowledge_base_attempts_reindex_for_old_embedding_chunks(
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
        assert exc.code == "SOURCE_INDEXING_FAILED"
        assert exc.status_code == 422
        assert "Stored artifact" in exc.details["reason"]


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


def test_retrieval_lazy_indexes_uploaded_sources_and_matches_vietnamese(
    db_session,
    monkeypatch,
    tmp_path,
):
    from app.storage.models import Chunk, Document, Project, Source

    project = Project(name="Lazy indexing", description="query")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source_path = tmp_path / "chuong-1.txt"
    source_path.write_text("placeholder", encoding="utf-8")
    source = Source(
        project_id=project.id,
        type="file",
        original_uri="chuong-1.txt",
        storage_path=str(source_path),
        checksum="lazy-source",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    class EmptyCollection:
        def query(self, query_embeddings, n_results, where):
            return {"documents": [[]], "metadatas": [[]], "ids": [[]]}

    def fake_process_sources(
        db,
        project_id,
        job_id,
        sources,
        chunk_size,
        chunk_overlap,
        parent_run_id=None,
    ):
        document = Document(
            source_id=sources[0].id,
            title="chuong-1.txt",
            raw_path=sources[0].storage_path,
            clean_text="Chương 1 trình bày nội dung tổng quan của học phần.",
            token_count=10,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        chunk = Chunk(
            document_id=document.id,
            chunk_index=0,
            content="Chương 1 trình bày nội dung tổng quan của học phần.",
            chroma_id="lazy-chunk",
            embedding_model=LOCAL_EMBEDDING_MODEL,
            chunk_metadata={
                "source_id": str(sources[0].id),
                "document_id": str(document.id),
                "chunk_id": "lazy-chunk",
                "title": "chuong-1.txt",
            },
        )
        db.add(chunk)
        db.commit()
        return {
            "run_id": "lazy-run",
            "documents_created": 1,
            "chunks_created": 1,
        }

    monkeypatch.setattr(
        query_service,
        "embed_texts_with_local_model",
        lambda texts, model_name=LOCAL_EMBEDDING_MODEL: [[0.1, 0.2, 0.3]],
    )
    monkeypatch.setattr(
        query_service,
        "get_retrieval_collection",
        lambda embedding_model: EmptyCollection(),
    )
    monkeypatch.setattr(query_service, "process_sources", fake_process_sources)

    result = query_service.retrieve_hybrid_evidence(
        db_session,
        project_id=project.id,
        query="tóm tắt nội dung chương 1",
        top_k=3,
    )

    assert result.records
    assert result.records[0].metadata["chunk_id"] == "lazy-chunk"
    assert result.diagnostics["indexing"]["sources_processed"] == 1
    assert result.diagnostics["lexical_candidates"] == 1
    assert "chương" in query_service._tokenize_query("tóm tắt nội dung chương 1")
    assert query_service._score_lexical_match(
        ["chương", "1"],
        "chuong_1.pptx Slide 1",
    ) > query_service._score_lexical_match(
        ["chương", "1"],
        "chuong_2.pptx Slide 1",
    )
    assert query_service._score_title_match(
        ["chương", "1"],
        "chuong_1.pptx",
    ) > query_service._score_title_match(
        ["chương", "1"],
        "chuong_2.pptx",
    )


def test_retrieval_expands_context_for_requested_chapter(db_session, monkeypatch):
    from app.storage.models import Chunk, Document, Project, Source

    project = Project(name="Chapter context", description="query")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source_one = Source(
        project_id=project.id,
        type="file",
        original_uri="chuong 1.pptx",
        storage_path="/tmp/chuong-1.pptx",
        checksum="chapter-1",
        status="completed",
    )
    source_two = Source(
        project_id=project.id,
        type="file",
        original_uri="chuong 2.pptx",
        storage_path="/tmp/chuong-2.pptx",
        checksum="chapter-2",
        status="completed",
    )
    db_session.add_all([source_one, source_two])
    db_session.commit()
    db_session.refresh(source_one)
    db_session.refresh(source_two)

    document_one = Document(
        source_id=source_one.id,
        title="chuong_1.pptx",
        raw_path="/tmp/chuong-1.pptx",
        clean_text="chapter one",
        token_count=2,
    )
    document_two = Document(
        source_id=source_two.id,
        title="chuong_2.pptx",
        raw_path="/tmp/chuong-2.pptx",
        clean_text="chapter two",
        token_count=2,
    )
    db_session.add_all([document_one, document_two])
    db_session.commit()
    db_session.refresh(document_one)
    db_session.refresh(document_two)

    for index in range(3):
        db_session.add(
            Chunk(
                document_id=document_two.id,
                chunk_index=index,
                content=f"Slide {index + 1} chương 2 content",
                chroma_id=f"chapter-two-{index}",
                embedding_model=LOCAL_EMBEDDING_MODEL,
                chunk_metadata={
                    "source_id": str(source_two.id),
                    "document_id": str(document_two.id),
                    "chunk_id": f"chapter-two-{index}",
                    "title": "chuong_2.pptx",
                    "page_number": index + 1,
                },
            )
        )
    db_session.add(
        Chunk(
            document_id=document_one.id,
            chunk_index=0,
            content="Slide 1 chương 1 content",
            chroma_id="chapter-one-0",
            embedding_model=LOCAL_EMBEDDING_MODEL,
            chunk_metadata={
                "source_id": str(source_one.id),
                "document_id": str(document_one.id),
                "chunk_id": "chapter-one-0",
                "title": "chuong_1.pptx",
                "page_number": 1,
            },
        )
    )
    db_session.commit()

    class EmptyCollection:
        def query(self, query_embeddings, n_results, where):
            return {"documents": [[]], "metadatas": [[]], "ids": [[]]}

    monkeypatch.setattr(
        query_service,
        "embed_texts_with_local_model",
        lambda texts, model_name=LOCAL_EMBEDDING_MODEL: [[0.1, 0.2, 0.3]],
    )
    monkeypatch.setattr(
        query_service,
        "get_retrieval_collection",
        lambda embedding_model: EmptyCollection(),
    )

    result = query_service.retrieve_hybrid_evidence(
        db_session,
        project_id=project.id,
        query="phân tích chương 2",
        top_k=1,
    )

    assert [record.metadata["chunk_id"] for record in result.records[:3]] == [
        "chapter-two-0",
        "chapter-two-1",
        "chapter-two-2",
    ]
    assert all(record.metadata["title"] == "chuong_2.pptx" for record in result.records[:3])
