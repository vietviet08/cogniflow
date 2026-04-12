import uuid

from app.services import intelligence_service


def test_intelligence_scan_generates_change_events_and_digest(client, monkeypatch):
    project = _create_project(client)

    source_response = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/sources",
        json={
            "name": "Competitor pricing",
            "source_url": "https://example.com/pricing",
            "category": "pricing",
            "poll_interval_minutes": 60,
            "is_active": True,
        },
    )
    assert source_response.status_code == 201

    snapshots = iter(
        [
            intelligence_service.SourceSnapshot(
                content_hash="hash-a",
                excerpt="Pricing plan A with monthly details",
            ),
            intelligence_service.SourceSnapshot(
                content_hash="hash-b",
                excerpt="Pricing plan B changed with enterprise compliance and security terms",
            ),
        ]
    )
    monkeypatch.setattr(
        intelligence_service,
        "_fetch_source_snapshot",
        lambda _: next(snapshots),
    )

    first_scan = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/scan",
        json={"mode": "sync", "alert_threshold": "medium"},
    )
    assert first_scan.status_code == 200
    assert first_scan.json()["data"]["checked_sources"] == 1

    second_scan = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/scan",
        json={"mode": "sync", "alert_threshold": "medium"},
    )
    assert second_scan.status_code == 200
    assert second_scan.json()["data"]["events_created"] >= 1
    assert second_scan.json()["data"]["alerts_triggered"] >= 1

    events = client.get(f"/api/v1/projects/{project['id']}/intelligence/events")
    assert events.status_code == 200
    assert events.json()["data"]["total"] >= 2

    digest = client.get(f"/api/v1/projects/{project['id']}/intelligence/digest/today")
    assert digest.status_code == 200
    summary = digest.json()["data"]["summary"]
    assert summary["events_total"] >= 2


def test_intelligence_action_output_approval_and_roi_flow(client, monkeypatch):
    project = _create_project(client)

    source_response = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/sources",
        json={
            "name": "Competitor release notes",
            "source_url": "https://example.com/release",
            "category": "feature",
            "poll_interval_minutes": 120,
            "is_active": True,
        },
    )
    assert source_response.status_code == 201

    snapshots = iter(
        [
            intelligence_service.SourceSnapshot(content_hash="base", excerpt="Feature baseline"),
            intelligence_service.SourceSnapshot(content_hash="changed", excerpt="Feature update with pricing and policy changes"),
        ]
    )
    monkeypatch.setattr(
        intelligence_service,
        "_fetch_source_snapshot",
        lambda _: next(snapshots),
    )

    client.post(
        f"/api/v1/projects/{project['id']}/intelligence/scan",
        json={"mode": "sync", "alert_threshold": "low"},
    )
    client.post(
        f"/api/v1/projects/{project['id']}/intelligence/scan",
        json={"mode": "sync", "alert_threshold": "low"},
    )

    events_response = client.get(f"/api/v1/projects/{project['id']}/intelligence/events")
    assert events_response.status_code == 200
    event_id = events_response.json()["data"]["items"][0]["event_id"]

    action_response = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/actions",
        json={
            "title": "Prepare sales response",
            "description": "Update positioning and messaging",
            "event_id": event_id,
            "owner": "sales-lead",
            "priority": "high",
        },
    )
    assert action_response.status_code == 201
    action_id = action_response.json()["data"]["action_id"]

    update_response = client.patch(
        f"/api/v1/projects/{project['id']}/intelligence/actions/{action_id}",
        json={"status": "done"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["status"] == "done"

    output_response = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/outputs",
        json={"output_type": "battlecard", "event_id": event_id},
    )
    assert output_response.status_code == 201
    assert output_response.json()["data"]["output_type"] == "battlecard"

    approval_response = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/approvals",
        json={"target_type": "output", "target_id": output_response.json()["data"]["output_id"]},
    )
    assert approval_response.status_code == 201
    approval_id = approval_response.json()["data"]["approval_id"]

    review_response = client.post(
        f"/api/v1/projects/{project['id']}/intelligence/approvals/{approval_id}/review",
        json={"status": "approved", "review_notes": "Looks good"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["data"]["status"] == "approved"

    roi_response = client.get(f"/api/v1/projects/{project['id']}/intelligence/roi")
    assert roi_response.status_code == 200
    roi_data = roi_response.json()["data"]
    assert roi_data["actions_completed"] >= 1
    assert roi_data["outputs_generated"] >= 1


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Radar {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
