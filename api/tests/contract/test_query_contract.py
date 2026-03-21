import uuid

from app.api.routes import query as query_route_module


def test_query_search_returns_answer_and_citations(client, monkeypatch):
    project = _create_project(client)

    def fake_search_knowledge_base(db, project_id, query, top_k, filters):
        assert str(project_id) == project["id"]
        assert query == "What is the main idea?"
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
        }

    monkeypatch.setattr(query_route_module, "search_knowledge_base", fake_search_knowledge_base)

    response = client.post(
        "/api/v1/query/search",
        json={
            "project_id": project["id"],
            "query": "What is the main idea?",
            "top_k": 3,
            "filters": {"source_types": ["arxiv"]},
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["answer"] == "The main idea is retrieval grounded on indexed chunks."
    assert body["data"]["run_id"] == "run-1"
    assert len(body["data"]["citations"]) == 1
    assert body["data"]["citations"][0]["chunk_id"] == "chunk-1"


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Query {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
