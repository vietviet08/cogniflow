import uuid

from app.api.routes import chat as chat_route_module


def test_chat_message_uses_recent_history_for_follow_up_retrieval(client, monkeypatch):
    project = _create_project(client)
    session_response = client.post(
        f"/api/v1/projects/{project['id']}/chat/sessions",
        json={"title": "Pricing research"},
    )
    assert session_response.status_code == 201
    session_id = session_response.json()["data"]["id"]

    calls = []

    def fake_search_knowledge_base(
        db,
        project_id,
        query,
        provider,
        top_k,
        filters=None,
        conversation_context=None,
    ):
        calls.append(
            {
                "project_id": str(project_id),
                "query": query,
                "provider": provider,
                "top_k": top_k,
                "conversation_context": conversation_context or [],
            }
        )
        return {
            "answer": "Supported answer",
            "citations": [],
            "run_id": str(uuid.uuid4()),
            "provider": provider,
            "model": "gpt-test",
            "retrieval": {"mode": "hybrid"},
        }

    monkeypatch.setattr(chat_route_module, "search_knowledge_base", fake_search_knowledge_base)

    first = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={
            "content": "What changed in competitor pricing?",
            "provider": "openai",
            "top_k": 4,
        },
    )
    assert first.status_code == 201
    assert first.json()["data"]["context"]["history_aware_retrieval"] is False

    second = client.post(
        f"/api/v1/chat/sessions/{session_id}/messages",
        json={
            "content": "What about enterprise plans?",
            "provider": "openai",
            "top_k": 4,
        },
    )
    assert second.status_code == 201
    body = second.json()["data"]
    assert body["context"]["history_turns_used"] == 2
    assert body["context"]["history_aware_retrieval"] is True
    assert body["assistant_message"]["retrieval"] == {"mode": "hybrid"}

    follow_up_call = calls[-1]
    assert follow_up_call["query"].startswith("What about enterprise plans?")
    assert "What changed in competitor pricing?" in follow_up_call["query"]
    assert follow_up_call["conversation_context"][0]["role"] == "user"
    assert follow_up_call["conversation_context"][-1] == {
        "role": "user",
        "content": "What about enterprise plans?",
    }


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Chat {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
