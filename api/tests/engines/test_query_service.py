from app.services import query_service


def test_search_knowledge_base_sanitizes_embedding_provider_errors(monkeypatch):
    monkeypatch.setattr(
        query_service,
        "normalize_provider",
        lambda provider: provider,
    )
    monkeypatch.setattr(
        query_service,
        "resolve_embedding_provider_config",
        lambda db, project_id, provider: {
            "api_key": "sk-test",
            "embedding_model": "text-embedding-3-small",
        },
    )
    monkeypatch.setattr(
        query_service,
        "resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
        },
    )

    def fake_embed_texts_with_config(texts, api_key, model, base_url=None):
        raise RuntimeError("<!DOCTYPE html><html><body>bad gateway</body></html>")

    monkeypatch.setattr(query_service, "embed_texts_with_config", fake_embed_texts_with_config)

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
        assert exc.code == "QUERY_UPSTREAM_ERROR"
        assert exc.status_code == 502
        assert exc.details["provider"] == "openai"
        assert exc.details["stage"] == "retrieval"
        assert exc.details["reason"] == "Upstream provider returned an HTML error page."
