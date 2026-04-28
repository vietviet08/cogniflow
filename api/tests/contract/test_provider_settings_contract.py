import uuid

from app.core.crypto import SECRET_PREFIX, decrypt_secret
from app.services import provider_settings_service
from app.storage.models import IntegrationConnection, ProviderCredential


def test_list_provider_settings_returns_supported_providers(client):
    project = _create_project(client)

    response = client.get(f"/api/v1/projects/{project['id']}/providers")

    assert response.status_code == 200
    body = response.json()
    providers = {item["provider"]: item for item in body["data"]["items"]}
    assert set(providers) == {"openai", "gemini"}
    assert providers["openai"]["configured"] is False
    assert providers["openai"]["supports_base_url"] is True
    assert providers["openai"]["available_chat_models"] == []
    assert providers["gemini"]["configured_source"] == "missing"
    assert providers["gemini"]["supports_base_url"] is False
    assert providers["gemini"]["available_chat_models"] == []
    assert providers["openai"]["available_embedding_models"] == []


def test_save_provider_key_and_models_masks_secret_in_response(client, db_session, monkeypatch):
    project = _create_project(client)
    monkeypatch.setattr(
        provider_settings_service,
        "discover_provider_models",
        lambda provider, api_key, base_url=None: {
            "chat_models": ["gpt-4o", "gpt-4.1-mini"],
            "embedding_models": ["text-embedding-3-small"],
        },
    )

    response = client.put(
        f"/api/v1/projects/{project['id']}/providers/openai",
        json={
            "api_key": "sk-test-openai-1234",
            "base_url": "https://proxy.example.com/v1",
            "chat_model": "gpt-4o",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["provider"] == "openai"
    assert body["data"]["configured"] is True
    assert body["data"]["configured_source"] == "project"
    assert body["data"]["masked_api_key"] == "sk-t...1234"
    assert body["data"]["base_url"] == "https://proxy.example.com/v1"
    assert body["data"]["chat_model"] == "gpt-4o"
    assert body["data"]["embedding_model"] is None
    assert body["data"]["available_chat_models"] == ["gpt-4o", "gpt-4.1-mini"]
    assert body["data"]["available_embedding_models"] == []

    credential = (
        db_session.query(ProviderCredential)
        .filter(
            ProviderCredential.project_id == uuid.UUID(project["id"]),
            ProviderCredential.provider == "openai",
        )
        .one()
    )
    assert credential.api_key.startswith(SECRET_PREFIX)
    assert decrypt_secret(credential.api_key) == "sk-test-openai-1234"


def test_integration_connection_encrypts_access_token_at_rest(client, db_session):
    project = _create_project(client)

    response = client.put(
        f"/api/v1/projects/{project['id']}/integrations/google_drive",
        json={
            "access_token": "drive-token-1234",
            "account_label": "Drive",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["masked_access_token"] == "driv...1234"

    connection = (
        db_session.query(IntegrationConnection)
        .filter(
            IntegrationConnection.project_id == uuid.UUID(project["id"]),
            IntegrationConnection.provider == "google_drive",
        )
        .one()
    )
    assert connection.access_token.startswith(SECRET_PREFIX)
    assert decrypt_secret(connection.access_token) == "drive-token-1234"


def test_delete_provider_key_removes_project_override(client, monkeypatch):
    project = _create_project(client)
    monkeypatch.setattr(
        provider_settings_service,
        "discover_provider_models",
        lambda provider, api_key, base_url=None: {
            "chat_models": ["gemini-2.5-flash"],
            "embedding_models": [],
        },
    )
    client.put(
        f"/api/v1/projects/{project['id']}/providers/gemini",
        json={
            "api_key": "gemini-secret-5678",
            "chat_model": "gemini-2.5-flash",
        },
    )

    response = client.delete(f"/api/v1/projects/{project['id']}/providers/gemini")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["provider"] == "gemini"
    assert body["data"]["removed"] is True
    assert body["data"]["configured"] is False
    assert body["data"]["configured_source"] == "missing"


def test_discover_provider_models_uses_payload_credentials(client, monkeypatch):
    project = _create_project(client)
    monkeypatch.setattr(
        provider_settings_service,
        "discover_provider_models",
        lambda provider, api_key, base_url=None: {
            "chat_models": ["gpt-4.1", "gpt-4o-mini"],
            "embedding_models": ["text-embedding-3-large"],
        },
    )

    response = client.post(
        f"/api/v1/projects/{project['id']}/providers/openai/models/discover",
        json={
            "api_key": "sk-test-openai-1234",
            "base_url": "https://proxy.example.com/v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["provider"] == "openai"
    assert body["data"]["source"] == "payload"
    assert body["data"]["base_url"] == "https://proxy.example.com/v1"
    assert body["data"]["available_chat_models"] == ["gpt-4.1", "gpt-4o-mini"]
    assert body["data"]["available_embedding_models"] == []


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Providers {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
