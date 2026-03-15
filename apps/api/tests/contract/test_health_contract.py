def test_health_endpoint_returns_envelope(client):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["data"]["status"] == "ok"
    assert body["data"]["service"] == "notemesh-api"
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]
