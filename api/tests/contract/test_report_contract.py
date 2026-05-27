import uuid

from app.api.routes import reports as report_route_module
from app.storage.models import (
    Chunk,
    Document,
    Insight,
    InsightCitation,
    ProcessingRun,
    QuizAttempt,
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


def test_generate_flashcards_report_returns_structured_payload(client, monkeypatch):
    project = _create_project(client)

    monkeypatch.setattr(
        report_route_module,
        "generate_report",
        lambda **kwargs: {
            "report_id": "report-flashcards",
            "query": "Create flashcards",
            "title": "Flashcards: Create flashcards",
            "type": "flashcards",
            "format": "markdown",
            "content": "# Flashcards\n\n## Cards",
            "structured_payload": {
                "overview": "One study deck was generated.",
                "cards": [
                    {
                        "id": "card-1",
                        "front": "What is the main concept?",
                        "back": "The main concept is source-grounded.",
                        "explanation": "The answer comes from indexed evidence.",
                        "difficulty": "easy",
                        "tags": ["concept"],
                        "citations": [],
                    }
                ],
            },
            "status": "completed",
            "run_id": "run-1",
            "source_ids": [],
            "citations": [],
        },
    )

    response = client.post(
        "/api/v1/reports/generate",
        json={
            "project_id": project["id"],
            "query": "Create flashcards",
            "type": "flashcards",
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["type"] == "flashcards"
    assert body["data"]["structured_payload"]["cards"][0]["front"] == "What is the main concept?"


def test_generate_quiz_report_returns_structured_payload(client, monkeypatch):
    project = _create_project(client)

    monkeypatch.setattr(
        report_route_module,
        "generate_report",
        lambda **kwargs: {
            "report_id": "report-quiz",
            "query": "Create quiz",
            "title": "Quiz: Create quiz",
            "type": "quiz",
            "format": "markdown",
            "content": "# Quiz\n\n## Questions",
            "structured_payload": {
                "overview": "One quiz was generated.",
                "questions": [
                    {
                        "id": "question-1",
                        "type": "multiple_choice",
                        "question": "What is the main concept?",
                        "options": [
                            {"id": "a", "text": "The source-grounded concept"},
                            {"id": "b", "text": "Unsupported option"},
                            {"id": "c", "text": "Another unsupported option"},
                            {"id": "d", "text": "A contradiction"},
                        ],
                        "correct_option_id": "a",
                        "explanation": "The answer comes from indexed evidence.",
                        "difficulty": "easy",
                        "tags": ["concept"],
                        "citations": [],
                    }
                ],
            },
            "status": "completed",
            "run_id": "run-1",
            "source_ids": [],
            "citations": [],
        },
    )

    response = client.post(
        "/api/v1/reports/generate",
        json={
            "project_id": project["id"],
            "query": "Create quiz",
            "type": "quiz",
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["type"] == "quiz"
    assert body["data"]["structured_payload"]["questions"][0]["question"] == "What is the main concept?"


def test_generate_study_guide_report_returns_structured_payload(client, monkeypatch):
    project = _create_project(client)

    monkeypatch.setattr(
        report_route_module,
        "generate_report",
        lambda **kwargs: {
            "report_id": "report-study-guide",
            "query": "Create study guide",
            "title": "Study Guide: Create study guide",
            "type": "study_guide",
            "format": "markdown",
            "content": "# Study Guide\n\n## Sections",
            "structured_payload": {
                "overview": "One study guide was generated.",
                "sections": [
                    {
                        "id": "section-1",
                        "title": "Main topic",
                        "summary": "The source-grounded topic.",
                        "key_points": ["The topic is important."],
                        "citations": [],
                    }
                ],
                "key_concepts": [],
                "timeline": [],
                "review_questions": [],
            },
            "status": "completed",
            "run_id": "run-1",
            "source_ids": [],
            "citations": [],
        },
    )

    response = client.post(
        "/api/v1/reports/generate",
        json={
            "project_id": project["id"],
            "query": "Create study guide",
            "type": "study_guide",
            "provider": "openai",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["type"] == "study_guide"
    assert body["data"]["structured_payload"]["sections"][0]["title"] == "Main topic"


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


def test_get_flashcards_report_hydrates_card_citations(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])

    source = Source(
        project_id=project_id,
        type="file",
        original_uri="deck.pdf",
        storage_path="data/uploads/deck.pdf",
        checksum="flashcard-contract",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Deck",
        raw_path=source.storage_path,
        clean_text="The indexed fact.",
        token_count=8,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="The indexed fact supports the flashcard answer.",
        chroma_id=str(uuid.uuid4()),
        embedding_model="local-test-model",
        chunk_metadata={"page_number": 4},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    report = Report(
        project_id=project_id,
        query="Create flashcards",
        title="Flashcards: Create flashcards",
        report_type="flashcards",
        format="markdown",
        content="# Flashcards",
        structured_payload={
            "overview": "One study deck.",
            "cards": [
                {
                    "id": "card-1",
                    "front": "What supports the answer?",
                    "back": "The indexed fact.",
                    "explanation": "The fact appears in the indexed source.",
                    "difficulty": "easy",
                    "tags": ["fact"],
                    "citations": [{"chunk_id": str(chunk.id)}],
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
    card = response.json()["data"]["structured_payload"]["cards"][0]
    assert card["citations"][0]["chunk_id"] == str(chunk.id)
    assert card["citations"][0]["title"] == "Deck"
    assert card["citations"][0]["page_number"] == 4


def test_get_quiz_report_hydrates_question_citations(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])

    source = Source(
        project_id=project_id,
        type="file",
        original_uri="quiz-deck.pdf",
        storage_path="data/uploads/quiz-deck.pdf",
        checksum="quiz-contract",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Quiz Deck",
        raw_path=source.storage_path,
        clean_text="The indexed quiz fact.",
        token_count=8,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="The indexed quiz fact supports the quiz answer.",
        chroma_id=str(uuid.uuid4()),
        embedding_model="local-test-model",
        chunk_metadata={"page_number": 5},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    report = Report(
        project_id=project_id,
        query="Create quiz",
        title="Quiz: Create quiz",
        report_type="quiz",
        format="markdown",
        content="# Quiz",
        structured_payload={
            "overview": "One quiz.",
            "questions": [
                {
                    "id": "question-1",
                    "type": "true_false",
                    "question": "The indexed fact supports the answer.",
                    "options": [
                        {"id": "true", "text": "True"},
                        {"id": "false", "text": "False"},
                    ],
                    "correct_option_id": "true",
                    "explanation": "The fact appears in the indexed source.",
                    "difficulty": "easy",
                    "tags": ["fact"],
                    "citations": [{"chunk_id": str(chunk.id)}],
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
    question = response.json()["data"]["structured_payload"]["questions"][0]
    assert question["citations"][0]["chunk_id"] == str(chunk.id)
    assert question["citations"][0]["title"] == "Quiz Deck"
    assert question["citations"][0]["page_number"] == 5


def test_get_study_guide_report_hydrates_nested_citations(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])

    source = Source(
        project_id=project_id,
        type="file",
        original_uri="study-guide-deck.pdf",
        storage_path="data/uploads/study-guide-deck.pdf",
        checksum="study-guide-contract",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Study Guide Deck",
        raw_path=source.storage_path,
        clean_text="The indexed study guide fact.",
        token_count=8,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="The indexed study guide fact supports each guide item.",
        chroma_id=str(uuid.uuid4()),
        embedding_model="local-test-model",
        chunk_metadata={"page_number": 6},
    )
    db_session.add(chunk)
    db_session.commit()
    db_session.refresh(chunk)

    citation = {"chunk_id": str(chunk.id)}
    report = Report(
        project_id=project_id,
        query="Create study guide",
        title="Study Guide: Create study guide",
        report_type="study_guide",
        format="markdown",
        content="# Study Guide",
        structured_payload={
            "overview": "One guide.",
            "sections": [
                {
                    "id": "section-1",
                    "title": "Section",
                    "summary": "A supported section.",
                    "key_points": ["A supported point."],
                    "citations": [citation],
                }
            ],
            "key_concepts": [
                {
                    "id": "concept-1",
                    "term": "Concept",
                    "definition": "A supported definition.",
                    "importance": "A supported importance.",
                    "citations": [citation],
                }
            ],
            "timeline": [
                {
                    "id": "timeline-1",
                    "label": "Stage",
                    "description": "A supported stage.",
                    "citations": [citation],
                }
            ],
            "review_questions": [
                {
                    "id": "review-1",
                    "question": "What is supported?",
                    "answer": "The indexed fact.",
                    "citations": [citation],
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
    payload = response.json()["data"]["structured_payload"]
    assert payload["sections"][0]["citations"][0]["title"] == "Study Guide Deck"
    assert payload["key_concepts"][0]["citations"][0]["chunk_id"] == str(chunk.id)
    assert payload["timeline"][0]["citations"][0]["page_number"] == 6
    assert payload["review_questions"][0]["citations"][0]["title"] == "Study Guide Deck"


def test_create_and_list_quiz_attempts_scores_answers(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])
    report = Report(
        project_id=project_id,
        query="Create quiz",
        title="Quiz: Create quiz",
        report_type="quiz",
        format="markdown",
        content="# Quiz",
        structured_payload={
            "overview": "One quiz.",
            "questions": [
                {
                    "id": "question-1",
                    "type": "multiple_choice",
                    "question": "What is correct?",
                    "options": [
                        {"id": "a", "text": "Correct"},
                        {"id": "b", "text": "Wrong"},
                        {"id": "c", "text": "Wrong"},
                        {"id": "d", "text": "Wrong"},
                    ],
                    "correct_option_id": "a",
                    "explanation": "A is supported.",
                    "difficulty": "easy",
                    "tags": [],
                    "citations": [],
                },
                {
                    "id": "question-2",
                    "type": "true_false",
                    "question": "The claim is true.",
                    "options": [
                        {"id": "true", "text": "True"},
                        {"id": "false", "text": "False"},
                    ],
                    "correct_option_id": "true",
                    "explanation": "The source says so.",
                    "difficulty": "medium",
                    "tags": [],
                    "citations": [],
                },
            ],
        },
        status="completed",
        run_id=None,
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    response = client.post(
        f"/api/v1/reports/{report.id}/quiz-attempts",
        json={"answers": {"question-1": "a", "question-2": "false"}},
    )

    assert response.status_code == 201
    created = response.json()["data"]
    assert created["score_correct"] == 1
    assert created["score_total"] == 2
    assert created["score_percent"] == 50
    assert created["answers"]["question-2"] == "false"

    persisted = db_session.get(QuizAttempt, uuid.UUID(created["attempt_id"]))
    assert persisted is not None
    assert persisted.score_correct == 1

    list_response = client.get(f"/api/v1/reports/{report.id}/quiz-attempts")
    assert list_response.status_code == 200
    listed = list_response.json()["data"]
    assert listed["total"] == 1
    assert listed["items"][0]["attempt_id"] == created["attempt_id"]


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


def test_report_quality_scores_citation_fidelity_and_snapshots(client, db_session):
    project = _create_project(client)
    project_id = uuid.UUID(project["id"])

    source = Source(
        project_id=project_id,
        type="file",
        original_uri="quality.pdf",
        storage_path="data/uploads/quality.pdf",
        checksum="quality",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Quality Evidence",
        raw_path=source.storage_path,
        clean_text="The quality evidence supports a launch owner.",
        token_count=8,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        document_id=document.id,
        chunk_index=0,
        content="The quality evidence supports a launch owner.",
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
        run_metadata={
            "query": "Who owns launch?",
            "evidence_snapshot": [
                {
                    "chunk_id": str(chunk.id),
                    "quote_preview": "The quality evidence supports a launch owner.",
                }
            ],
        },
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(chunk)
    db_session.refresh(run)

    insight = Insight(
        project_id=project_id,
        query="Who owns launch?",
        summary="Launch ownership is supported.",
        findings=[],
        provider="openai",
        model_id="gpt-test",
        run_id=run.id,
        status="completed",
    )
    db_session.add(insight)
    db_session.commit()
    db_session.refresh(insight)

    citation_payload = {
        "citation_id": str(chunk.id),
        "source_id": str(source.id),
        "source_type": "file",
        "document_id": str(document.id),
        "chunk_id": str(chunk.id),
        "title": "Quality Evidence",
    }
    citation = InsightCitation(
        insight_id=insight.id,
        source_id=str(source.id),
        source_type="file",
        document_id=str(document.id),
        chunk_id=str(chunk.id),
        title="Quality Evidence",
        url="",
    )
    report = Report(
        project_id=project_id,
        query="Who owns launch?",
        title="Action Items: Quality Evidence",
        report_type="action_items",
        format="markdown",
        content="# Action Items",
        structured_payload={
            "overview": "One action is grounded.",
            "items": [
                {
                    "id": "item-1",
                    "title": "Assign launch owner",
                    "description": "Confirm the owner.",
                    "priority": "high",
                    "owner_suggested": "Ops",
                    "due_date_suggested": None,
                    "status": "open",
                    "citations": [citation_payload],
                }
            ],
        },
        status="completed",
        run_id=run.id,
    )
    db_session.add_all([citation, report])
    db_session.commit()
    db_session.refresh(report)

    db_session.add(ReportInsight(report_id=report.id, insight_id=insight.id))
    db_session.commit()

    response = client.get(f"/api/v1/reports/{report.id}/quality")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] in {"pass", "warning"}
    assert data["metrics"]["citation_count"] == 1
    assert data["metrics"]["items_with_citations"] == 1
    assert data["metrics"]["missing_quote_count"] == 0
    assert data["scores"]["citation_fidelity"] == 1.0
    assert data["checks"][0]["code"] == "citation_coverage"


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
