import uuid

from app.api.routes import query as query_route_module
from app.services.query_service import QueryError


def test_query_search_returns_answer_and_citations(client, monkeypatch):
    project = _create_project(client)

    def fake_search_knowledge_base(db, project_id, query, provider, top_k, filters):
        assert str(project_id) == project["id"]
        assert query == "What is the main idea?"
        assert provider == "gemini"
        assert top_k == 3
        return {
            "answer": "The main idea is retrieval grounded on indexed chunks.",
            "citations": [
                {
                    "citation_id": "chunk-1",
                    "source_id": "source-1",
                    "document_id": "doc-1",
                    "chunk_id": "chunk-1",
                    "title": "Paper A",
                    "url": "https://arxiv.org/abs/1234.5678",
                }
            ],
            "run_id": "run-1",
            "provider": "gemini",
            "model": "gemini-2.5-flash",
        }

    monkeypatch.setattr(query_route_module, "search_knowledge_base", fake_search_knowledge_base)

    response = client.post(
        "/api/v1/query/search",
        json={
            "project_id": project["id"],
            "query": "What is the main idea?",
            "provider": "gemini",
            "top_k": 3,
            "filters": {"source_types": ["arxiv"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["answer"] == "The main idea is retrieval grounded on indexed chunks."
    assert body["data"]["run_id"] == "run-1"
    assert body["data"]["provider"] == "gemini"
    assert body["data"]["model"] == "gemini-2.5-flash"
    assert len(body["data"]["citations"]) == 1
    assert body["data"]["citations"][0]["chunk_id"] == "chunk-1"


def test_query_search_returns_structured_upstream_error(client, monkeypatch):
    project = _create_project(client)

    def fake_search_knowledge_base(db, project_id, query, provider, top_k, filters):
        raise QueryError(
            "OpenAI request failed during retrieval.",
            code="QUERY_UPSTREAM_ERROR",
            status_code=502,
            details={
                "provider": "openai",
                "stage": "retrieval",
                "reason": "Upstream provider returned an HTML error page.",
            },
        )

    monkeypatch.setattr(query_route_module, "search_knowledge_base", fake_search_knowledge_base)

    response = client.post(
        "/api/v1/query/search",
        json={
            "project_id": project["id"],
            "query": "What is the main idea?",
            "provider": "openai",
        },
    )

    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "QUERY_UPSTREAM_ERROR"
    assert body["error"]["details"]["provider"] == "openai"
    assert body["error"]["details"]["stage"] == "retrieval"
    assert body["error"]["details"]["reason"] == "Upstream provider returned an HTML error page."


def test_query_search_hides_unexpected_raw_exception_details(client, monkeypatch):
    project = _create_project(client)

    def fake_search_knowledge_base(db, project_id, query, provider, top_k, filters):
        raise RuntimeError("<!DOCTYPE html><html><body>bad gateway</body></html>")

    monkeypatch.setattr(query_route_module, "search_knowledge_base", fake_search_knowledge_base)

    response = client.post(
        "/api/v1/query/search",
        json={
            "project_id": project["id"],
            "query": "What is the main idea?",
            "provider": "openai",
        },
    )

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "QUERY_INTERNAL_ERROR"
    assert body["error"]["message"] == "Unexpected query failure."
    assert body["error"]["details"] == {}


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Query {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
