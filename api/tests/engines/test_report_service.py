import uuid

from app.services import report_service
from app.storage.models import Chunk, Document, ProcessingRun, Project, Report, Source


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
                    "quote": chunk.content,
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

    run = db_session.get(ProcessingRun, uuid.UUID(result["run_id"]))
    assert run is not None
    assert run.run_metadata["evidence_snapshot"][0]["chunk_id"] == str(chunk.id)
    assert run.run_metadata["evidence_snapshot"][0]["quote_preview"] == chunk.content


def test_generate_flashcards_report_uses_all_indexed_chunks(db_session, monkeypatch):
    project = Project(name="Flashcard Project", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="chapter.pptx",
        storage_path="data/uploads/chapter.pptx",
        checksum="flashcards-1",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Chapter Deck",
        raw_path=source.storage_path,
        clean_text="Definition content. Method content. Meaning content.",
        token_count=42,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunks = []
    for index, content in enumerate(
        [
            "Slide 1 defines the main concept.",
            "Slide 2 explains the research method.",
            "Slide 3 states the learning meaning.",
        ]
    ):
        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=document.id,
            chunk_index=index,
            content=content,
            chroma_id=str(uuid.uuid4()),
            embedding_model=report_service.LOCAL_EMBEDDING_MODEL,
            chunk_metadata={
                "source_id": str(source.id),
                "document_id": str(document.id),
                "page_number": index + 1,
            },
        )
        chunks.append(chunk)
    db_session.add_all(chunks)
    db_session.commit()

    monkeypatch.setattr(
        report_service,
        "generate_insight",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("flashcards must not use insight top-k")),
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
    prompts: list[str] = []

    def fake_flashcards_json(**kwargs):
        prompts.append(kwargs["prompt"])
        return """
        {
          "overview": "A study deck for the chapter.",
          "cards": [
            {
              "front": "What does slide 1 define?",
              "back": "The main concept.",
              "explanation": "Slide 1 defines the main concept.",
              "difficulty": "easy",
              "tags": ["concept"],
              "citation_indexes": [1]
            },
            {
              "front": "What does slide 2 explain?",
              "back": "The research method.",
              "explanation": "Slide 2 explains the research method.",
              "difficulty": "medium",
              "tags": ["method"],
              "citation_indexes": [2]
            },
            {
              "front": "What does slide 3 state?",
              "back": "The learning meaning.",
              "explanation": "Slide 3 states the learning meaning.",
              "difficulty": "medium",
              "tags": ["meaning"],
              "citation_indexes": [3]
            }
          ]
        }
        """

    monkeypatch.setattr(report_service, "_call_llm_json", fake_flashcards_json)

    result = report_service.generate_report(
        db=db_session,
        project_id=project.id,
        query="Create flashcards from all documents",
        report_type="flashcards",
        format="markdown",
        provider="openai",
    )

    assert result["type"] == "flashcards"
    assert len(result["structured_payload"]["cards"]) == 3
    assert result["structured_payload"]["cards"][0]["citations"][0]["chunk_id"] == str(chunks[0].id)
    assert "## Cards" in result["content"]
    assert prompts
    assert "Slide 1 defines" in prompts[0]
    assert "Slide 2 explains" in prompts[0]
    assert "Slide 3 states" in prompts[0]

    persisted = db_session.get(Report, uuid.UUID(result["report_id"]))
    assert persisted is not None
    assert persisted.structured_payload["cards"][1]["front"] == "What does slide 2 explain?"

    run = db_session.get(ProcessingRun, uuid.UUID(result["run_id"]))
    assert run is not None
    assert run.run_metadata["indexed_chunk_count"] == 3
    assert run.run_metadata["generated_card_count"] == 3


