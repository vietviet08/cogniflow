def test_job_not_found_returns_error_envelope(client):
    response = client.get("/api/v1/jobs/9e084c7a-a24d-4ee8-86bf-a79550970f0e")

    assert response.status_code == 404
    body = response.json()

    assert "error" in body
    assert "meta" in body
    assert body["error"]["code"] == "JOB_NOT_FOUND"
    assert "message" in body["error"]
