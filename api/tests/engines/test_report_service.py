import uuid

from app.services import report_service
from app.storage.models import Chunk, Document, Project, Report, Source


def test_generate_action_items_report_persists_structured_payload(db_session, monkeypatch):
    project = Project(name="Actionable Outputs", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="handoff.pdf",
        storage_path="data/uploads/handoff.pdf",
        checksum="checksum-1",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Project Handoff",
        raw_path=source.storage_path,
        clean_text="Alice should review the roadmap before Friday.",
        token_count=24,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=0,
        content="Alice should review the roadmap before Friday and share blockers with ops.",
        chroma_id=str(uuid.uuid4()),
        embedding_model="local-test-model",
        chunk_metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    insight_id = uuid.uuid4()

    monkeypatch.setattr(
        report_service,
        "generate_insight",
        lambda **kwargs: {
            "insight_id": str(insight_id),
            "summary": "The evidence contains clear follow-ups for the team.",
            "findings": [
                {
                    "theme": "Roadmap follow-up",
                    "points": ["Alice should review the roadmap before Friday."],
                }
            ],
            "citations": [
                {
                    "citation_id": str(chunk.id),
                    "source_id": str(source.id),
                    "document_id": str(document.id),
                    "chunk_id": str(chunk.id),
                    "title": "Project Handoff",
                    "url": "",
                }
            ],
            "run_id": str(uuid.uuid4()),
            "provider": "openai",
            "model": "gpt-test",
        },
    )

    monkeypatch.setattr(
        "app.services.provider_settings_service.normalize_provider",
        lambda provider: provider,
    )
    monkeypatch.setattr(
        "app.services.provider_settings_service.resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    monkeypatch.setattr(
        report_service,
        "_call_llm_json",
        lambda **kwargs: """
        {
          "overview": "The team should complete one critical follow-up.",
          "items": [
            {
              "title": "Review roadmap",
              "description": "Alice should review the roadmap and share blockers.",
              "priority": "high",
              "owner_suggested": "Alice",
              "due_date_suggested": "before Friday",
              "status": "open",
              "citation_indexes": [1]
            }
          ]
        }
        """,
    )

    result = report_service.generate_report(
        db=db_session,
        project_id=project.id,
        query="What should the team do next?",
        report_type="action_items",
        format="markdown",
        provider="openai",
    )

    assert result["type"] == "action_items"
    assert result["structured_payload"]["overview"] == "The team should complete one critical follow-up."
    assert result["structured_payload"]["items"][0]["title"] == "Review roadmap"
    assert result["structured_payload"]["items"][0]["citations"][0]["chunk_id"] == str(chunk.id)
    assert "## Action Items" in result["content"]

    persisted = db_session.get(Report, uuid.UUID(result["report_id"]))
    assert persisted is not None
    assert persisted.structured_payload is not None
    assert persisted.structured_payload["items"][0]["owner_suggested"] == "Alice"


def test_update_action_item_status_updates_payload_and_markdown(db_session):
    project = Project(name="Action item status", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    report = Report(
        project_id=project.id,
        query="What should the team do next?",
        title="Action Items: Launch checklist",
        report_type="action_items",
        format="markdown",
        content="# Action Items",
        structured_payload={
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
        status="completed",
        run_id=None,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    updated = report_service.update_action_item_status(
        db=db_session,
        report_id=report.id,
        item_id="item-1",
        status="done",
    )

    assert updated["query"] == "What should the team do next?"
    assert updated["structured_payload"]["items"][0]["status"] == "done"
    assert "Status: done" in updated["content"]
