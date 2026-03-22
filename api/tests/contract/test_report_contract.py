import uuid

from app.api.routes import reports as report_route_module
from app.storage.models import Project, Report


def test_generate_report_returns_structured_payload(client, monkeypatch):
    project = _create_project(client)

    monkeypatch.setattr(
        report_route_module,
        "generate_report",
        lambda **kwargs: {
            "report_id": "report-1",
            "query": "What should we do next?",
            "title": "Action Items: Launch checklist",
            "type": "action_items",
            "format": "markdown",
            "content": "# Action Items",
            "structured_payload": {
                "overview": "One key follow-up was detected.",
                "items": [
                    {
                        "id": "item-1",
                        "title": "Confirm launch date",
                        "description": "Validate the launch date with operations.",
                        "priority": "high",
                        "owner_suggested": "Ops",
                        "due_date_suggested": None,
                        "status": "open",
                        "citations": [],
                    }
                ],
            },
            "status": "completed",
            "run_id": "run-1",
            "insight_id": "insight-1",
            "source_ids": [],
            "citations": [],
        },
    )

    response = client.post(
        "/api/v1/reports/generate",
        json={
            "project_id": project["id"],
            "query": "What should we do next?",
            "type": "action_items",
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["type"] == "action_items"
    assert body["data"]["query"] == "What should we do next?"
    assert body["data"]["structured_payload"]["items"][0]["title"] == "Confirm launch date"


def test_get_report_returns_structured_payload(client, db_session):
    project = Project(name="Report contract", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    report = Report(
        project_id=project.id,
        query="What are the main vendor risks?",
        title="Risk Analysis: Vendor Review",
        report_type="risk_analysis",
        format="markdown",
        content="# Risk Analysis",
        structured_payload={
            "overview": "One medium-severity risk was identified.",
            "items": [
                {
                    "id": "risk-1",
                    "title": "Unclear SLA",
                    "severity": "medium",
                    "why_it_matters": "The vendor response does not define recovery targets.",
                    "recommended_action": "Clarify the SLA before approval.",
                    "status": "needs_review",
                    "citations": [],
                }
            ],
        },
        status="completed",
        run_id=None,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    response = client.get(f"/api/v1/reports/{report.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["type"] == "risk_analysis"
    assert body["data"]["query"] == "What are the main vendor risks?"
    assert body["data"]["structured_payload"]["items"][0]["recommended_action"] == "Clarify the SLA before approval."


def test_update_action_item_status_returns_updated_report(client, monkeypatch):
    project = _create_project(client)

    monkeypatch.setattr(
        report_route_module,
        "update_action_item_status",
        lambda **kwargs: {
            "report_id": "report-1",
            "project_id": project["id"],
            "query": "What should we do next?",
            "title": "Action Items: Launch checklist",
            "type": "action_items",
            "format": "markdown",
            "content": "# Action Items",
            "structured_payload": {
                "overview": "One key follow-up was detected.",
                "items": [
                    {
                        "id": "item-1",
                        "title": "Confirm launch date",
                        "description": "Validate the launch date with operations.",
                        "priority": "high",
                        "owner_suggested": "Ops",
                        "due_date_suggested": None,
                        "status": "done",
                        "citations": [],
                    }
                ],
            },
            "status": "completed",
            "run_id": "run-1",
            "created_at": "2026-03-22T00:00:00+00:00",
        },
    )

    response = client.put(
        "/api/v1/reports/report-1/action-items/item-1",
        json={"status": "done"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["structured_payload"]["items"][0]["status"] == "done"


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Reports {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
