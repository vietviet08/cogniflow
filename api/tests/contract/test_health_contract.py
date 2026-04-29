import uuid

from app.observability.telemetry import reset_metrics
from app.storage.models import Job


def test_health_endpoint_returns_envelope(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["data"]["status"] == "ok"
    assert body["data"]["service"] == "cogniflow-api"
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]


def test_health_endpoint_propagates_request_id(unauthenticated_client):
    response = unauthenticated_client.get(
        "/api/v1/health",
        headers={"x-request-id": "req-observability-1"},
    )

    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-observability-1"
    assert response.json()["meta"]["request_id"] == "req-observability-1"


def test_metrics_endpoint_returns_snapshot(unauthenticated_client):
    reset_metrics()

    unauthenticated_client.get("/api/v1/health")
    response = unauthenticated_client.get("/api/v1/metrics")

    assert response.status_code == 200
    body = response.json()
    metrics = body["data"]["metrics"]
    assert "http_requests_total" in metrics
    assert "http_latency_ms" in metrics
    assert any(key.endswith("/health") for key in metrics["http_requests_total"])


def test_ops_slo_endpoint_reports_queue_and_provider_alerts(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])

    for _ in range(26):
        db_session.add(
            Job(
                project_id=project_id,
                job_type="processing",
                status="queued",
                queue_name="processing",
            )
        )
    db_session.add(
        Job(
            project_id=project_id,
            job_type="report_generation",
            status="dead_letter",
            queue_name="report",
            error_code="REPORT_UPSTREAM_ERROR",
            error_message="OpenAI provider timeout",
        )
    )
    db_session.commit()

    response = client.get("/api/v1/ops/slo")

    assert response.status_code == 200
    data = response.json()["data"]
    alert_codes = {alert["code"] for alert in data["alerts"]}
    assert data["status"] in {"warning", "critical"}
    assert data["jobs"]["status_counts"]["queued"] == 26
    assert "QUEUE_BACKLOG_HIGH" in alert_codes
    assert "PROVIDER_FAILURES_DETECTED" in alert_codes


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Ops {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
