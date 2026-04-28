import uuid

from app.api.routes import reports as report_route_module
from app.storage.models import (
    Chunk,
    Document,
    Insight,
    InsightCitation,
    ProcessingRun,
    Report,
    ReportInsight,
    Source,
)


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
    project = _create_project(client)

    report = Report(
        project_id=uuid.UUID(project["id"]),
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
    assert (
        body["data"]["structured_payload"]["items"][0]["recommended_action"]
        == "Clarify the SLA before approval."
    )


def test_update_action_item_status_returns_updated_report(client, db_session, monkeypatch):
    project = _create_project(client)
    report = Report(
        project_id=uuid.UUID(project["id"]),
        query="What should we do next?",
        title="Action Items: Launch checklist",
        report_type="action_items",
        format="markdown",
        content="# Action Items",
        structured_payload={"overview": "One key follow-up was detected.", "items": []},
        status="completed",
        run_id=None,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    monkeypatch.setattr(
        report_route_module,
        "update_action_item_status",
        lambda **kwargs: {
            "report_id": str(report.id),
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
        f"/api/v1/reports/{report.id}/action-items/item-1",
        json={"status": "done"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["structured_payload"]["items"][0]["status"] == "done"


def test_report_lineage_returns_auditable_source_document_chunk_graph(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])

    source = Source(
        project_id=project_id,
        type="file",
        original_uri="evidence.pdf",
        storage_path="data/uploads/evidence.pdf",
        checksum="lineage",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Evidence",
        raw_path=source.storage_path,
        clean_text="The source text supports a launch action.",
        token_count=8,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="The source text supports a launch action.",
        chroma_id=str(uuid.uuid4()),
        embedding_model="local-test-model",
        chunk_metadata={},
    )
    db_session.add(chunk)

    run = ProcessingRun(
        project_id=project_id,
        run_type="report",
        model_id="gpt-test",
        retrieval_config={"mode": "hybrid"},
        run_metadata={"query": "What action is supported?"},
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(chunk)
    db_session.refresh(run)

    insight = Insight(
        project_id=project_id,
        query="What action is supported?",
        summary="A launch action is supported.",
        findings=[],
        provider="openai",
        model_id="gpt-test",
        run_id=run.id,
        status="completed",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    citation = InsightCitation(
        insight_id=insight.id,
        source_id=str(source.id),
        source_type="file",
        document_id=str(document.id),
        chunk_id=str(chunk.id),
        title="Evidence",
        url="",
    )
    report = Report(
        project_id=project_id,
        query="What action is supported?",
        title="Action Items: Evidence",
        report_type="action_items",
        format="markdown",
        content="# Action Items",
        structured_payload={"overview": "Do the launch action.", "items": []},
        status="completed",
        run_id=run.id,
    )
    db_session.add_all([citation, report])
    db_session.commit()
    db_session.refresh(report)

    db_session.add(ReportInsight(report_id=report.id, insight_id=insight.id))
    db_session.commit()

    response = client.get(f"/api/v1/reports/{report.id}/lineage")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["summary"]["source_count"] == 1
    assert data["summary"]["chunk_count"] == 1
    assert data["runs"][0]["retrieval_config"]["mode"] == "hybrid"
    assert data["sources"][0]["documents"][0]["chunks"][0]["chunk_id"] == str(chunk.id)
    assert data["citations"][0]["quote"] == "The source text supports a launch action."


def test_insight_lineage_returns_citation_graph(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])

    insight = Insight(
        project_id=project_id,
        query="What changed?",
        summary="Pricing changed.",
        findings=[],
        provider="openai",
        model_id="gpt-test",
        status="completed",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    response = client.get(f"/api/v1/insights/{insight.id}/lineage")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["insight_id"] == str(insight.id)
    assert data["summary"]["insight_count"] == 1


def _create_project(client):
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Reports {uuid.uuid4()}", "description": "test"},
    )
    assert response.status_code == 201
    return response.json()["data"]
