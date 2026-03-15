def test_create_project_returns_envelope(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": "Bootstrap Project", "description": "Contract test"},
    )

    assert response.status_code == 201
    body = response.json()

    assert "data" in body
    assert "meta" in body
    assert body["data"]["name"] == "Bootstrap Project"
    assert "id" in body["data"]
