from app.observability.telemetry import reset_metrics


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