def test_generate_flashcards_report_falls_back_on_malformed_json(db_session, monkeypatch):
    project = Project(name="Fallback Flashcards", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="fallback.pdf",
        storage_path="data/uploads/fallback.pdf",
        checksum="flashcards-2",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Fallback Source",
        raw_path=source.storage_path,
        clean_text="Fallback content.",
        token_count=12,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=0,
        content="Fallback content should still become a flashcard.",
        chroma_id=str(uuid.uuid4()),
        embedding_model=report_service.LOCAL_EMBEDDING_MODEL,
        chunk_metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    db_session.add(chunk)
    db_session.commit()

    monkeypatch.setattr("app.services.provider_settings_service.normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        "app.services.provider_settings_service.resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    monkeypatch.setattr(report_service, "_call_llm_json", lambda **kwargs: "not json")

    result = report_service.generate_report(
        db=db_session,
        project_id=project.id,
        query="Create flashcards",
        report_type="flashcards",
        format="markdown",
        provider="openai",
    )

    card = result["structured_payload"]["cards"][0]
    assert card["front"].startswith("What is the key point")
    assert card["citations"][0]["chunk_id"] == str(chunk.id)


def test_generate_quiz_report_uses_all_indexed_chunks(db_session, monkeypatch):
    project = Project(name="Quiz Project", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="quiz-chapter.pptx",
        storage_path="data/uploads/quiz-chapter.pptx",
        checksum="quiz-1",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Quiz Chapter",
        raw_path=source.storage_path,
        clean_text="Concept content. Method content. Meaning content.",
        token_count=42,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunks = []
    for index, content in enumerate(
        [
            "Slide 1 defines the central concept.",
            "Slide 2 explains the main method.",
            "Slide 3 states why the lesson matters.",
        ]
    ):
        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=document.id,
            chunk_index=index,
            content=content,
            chroma_id=str(uuid.uuid4()),
            embedding_model=report_service.LOCAL_EMBEDDING_MODEL,
            chunk_metadata={
                "source_id": str(source.id),
                "document_id": str(document.id),
                "page_number": index + 1,
            },
        )
        chunks.append(chunk)
    db_session.add_all(chunks)
    db_session.commit()

    monkeypatch.setattr(
        report_service,
        "generate_insight",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("quiz must not use insight top-k")),
    )
    monkeypatch.setattr("app.services.provider_settings_service.normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        "app.services.provider_settings_service.resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    prompts: list[str] = []

    def fake_quiz_json(**kwargs):
        prompts.append(kwargs["prompt"])
        return """
        {
          "overview": "A source-grounded quiz.",
          "questions": [
            {
              "type": "multiple_choice",
              "question": "What does slide 1 define?",
              "options": [
                {"id": "a", "text": "The central concept"},
                {"id": "b", "text": "A due date"},
                {"id": "c", "text": "A budget"},
                {"id": "d", "text": "A risk"}
              ],
              "correct_option_id": "a",
              "explanation": "Slide 1 defines the central concept.",
              "difficulty": "easy",
              "tags": ["concept"],
              "citation_indexes": [1]
            },
            {
              "type": "true_false",
              "question": "Slide 2 explains the main method.",
              "options": [
                {"id": "true", "text": "True"},
                {"id": "false", "text": "False"}
              ],
              "correct_option_id": "true",
              "explanation": "Slide 2 explains the main method.",
              "difficulty": "medium",
              "tags": ["method"],
              "citation_indexes": [2]
            },
            {
              "type": "multiple_choice",
              "question": "What does slide 3 state?",
              "options": [
                {"id": "a", "text": "Why the lesson matters"},
                {"id": "b", "text": "The author biography"},
                {"id": "c", "text": "The file name only"},
                {"id": "d", "text": "A contradiction"}
              ],
              "correct_option_id": "a",
              "explanation": "Slide 3 states why the lesson matters.",
              "difficulty": "medium",
              "tags": ["meaning"],
              "citation_indexes": [3]
            }
          ]
        }
        """

    monkeypatch.setattr(report_service, "_call_llm_json", fake_quiz_json)

    result = report_service.generate_report(
        db=db_session,
        project_id=project.id,
        query="Create a quiz from all documents",
        report_type="quiz",
        format="markdown",
        provider="openai",
    )

    assert result["type"] == "quiz"
    questions = result["structured_payload"]["questions"]
    assert len(questions) == 3
    assert questions[0]["type"] == "multiple_choice"
    assert questions[1]["type"] == "true_false"
    assert questions[0]["citations"][0]["chunk_id"] == str(chunks[0].id)
    assert "## Questions" in result["content"]
    assert prompts
    assert "Slide 1 defines" in prompts[0]
    assert "Slide 2 explains" in prompts[0]
    assert "Slide 3 states" in prompts[0]

    persisted = db_session.get(Report, uuid.UUID(result["report_id"]))
    assert persisted is not None
    assert persisted.structured_payload["questions"][1]["correct_option_id"] == "true"

    run = db_session.get(ProcessingRun, uuid.UUID(result["run_id"]))
    assert run is not None
    assert run.run_metadata["indexed_chunk_count"] == 3
    assert run.run_metadata["generated_question_count"] == 3


def test_generate_quiz_report_falls_back_on_malformed_json(db_session, monkeypatch):
    project = Project(name="Fallback Quiz", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="quiz-fallback.pdf",
        storage_path="data/uploads/quiz-fallback.pdf",
        checksum="quiz-2",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Quiz Fallback Source",
        raw_path=source.storage_path,
        clean_text="Fallback quiz content.",
        token_count=12,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=0,
        content="Fallback quiz content should still become a question.",
        chroma_id=str(uuid.uuid4()),
        embedding_model=report_service.LOCAL_EMBEDDING_MODEL,
        chunk_metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    db_session.add(chunk)
    db_session.commit()

    monkeypatch.setattr("app.services.provider_settings_service.normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        "app.services.provider_settings_service.resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    monkeypatch.setattr(report_service, "_call_llm_json", lambda **kwargs: "not json")

    result = report_service.generate_report(
        db=db_session,
        project_id=project.id,
        query="Create quiz",
        report_type="quiz",
        format="markdown",
        provider="openai",
    )

    question = result["structured_payload"]["questions"][0]
    assert question["question"].startswith("What is a key point")
    assert question["correct_option_id"] == "a"
    assert question["citations"][0]["chunk_id"] == str(chunk.id)


def test_generate_study_guide_report_uses_all_indexed_chunks(db_session, monkeypatch):
    project = Project(name="Study Guide Project", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="study-guide-chapter.pptx",
        storage_path="data/uploads/study-guide-chapter.pptx",
        checksum="study-guide-1",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Study Guide Chapter",
        raw_path=source.storage_path,
        clean_text="Concept content. Timeline content. Review content.",
        token_count=42,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunks = []
    for index, content in enumerate(
        [
            "Slide 1 introduces the chapter concept.",
            "Slide 2 explains a historical stage.",
            "Slide 3 gives a review-worthy conclusion.",
        ]
    ):
        chunk = Chunk(
            id=uuid.uuid4(),
            document_id=document.id,
            chunk_index=index,
            content=content,
            chroma_id=str(uuid.uuid4()),
            embedding_model=report_service.LOCAL_EMBEDDING_MODEL,
            chunk_metadata={
                "source_id": str(source.id),
                "document_id": str(document.id),
                "page_number": index + 1,
            },
        )
        chunks.append(chunk)
    db_session.add_all(chunks)
    db_session.commit()

    monkeypatch.setattr(
        report_service,
        "generate_insight",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("study guide must not use insight top-k")),
    )
    monkeypatch.setattr("app.services.provider_settings_service.normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        "app.services.provider_settings_service.resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    prompts: list[str] = []

    def fake_study_guide_json(**kwargs):
        prompts.append(kwargs["prompt"])
        return """
        {
          "overview": "A source-grounded study guide.",
          "sections": [
            {
              "title": "Chapter concept",
              "summary": "Slide 1 introduces the chapter concept.",
              "key_points": ["The chapter concept is introduced."],
              "citation_indexes": [1]
            }
          ],
          "key_concepts": [
            {
              "term": "Historical stage",
              "definition": "Slide 2 explains a historical stage.",
              "importance": "It organizes the chapter in sequence.",
              "citation_indexes": [2]
            }
          ],
          "timeline": [
            {
              "label": "Historical stage",
              "description": "Slide 2 explains this stage.",
              "citation_indexes": [2]
            }
          ],
          "review_questions": [
            {
              "question": "What conclusion should learners review?",
              "answer": "Slide 3 gives a review-worthy conclusion.",
              "citation_indexes": [3]
            }
          ]
        }
        """

    monkeypatch.setattr(report_service, "_call_llm_json", fake_study_guide_json)

    result = report_service.generate_report(
        db=db_session,
        project_id=project.id,
        query="Create a study guide from all documents",
        report_type="study_guide",
        format="markdown",
        provider="openai",
    )

    assert result["type"] == "study_guide"
    payload = result["structured_payload"]
    assert payload["sections"][0]["citations"][0]["chunk_id"] == str(chunks[0].id)
    assert payload["key_concepts"][0]["citations"][0]["chunk_id"] == str(chunks[1].id)
    assert payload["timeline"][0]["citations"][0]["chunk_id"] == str(chunks[1].id)
    assert payload["review_questions"][0]["citations"][0]["chunk_id"] == str(chunks[2].id)
    assert "## Sections" in result["content"]
    assert "## Key Concepts" in result["content"]
    assert "## Timeline" in result["content"]
    assert "## Review Questions" in result["content"]
    assert prompts
    assert "Slide 1 introduces" in prompts[0]
    assert "Slide 2 explains" in prompts[0]
    assert "Slide 3 gives" in prompts[0]

    persisted = db_session.get(Report, uuid.UUID(result["report_id"]))
    assert persisted is not None
    assert persisted.structured_payload["sections"][0]["title"] == "Chapter concept"

    run = db_session.get(ProcessingRun, uuid.UUID(result["run_id"]))
    assert run is not None
    assert run.run_metadata["indexed_chunk_count"] == 3
    assert run.run_metadata["generated_section_count"] == 1
    assert run.run_metadata["generated_concept_count"] == 1
    assert run.run_metadata["generated_timeline_count"] == 1
    assert run.run_metadata["generated_review_question_count"] == 1


def test_generate_study_guide_report_falls_back_on_malformed_json(db_session, monkeypatch):
    project = Project(name="Fallback Study Guide", description="test")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    source = Source(
        project_id=project.id,
        type="file",
        original_uri="study-guide-fallback.pdf",
        storage_path="data/uploads/study-guide-fallback.pdf",
        checksum="study-guide-2",
        status="completed",
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)

    document = Document(
        source_id=source.id,
        title="Study Guide Fallback Source",
        raw_path=source.storage_path,
        clean_text="Fallback study guide content.",
        token_count=12,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        chunk_index=0,
        content="Fallback study guide content should still become a guide.",
        chroma_id=str(uuid.uuid4()),
        embedding_model=report_service.LOCAL_EMBEDDING_MODEL,
        chunk_metadata={"source_id": str(source.id), "document_id": str(document.id)},
    )
    db_session.add(chunk)
    db_session.commit()

    monkeypatch.setattr("app.services.provider_settings_service.normalize_provider", lambda provider: provider)
    monkeypatch.setattr(
        "app.services.provider_settings_service.resolve_chat_provider_config",
        lambda db, project_id, provider: {
            "api_key": "test-key",
            "base_url": None,
            "chat_model": "gpt-test",
        },
    )
    monkeypatch.setattr(report_service, "_call_llm_json", lambda **kwargs: "not json")

    result = report_service.generate_report(
        db=db_session,
        project_id=project.id,
        query="Create study guide",
        report_type="study_guide",
        format="markdown",
        provider="openai",
    )

    payload = result["structured_payload"]
    assert payload["sections"][0]["title"] == "Study Guide Fallback Source"
    assert payload["review_questions"][0]["question"].startswith("What is a key point")
    assert payload["sections"][0]["citations"][0]["chunk_id"] == str(chunk.id)


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
