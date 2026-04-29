import uuid

from app.storage.models import Approval, Insight, Report


def test_research_review_flow_for_report(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])
    report = Report(
        project_id=project_id,
        query="What should be reviewed?",
        title="Research Brief: Review",
        report_type="research_brief",
        format="markdown",
        content="# Review",
        structured_payload={},
        status="completed",
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    create_response = client.post(
        f"/api/v1/projects/{project['id']}/reviews",
        json={"target_type": "report", "target_id": str(report.id)},
    )

    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["target_type"] == "report"
    assert created["target_id"] == str(report.id)
    assert created["status"] == "pending"

    list_response = client.get(
        f"/api/v1/projects/{project['id']}/reviews",
        params={"target_type": "report", "status": "pending"},
    )
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 1

    decision_response = client.post(
        f"/api/v1/projects/{project['id']}/reviews/{created['approval_id']}/decision",
        json={"status": "approved", "review_notes": "Citations look decision-ready."},
    )
    assert decision_response.status_code == 200
    decision = decision_response.json()["data"]
    assert decision["status"] == "approved"
    assert decision["review_notes"] == "Citations look decision-ready."

    approval = db_session.get(Approval, uuid.UUID(created["approval_id"]))
    assert approval is not None
    assert approval.reviewed_at is not None


def test_research_review_validates_insight_target_project(client, db_session):
    project = _create_project(client)
    other_project = _create_project(client)
    insight = Insight(
        project_id=uuid.UUID(other_project["id"]),
        query="What changed?",
        summary="Something changed.",
        findings=[],
        provider="openai",
        model_id="gpt-test",
        status="completed",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    response = client.post(
        f"/api/v1/projects/{project['id']}/reviews",
        json={"target_type": "insight", "target_id": str(insight.id)},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REVIEW_TARGET_NOT_FOUND"


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Reviews {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
