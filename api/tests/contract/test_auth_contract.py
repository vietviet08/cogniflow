def test_bootstrap_auth_returns_user_and_token(unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "owner@example.com", "display_name": "Owner"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["user"]["email"] == "owner@example.com"
    assert body["data"]["token"]


def test_protected_endpoint_requires_bearer_token(unauthenticated_client):
    response = unauthenticated_client.get("/api/v1/projects")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"
