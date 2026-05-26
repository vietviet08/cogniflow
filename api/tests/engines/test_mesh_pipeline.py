import uuid

from app.engines.report import mesh_pipeline
from app.services.insight_service import InsightError
from app.storage.models import Chunk, Document, Insight, Project, Report, Source


def test_conflict_mesh_falls_back_to_all_project_sources(db_session, monkeypatch):
    project = Project(name="Chapter graph", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    for filename in ["chuong 2.pdf", "chuong 1.pdf", "chuong 3.pdf"]:
        db_session.add(
            Source(
                project_id=project.id,
                type="file",
                original_uri=filename,
                status="completed",
            )
        )
    db_session.commit()

    insight = Insight(
        id=uuid.uuid4(),
        project_id=project.id,
        query="tạo graph mối quan hệ giữa 3 chương",
        summary="No indexed chunks were available.",
        findings=[],
        provider="openai",
        model_id="gpt-test",
        status="completed",
    )
    db_session.add(insight)
    db_session.commit()

    monkeypatch.setattr(
        mesh_pipeline,
        "generate_insight",
        lambda **kwargs: {
            "insight_id": str(insight.id),
            "summary": insight.summary,
            "findings": [],
            "citations": [],
            "run_id": str(uuid.uuid4()),
            "provider": "openai",
            "model": "gpt-test",
        },
    )
    monkeypatch.setattr(mesh_pipeline, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        mesh_pipeline,
        "resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    monkeypatch.setattr(
        mesh_pipeline,
        "_call_llm_json",
        lambda **kwargs: "not valid json",
    )

    result = mesh_pipeline.generate_conflict_mesh(
        db=db_session,
        project_id=project.id,
        query="tạo graph mối quan hệ giữa 3 chương",
        provider="openai",
    )

    payload = result["structured_payload"]
    assert [node["label"] for node in payload["nodes"]] == [
        "chuong 1",
        "chuong 2",
        "chuong 3",
    ]
    assert len(payload["edges"]) == 2
    assert payload["edges"][0]["source"] == payload["nodes"][0]["id"]
    assert payload["edges"][0]["target"] == payload["nodes"][1]["id"]

    persisted = db_session.get(Report, uuid.UUID(result["report_id"]))
    assert persisted is not None
    assert persisted.structured_payload["nodes"] == payload["nodes"]


def test_conflict_mesh_parses_fenced_json_and_merges_source_nodes(db_session, monkeypatch):
    project = Project(name="Parsed mesh", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="chuong 1.pdf",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()

    insight = Insight(
        id=uuid.uuid4(),
        project_id=project.id,
        query="mesh",
        summary="Parsed evidence.",
        findings=[],
        provider="openai",
        model_id="gpt-test",
        status="completed",
    )
    db_session.add(insight)
    db_session.commit()

    monkeypatch.setattr(
        mesh_pipeline,
        "generate_insight",
        lambda **kwargs: {
            "insight_id": str(insight.id),
            "summary": insight.summary,
            "findings": [],
            "citations": [],
            "run_id": str(uuid.uuid4()),
            "provider": "openai",
            "model": "gpt-test",
        },
    )
    monkeypatch.setattr(mesh_pipeline, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        mesh_pipeline,
        "resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    monkeypatch.setattr(
        mesh_pipeline,
        "_call_llm_json",
        lambda **kwargs: """
        Here is the graph:
        ```json
        {
          "overview": "Parsed graph.",
          "nodes": [{"id": "concept-a", "label": "Concept A", "type": "concept"}],
          "edges": []
        }
        ```
        """,
    )

    result = mesh_pipeline.generate_conflict_mesh(
        db=db_session,
        project_id=project.id,
        query="mesh",
        provider="openai",
    )

    payload = result["structured_payload"]
    assert payload["overview"] == "Parsed graph."
    assert {node["label"] for node in payload["nodes"]} == {"Concept A", "chuong 1"}


def test_conflict_mesh_creates_source_graph_when_insight_fails(db_session, monkeypatch):
    project = Project(name="Offline graph", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    for filename in ["chuong 1.pdf", "chuong 2.pdf"]:
        source = Source(
            project_id=project.id,
            type="file",
            original_uri=filename,
            status="completed",
        )
        db_session.add(source)
        db_session.flush()
        document = Document(
            source_id=source.id,
            title=filename,
            raw_path=None,
            clean_text="indexed slide text",
            token_count=3,
        )
        db_session.add(document)
        db_session.flush()
        db_session.add(
            Chunk(
                document_id=document.id,
                chunk_index=0,
                content=f"{filename} indexed content",
                chroma_id=f"chunk-{source.id}",
                embedding_model="local",
                chunk_metadata={"page_number": 1},
            )
        )
    db_session.commit()

    def raise_insight_error(**kwargs):
        raise InsightError(
            "OpenAI request failed during insight generation.",
            code="INSIGHT_UPSTREAM_ERROR",
            status_code=502,
            details={"reason": "402 insufficient balance"},
        )

    monkeypatch.setattr(mesh_pipeline, "generate_insight", raise_insight_error)
    monkeypatch.setattr(mesh_pipeline, "normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        mesh_pipeline,
        "resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )

    result = mesh_pipeline.generate_conflict_mesh(
        db=db_session,
        project_id=project.id,
        query="tạo graph",
        provider="openai",
    )

    payload = result["structured_payload"]
    assert result["fallback"] is True
    assert [node["label"] for node in payload["nodes"]] == ["chuong 1", "chuong 2"]
    assert len(payload["edges"]) == 1
    assert payload["edges"][0]["citations"]
    assert result["citations"]
