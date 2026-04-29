from __future__ import annotations

import os
import sys
import uuid
from typing import Any

import requests

API_BASE_URL = os.getenv("NOTEMESH_API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
SMOKE_EMAIL = os.getenv("NOTEMESH_SMOKE_EMAIL", "staging-smoke@example.com")
SMOKE_PASSWORD = os.getenv("NOTEMESH_SMOKE_PASSWORD", "staging-smoke")


def main() -> int:
    session = requests.Session()
    _check_health(session)
    token = _ensure_auth_token(session)
    session.headers.update({"Authorization": f"Bearer {token}"})
    project = _create_project(session)
    saved_search = _create_saved_search(session, project["id"])
    _run_saved_search(session, project["id"], saved_search["saved_search_id"])
    print("staging smoke passed")
    return 0


def _check_health(session: requests.Session) -> None:
    response = session.get(f"{API_BASE_URL}/health", timeout=20)
    response.raise_for_status()
    _assert_envelope(response.json())


def _ensure_auth_token(session: requests.Session) -> str:
    bootstrap_payload = {
        "email": SMOKE_EMAIL,
        "display_name": "Staging Smoke",
        "password": SMOKE_PASSWORD,
    }
    bootstrap = session.post(
        f"{API_BASE_URL}/auth/bootstrap",
        json=bootstrap_payload,
        timeout=20,
    )
    if bootstrap.status_code not in {200, 201, 409, 422}:
        bootstrap.raise_for_status()

    login = session.post(
        f"{API_BASE_URL}/auth/login",
        json={"email": SMOKE_EMAIL, "password": SMOKE_PASSWORD, "token_name": "staging-smoke"},
        timeout=20,
    )
    login.raise_for_status()
    body = login.json()
    _assert_envelope(body)
    token = body["data"].get("token")
    if not token:
        raise RuntimeError("Auth login did not return a token.")
    return str(token)


def _create_project(session: requests.Session) -> dict[str, Any]:
    response = session.post(
        f"{API_BASE_URL}/projects",
        json={
            "name": f"Staging Smoke {uuid.uuid4()}",
            "description": "Automated staging smoke project.",
        },
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    _assert_envelope(body)
    return body["data"]


def _create_saved_search(session: requests.Session, project_id: str) -> dict[str, Any]:
    response = session.post(
        f"{API_BASE_URL}/projects/{project_id}/saved-searches",
        json={
            "name": "Staging weekly research",
            "query": "What changed in the staging corpus?",
            "report_type": "executive_brief",
            "provider": "openai",
            "schedule_interval_minutes": 10080,
        },
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    _assert_envelope(body)
    return body["data"]


def _run_saved_search(
    session: requests.Session,
    project_id: str,
    saved_search_id: str,
) -> None:
    response = session.post(
        f"{API_BASE_URL}/projects/{project_id}/saved-searches/{saved_search_id}/run",
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    _assert_envelope(body)
    if body["data"].get("status") != "queued":
        raise RuntimeError("Saved search did not queue a report job.")


def _assert_envelope(body: dict[str, Any]) -> None:
    if "data" not in body or "meta" not in body:
        raise RuntimeError(f"Response is not a NoteMesh envelope: {body}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"staging smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
