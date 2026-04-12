from app.core.security import verify_password
from app.storage.models import User


def test_bootstrap_auth_returns_user_and_token(unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "owner@example.com", "display_name": "Owner", "password": "admin"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["user"]["email"] == "owner@example.com"
    assert body["data"]["user"]["role"] == "admin"
    assert body["data"]["token"]


def test_login_auth_returns_user_and_token(unauthenticated_client):
    bootstrap = unauthenticated_client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "owner@example.com", "display_name": "Owner", "password": "admin"},
    )
    assert bootstrap.status_code == 201

    response = unauthenticated_client.post(
        "/api/v1/auth/login",
        json={"email": "owner@example.com", "password": "admin"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["user"]["email"] == "owner@example.com"
    assert body["data"]["token"]


def test_bootstrap_hashes_password(db_session, unauthenticated_client):
    response = unauthenticated_client.post(
        "/api/v1/auth/bootstrap",
        json={"email": "owner@example.com", "display_name": "Owner", "password": "admin"},
    )
    assert response.status_code == 201

    user = db_session.query(User).filter(User.email == "owner@example.com").one()
    assert user.password_hash != "admin"
    assert verify_password("admin", user.password_hash)


def test_protected_endpoint_requires_bearer_token(unauthenticated_client):
    response = unauthenticated_client.get("/api/v1/projects")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "AUTH_REQUIRED"
