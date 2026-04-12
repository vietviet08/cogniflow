from app.services.provider_model_service import discover_provider_models


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._payload


def test_discover_openai_models_default_base_url_filters_to_openai_chat(monkeypatch):
    def fake_get(url, headers, timeout):
        assert url == "https://api.openai.com/v1/models"
        assert "Authorization" in headers
        assert timeout == 20
        return _FakeResponse(
            {
                "data": [
                    {"id": "gpt-4.1-mini"},
                    {"id": "text-embedding-3-small"},
                    {"id": "claude-3-7-sonnet"},
                ]
            }
        )

    monkeypatch.setattr("app.services.provider_model_service.requests.get", fake_get)

    models = discover_provider_models(provider="openai", api_key="sk-test")

    assert models["chat_models"] == ["gpt-4.1-mini"]
    assert models["embedding_models"] == ["text-embedding-3-small"]


def test_discover_openai_models_custom_base_url_keeps_non_embedding_models(monkeypatch):
    def fake_get(url, headers, timeout):
        assert url == "https://proxy.example.com/v1/models"
        assert "Authorization" in headers
        assert timeout == 20
        return _FakeResponse(
            {
                "data": [
                    {"id": "gpt-4.1-mini"},
                    {"id": "claude-3-7-sonnet"},
                    {"id": "deepseek-chat"},
                    {"id": "text-embedding-3-small"},
                ]
            }
        )

    monkeypatch.setattr("app.services.provider_model_service.requests.get", fake_get)

    models = discover_provider_models(
        provider="openai",
        api_key="sk-test",
        base_url="https://proxy.example.com/v1",
    )

    assert models["chat_models"] == ["claude-3-7-sonnet", "deepseek-chat", "gpt-4.1-mini"]
    assert models["embedding_models"] == ["text-embedding-3-small"]
