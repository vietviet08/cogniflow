import uuid


def test_list_provider_settings_returns_supported_providers(client):
    project = _create_project(client)

    response = client.get(f"/api/v1/projects/{project['id']}/providers")

    assert response.status_code == 200
    body = response.json()
    providers = {item["provider"]: item for item in body["data"]["items"]}
    assert set(providers) == {"openai", "gemini"}
    assert providers["openai"]["configured"] is False
    assert providers["gemini"]["configured_source"] == "missing"


def test_save_provider_key_masks_secret_in_response(client):
    project = _create_project(client)

    response = client.put(
        f"/api/v1/projects/{project['id']}/providers/openai",
        json={"api_key": "sk-test-openai-1234"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["provider"] == "openai"
    assert body["data"]["configured"] is True
    assert body["data"]["configured_source"] == "project"
    assert body["data"]["masked_api_key"] == "sk-t...1234"


def test_delete_provider_key_removes_project_override(client):
    project = _create_project(client)
    client.put(
        f"/api/v1/projects/{project['id']}/providers/gemini",
        json={"api_key": "gemini-secret-5678"},
    )

    response = client.delete(f"/api/v1/projects/{project['id']}/providers/gemini")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["provider"] == "gemini"
    assert body["data"]["removed"] is True
    assert body["data"]["configured"] is False
    assert body["data"]["configured_source"] == "missing"


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Providers {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
