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


def test_list_projects_includes_membership_role(client):
    create_response = client.post(
        "/api/v1/projects",
        json={"name": "RBAC Project", "description": "Role payload check"},
    )
    assert create_response.status_code == 201

    list_response = client.get("/api/v1/projects")
    assert list_response.status_code == 200

    body = list_response.json()
    assert "data" in body
    assert "items" in body["data"]
    assert len(body["data"]["items"]) >= 1
    assert body["data"]["items"][0]["role"] in {"viewer", "editor", "owner"}
