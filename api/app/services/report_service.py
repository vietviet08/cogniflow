"""Report service: assemble a research report from insight synthesis."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
import uuid
from typing import Any, Iterable

import google.genai as genai
from openai import OpenAI
from sqlalchemy.orm import Session

from app.services.citation_service import hydrate_citations, hydrate_report_payload_citations
from app.services.embedding_service import LOCAL_EMBEDDING_MODEL
from app.services.insight_service import InsightError, generate_insight
from app.services.query_service import ensure_project_sources_indexed
from app.storage.models import Chunk, Document, QuizAttempt, Report, ReportInsight, Source
from app.storage.repositories.processing_run_repository import ProcessingRunRepository
from app.storage.repositories.report_repository import ReportRepository


class ReportError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "REPORT_FAILED",
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


# ---------------------------------------------------------------------------
# Report prompt templates
# ---------------------------------------------------------------------------

_REPORT_PROMPT_TEMPLATE = """\
You are a research writer. Based on the analysis below, write a {report_type} report.
Format the output as clean Markdown with headings, bullet points, and a citations section.

Report type description:
- research_brief: Executive summary and key findings (1-2 pages)
- summary: Concise bullet-point overview of the main themes
- comparison: Side-by-side comparison of different perspectives found in the evidence

Query / topic: {query}

Structured analysis:
{analysis}

Instructions:
- Start with a # Title
- Include ## Executive Summary
- Include ## Key Findings (use the themes from the analysis)
- Include ## Sources Consulted listing the unique source titles
- Keep the report factual and grounded in the evidence provided.
"""

_ACTION_ITEMS_PROMPT_TEMPLATE = """\
You are an operations analyst. Based ONLY on the evidence below, generate actionable follow-ups.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short overview>",
  "items": [
    {{
      "title": "<action title>",
      "description": "<what should be done and why>",
      "priority": "high|medium|low",
      "owner_suggested": "<team or role, or empty string>",
      "due_date_suggested": "<date or time hint if explicitly supported, else empty string>",
      "status": "open|needs_review|done",
      "citation_indexes": [1, 2]
    }}
  ]
}}

Rules:
- Use only the evidence below. Do not invent details.
- Produce 3-7 action items when evidence supports it.
- Each item must include at least one citation index from the evidence list.
- If due dates or owners are not explicit, use empty string.
- If evidence is weak, mark status as "needs_review".

User request: {query}

Structured analysis:
{analysis}

Evidence:
{evidence}
"""

_RISK_ANALYSIS_PROMPT_TEMPLATE = """\
You are a risk reviewer. Based ONLY on the evidence below, identify practical risks and what to do next.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short overall risk overview>",
  "items": [
    {{
      "title": "<risk title>",
      "severity": "high|medium|low",
      "why_it_matters": "<impact and evidence-backed explanation>",
      "recommended_action": "<practical next step>",
      "status": "open|needs_review|accepted",
      "citation_indexes": [1, 2]
    }}
  ]
}}

Rules:
- Use only the evidence below.
- Produce 3-6 risks when supported by the evidence.
- Each item must include at least one citation index.
- If risk severity is unclear, use "needs_review" and conservative wording.

User request: {query}

Structured analysis:
{analysis}

Evidence:
{evidence}
"""

_EXECUTIVE_BRIEF_PROMPT_TEMPLATE = """\
You are writing an executive brief for a busy team lead.

Return a JSON object with EXACTLY this shape:
{{
  "summary": "<2-3 sentence summary>",
  "key_points": ["<point 1>", "<point 2>"],
  "decisions_needed": ["<decision 1>", "<decision 2>"],
  "next_steps": ["<step 1>", "<step 2>"],
  "citation_indexes": [1, 2]
}}

Rules:
- Use only the evidence below.
- Keep points concise and decision-oriented.
- Include 2-5 items for each list when supported.
- Add citation indexes that best support the brief overall.

User request: {query}

Structured analysis:
{analysis}

Evidence:
{evidence}
"""

_FLASHCARDS_PROMPT_TEMPLATE = """\
You are creating study flashcards from indexed source material.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short overview for this batch>",
  "cards": [
    {{
      "front": "<question, concept, or term prompt>",
      "back": "<short answer>",
      "explanation": "<why this answer is correct, grounded in the evidence>",
      "difficulty": "easy|medium|hard",
      "tags": ["<short topic tag>"],
      "citation_indexes": [1]
    }}
  ]
}}

Rules:
- Use only the evidence below. Do not add outside knowledge.
- Make cards useful for study, not generic reading comprehension.
- Prefer key concepts, definitions, processes, timelines, comparisons, and exam-worthy facts.
- Each card must include at least one citation index from the evidence list.
- Avoid duplicate cards in this batch.
- Produce up to {card_limit} cards.

User request: {query}

Evidence:
{evidence}
"""

_QUIZ_PROMPT_TEMPLATE = """\
You are creating a source-grounded quiz from indexed source material.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short overview for this batch>",
  "questions": [
    {{
      "type": "multiple_choice|true_false",
      "question": "<question text>",
      "options": [
        {{ "id": "a", "text": "<option text>" }},
        {{ "id": "b", "text": "<option text>" }}
      ],
      "correct_option_id": "a",
      "explanation": "<why the answer is correct, grounded in the evidence>",
      "difficulty": "easy|medium|hard",
      "tags": ["<short topic tag>"],
      "citation_indexes": [1]
    }}
  ]
}}

Rules:
- Use only the evidence below. Do not add outside knowledge.
- Prefer exam-worthy concepts, definitions, processes, comparisons, timelines, and cause/effect.
- About 70% of questions should be multiple_choice and 30% true_false when the evidence supports it.
- multiple_choice questions must have exactly 4 options with ids "a", "b", "c", "d".
- true_false questions must have exactly 2 options with ids "true" and "false".
- Each question must include at least one citation index from the evidence list.
- Avoid duplicate questions in this batch.
- Produce up to {question_limit} questions.

User request: {query}

Evidence:
{evidence}
"""

_STUDY_GUIDE_PROMPT_TEMPLATE = """\
You are creating a source-grounded study guide from indexed source material.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short overview for this batch>",
  "sections": [
    {{
      "title": "<section, chapter, or topic title>",
      "summary": "<short summary grounded in the evidence>",
      "key_points": ["<important point>"],
      "citation_indexes": [1]
    }}
  ],
  "key_concepts": [
    {{
      "term": "<concept or term>",
      "definition": "<definition grounded in the evidence>",
      "importance": "<why this concept matters in the source material>",
      "citation_indexes": [1]
    }}
  ],
  "timeline": [
    {{
      "label": "<date, period, stage, or sequence label>",
      "description": "<what happened or why it matters>",
      "citation_indexes": [1]
    }}
  ],
  "review_questions": [
    {{
      "question": "<review question>",
      "answer": "<source-grounded answer>",
      "citation_indexes": [1]
    }}
  ]
}}

Rules:
- Use only the evidence below. Do not add outside knowledge.
- Prefer chapter structure, major topics, key concepts, timelines/stages, comparisons, and exam-worthy review questions.
- Timeline can be empty if the evidence does not contain clear dates, periods, stages, or ordered events.
- Every non-empty section, concept, timeline item, and review question must include at least one citation index.
- Avoid duplicates in this batch.
- Produce up to {section_limit} sections, {concept_limit} key concepts, {timeline_limit} timeline items, and {question_limit} review questions.

User request: {query}

Evidence:
{evidence}
"""

_MIND_MAP_PROMPT_TEMPLATE = """\
You are creating a source-grounded 2D mind map from indexed source material.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short overview for this batch>",
  "central_topic": "<main topic>",
  "nodes": [
    {{
      "id": "<unique_string_id>",
      "label": "<short node label>",
      "type": "central|topic|subtopic|concept|source",
      "summary": "<short detail grounded in the evidence>",
      "level": 0,
      "parent_id": null,
      "citation_indexes": [1]
    }}
  ],
  "edges": [
    {{
      "id": "<unique_string_id>",
      "source": "<node_id>",
      "target": "<node_id>",
      "type": "parent_child|relates_to|supports",
      "description": "<why these nodes relate>",
      "citation_indexes": [1]
    }}
  ]
}}

Rules:
- Use only the evidence below. Do not add outside knowledge.
- Build a study-friendly mind map, not a generic network.
- Keep node labels concise, usually 1-5 words.
- Include one central node at level 0 and branch nodes up to level {max_depth}.
- Use parent_child edges for hierarchy and relates_to/supports only when evidence supports cross-links.
- Every non-empty node and edge should include at least one citation index from the evidence list.
- Avoid duplicate nodes in this batch.
- Produce up to {node_limit} nodes and {edge_limit} edges.

User request: {query}

Evidence:
{evidence}
"""

_PODCAST_PROMPT_TEMPLATE = """\
You are an expert podcast scriptwriter. Based ONLY on the evidence below, write an engaging and informative podcast script.
The podcast features two hosts:
- Host A (the interviewer/curious host): asks insightful questions, sets the stage, and keeps the conversation lively.
- Host B (the expert/subject matter expert): explains the concepts clearly based on the provided evidence, uses analogies, and breaks down complex details.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short overview of the podcast topic>",
  "dialogue": [
    {{
      "speaker": "Host A",
      "text": "<dialogue text>",
      "citation_indexes": [1]
    }},
    {{
      "speaker": "Host B",
      "text": "<dialogue text>",
      "citation_indexes": [1, 2]
    }}
  ]
}}

Rules:
- Write between 6 to 12 dialogue turns in total.
- Keep the tone conversational, natural, and educational.
- Do not add outside knowledge. Every fact stated by Host B must be grounded in the provided evidence.
- Do not use markdown inside the dialogue text. Keep it as clean, readable text that can be spoken by a TTS reader.
- Each dialogue turn must include a "citation_indexes" list containing the integer index of the evidence that supports the statements in that turn.

User request / topic: {query}

Evidence:
{evidence}
"""

_STRUCTURED_REPORT_TYPES = {
    "action_items",
    "risk_analysis",
    "executive_brief",
    "flashcards",
    "quiz",
    "study_guide",
    "mind_map",
    "podcast",
}
_ACTIONABLE_REPORT_TYPES = {"action_items", "risk_analysis", "executive_brief"}
_FLASHCARDS_MAX_CARDS = 40
_FLASHCARDS_BATCH_SIZE = 10

_QUIZ_MAX_QUESTIONS = 30
_QUIZ_BATCH_SIZE = 10
_STUDY_GUIDE_MAX_SECTIONS = 12
_STUDY_GUIDE_MAX_CONCEPTS = 30
_STUDY_GUIDE_MAX_TIMELINE_ITEMS = 20
_STUDY_GUIDE_MAX_REVIEW_QUESTIONS = 20
_STUDY_GUIDE_BATCH_SIZE = 10
_MIND_MAP_MAX_NODES = 60
_MIND_MAP_MAX_EDGES = 90
_MIND_MAP_MAX_DEPTH = 4
_MIND_MAP_BATCH_SIZE = 10


def generate_report(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    report_type: str,
    format: str,
    provider: str,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Generate a structured research report backed by RAG insights."""
    if report_type == "conflict_mesh":
        from app.engines.report.mesh_pipeline import generate_conflict_mesh

        return generate_conflict_mesh(db, project_id, query, provider, parent_run_id=parent_run_id)
    if report_type == "flashcards":
        return _generate_flashcards_report(
            db=db,
            project_id=project_id,
            query=query,
            report_type=report_type,
            format=format,
            provider=provider,
            parent_run_id=parent_run_id,
        )
    if report_type == "quiz":
        return _generate_quiz_report(
            db=db,
            project_id=project_id,
            query=query,
            report_type=report_type,
            format=format,
            provider=provider,
            parent_run_id=parent_run_id,
        )
    if report_type == "study_guide":
        return _generate_study_guide_report(
            db=db,
            project_id=project_id,
            query=query,
            report_type=report_type,
            format=format,
            provider=provider,
            parent_run_id=parent_run_id,
        )
    if report_type == "mind_map":
        return _generate_mind_map_report(
            db=db,
            project_id=project_id,
            query=query,
            report_type=report_type,
            format=format,
            provider=provider,
            parent_run_id=parent_run_id,
        )
    if report_type == "podcast":
        return _generate_podcast_report(
            db=db,
            project_id=project_id,
            query=query,
            report_type=report_type,
            format=format,
            provider=provider,
            parent_run_id=parent_run_id,
        )

    # Step 1: Run insight synthesis
    try:
        insight_result = generate_insight(
            db=db,
            project_id=project_id,
            query=query,
            provider=provider,
        )
    except InsightError as exc:
        raise ReportError(
            exc.message,
            code="REPORT_INSIGHT_ERROR",
            status_code=exc.status_code,
            details=exc.details,
        ) from exc

    # Step 2: Build analysis context for the report writer
    findings_text = _format_findings_for_report(insight_result)
    evidence_blocks, evidence_citations = _build_evidence_blocks(db, insight_result.get("citations", []))
    prompt_template = _REPORT_PROMPT_TEMPLATE
    structured_payload: dict[str, Any] | None = None

    if report_type in _ACTIONABLE_REPORT_TYPES:
        prompt_template = _get_actionable_prompt_template(report_type)
        prompt = prompt_template.format(
            query=query,
            analysis=findings_text,
            evidence=evidence_blocks,
        )
    else:
        prompt = _REPORT_PROMPT_TEMPLATE.format(
            report_type=report_type,
            query=query,
            analysis=findings_text,
        )

    # Step 3: Render the report
    from app.services.provider_settings_service import (
        ProviderSettingsError,
        normalize_provider,
        resolve_chat_provider_config,
    )

    try:
        answer_provider = normalize_provider(provider)
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise ReportError(str(exc)) from exc

    try:
        if report_type in _ACTIONABLE_REPORT_TYPES:
            raw_payload = _call_llm_json(
                prompt=prompt,
                provider=answer_provider,
                api_key=generation_config["api_key"],
                base_url=generation_config.get("base_url"),
                model=generation_config["chat_model"],
            )
            structured_payload = _parse_actionable_payload(
                report_type=report_type,
                raw=raw_payload,
                citations=evidence_citations,
                insight_result=insight_result,
            )
            report_content = _render_structured_payload_as_markdown(
                report_type=report_type,
                title=_derive_title(query, report_type),
                payload=structured_payload,
            )
        else:
            report_content = _call_llm(
                prompt=prompt,
                provider=answer_provider,
                api_key=generation_config["api_key"],
                base_url=generation_config.get("base_url"),
                model=generation_config["chat_model"],
            )
    except ReportError:
        raise
    except Exception as exc:
        raise ReportError(
            "LLM call failed during report generation.",
            code="REPORT_UPSTREAM_ERROR",
            status_code=502,
            details={"reason": str(exc)[:240]},
        ) from exc

    # Step 4: Persist report + lineage
    title = _derive_title(query, report_type)
    prompt_hash = hashlib.sha256(prompt_template.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]
    evidence_snapshot = insight_result.get("evidence_snapshot") or _build_evidence_snapshot(
        insight_result.get("citations", [])
    )

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="report",
        model_id=generation_config["chat_model"],
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": report_type,
            "format": format,
            "query": query,
            "provider": answer_provider,
            "insight_id": insight_result["insight_id"],
            "structured_output": report_type in _STRUCTURED_REPORT_TYPES,
            "evidence_snapshot": evidence_snapshot,
        },
        parent_run_id=parent_run_id,
    )

    report = Report(
        project_id=project_id,
        query=query,
        title=title,
        report_type=report_type,
        format=format,
        content=report_content,
        structured_payload=structured_payload,
        status="completed",
        run_id=run.id,
    )
    db.add(report)
    db.flush()  # get report.id before committing

    # Link insight → report
    link = ReportInsight(
        report_id=report.id,
        insight_id=uuid.UUID(insight_result["insight_id"]),
    )
    db.add(link)
    db.commit()
    db.refresh(report)

    # Collect unique source ids from insight citations
    source_ids = list({c["source_id"] for c in insight_result["citations"] if c.get("source_id")})

    structured_payload = hydrate_report_payload_citations(db, structured_payload)
    citations = hydrate_citations(db, insight_result["citations"])

    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": report_type,
        "format": format,
        "content": report_content,
        "structured_payload": structured_payload,
        "status": "completed",
        "run_id": str(run.id),
        "insight_id": insight_result["insight_id"],
        "source_ids": source_ids,
        "citations": citations,
        "evidence_snapshot": evidence_snapshot,
    }


def _generate_flashcards_report(
    *,
    db: Session,
    project_id: uuid.UUID,
    query: str,
    report_type: str,
    format: str,
    provider: str,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    from app.services.provider_settings_service import (
        ProviderSettingsError,
        normalize_provider,
        resolve_chat_provider_config,
    )

    try:
        answer_provider = normalize_provider(provider)
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise ReportError(str(exc)) from exc

    indexing_result = ensure_project_sources_indexed(
        db,
        project_id=project_id,
        filters=None,
        trigger="flashcards_indexing",
    )
    chunks = _load_flashcard_chunks(db, project_id)
    if not chunks:
        raise ReportError(
            "No indexed chunks are available for flashcard generation.",
            code="REPORT_FLASHCARDS_NO_CHUNKS",
            status_code=409,
            details={"indexing": indexing_result},
        )

    batches = _chunk_list(chunks, _FLASHCARDS_BATCH_SIZE)
    cards_per_batch = max(2, min(6, math.ceil(_FLASHCARDS_MAX_CARDS / max(len(batches), 1))))
    collected_cards: list[dict[str, Any]] = []
    seen_fronts: set[str] = set()
    overview_parts: list[str] = []

    for batch in batches:
        if len(collected_cards) >= _FLASHCARDS_MAX_CARDS:
            break
        evidence_blocks, citations = _format_flashcard_evidence(batch)
        prompt = _FLASHCARDS_PROMPT_TEMPLATE.format(
            query=query,
            evidence=evidence_blocks,
            card_limit=cards_per_batch,
        )
        raw_payload = _call_llm_json(
            prompt=prompt,
            provider=answer_provider,
            api_key=generation_config["api_key"],
            base_url=generation_config.get("base_url"),
            model=generation_config["chat_model"],
        )
        parsed = _load_json_object(raw_payload)
        normalized = _normalize_flashcards_batch_payload(parsed, citations, query)
        overview = _coerce_string(normalized.get("overview"))
        if overview:
            overview_parts.append(overview)
        for card in normalized["cards"]:
            fingerprint = _flashcard_fingerprint(card.get("front", ""))
            if not fingerprint or fingerprint in seen_fronts:
                continue
            seen_fronts.add(fingerprint)
            collected_cards.append(card)
            if len(collected_cards) >= _FLASHCARDS_MAX_CARDS:
                break

    if not collected_cards:
        collected_cards = _fallback_flashcards(chunks[:_FLASHCARDS_MAX_CARDS], query)

    payload = {
        "overview": _build_flashcards_overview(overview_parts, len(collected_cards), len(chunks)),
        "cards": collected_cards[:_FLASHCARDS_MAX_CARDS],
    }
    title = _derive_title(query, report_type)
    report_content = _render_structured_payload_as_markdown(
        report_type=report_type,
        title=title,
        payload=payload,
    )
    prompt_hash = hashlib.sha256(_FLASHCARDS_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]
    all_citations = _unique_citations(
        citation
        for item in chunks
        for citation in [item["citation"]]
    )
    evidence_snapshot = _build_evidence_snapshot(all_citations)

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="report",
        model_id=generation_config["chat_model"],
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": report_type,
            "format": format,
            "query": query,
            "provider": answer_provider,
            "structured_output": True,
            "indexed_chunk_count": len(chunks),
            "generated_card_count": len(payload["cards"]),
            "indexing": indexing_result,
            "evidence_snapshot": evidence_snapshot,
        },
        parent_run_id=parent_run_id,
    )
    report = Report(
        project_id=project_id,
        query=query,
        title=title,
        report_type=report_type,
        format=format,
        content=report_content,
        structured_payload=payload,
        status="completed",
        run_id=run.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    structured_payload = hydrate_report_payload_citations(db, payload)
    citations = hydrate_citations(db, _unique_citations(
        citation
        for card in payload["cards"]
        for citation in card.get("citations", [])
    ))
    source_ids = list({citation["source_id"] for citation in all_citations if citation.get("source_id")})
    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": report_type,
        "format": format,
        "content": report_content,
        "structured_payload": structured_payload,
        "status": "completed",
        "run_id": str(run.id),
        "source_ids": source_ids,
        "citations": citations,
        "evidence_snapshot": evidence_snapshot,
    }


def _generate_quiz_report(
    *,
    db: Session,
    project_id: uuid.UUID,
    query: str,
    report_type: str,
    format: str,
    provider: str,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    from app.services.provider_settings_service import (
        ProviderSettingsError,
        normalize_provider,
        resolve_chat_provider_config,
    )

    try:
        answer_provider = normalize_provider(provider)
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise ReportError(str(exc)) from exc

    indexing_result = ensure_project_sources_indexed(
        db,
        project_id=project_id,
        filters=None,
        trigger="quiz_indexing",
    )
    chunks = _load_flashcard_chunks(db, project_id)
    if not chunks:
        raise ReportError(
            "No indexed chunks are available for quiz generation.",
            code="REPORT_QUIZ_NO_CHUNKS",
            status_code=409,
            details={"indexing": indexing_result},
        )

    batches = _chunk_list(chunks, _QUIZ_BATCH_SIZE)
    questions_per_batch = max(2, min(5, math.ceil(_QUIZ_MAX_QUESTIONS / max(len(batches), 1))))
    collected_questions: list[dict[str, Any]] = []
    seen_questions: set[str] = set()
    overview_parts: list[str] = []

    for batch in batches:
        if len(collected_questions) >= _QUIZ_MAX_QUESTIONS:
            break
        evidence_blocks, citations = _format_flashcard_evidence(batch)
        prompt = _QUIZ_PROMPT_TEMPLATE.format(
            query=query,
            evidence=evidence_blocks,
            question_limit=questions_per_batch,
        )
        raw_payload = _call_llm_json(
            prompt=prompt,
            provider=answer_provider,
            api_key=generation_config["api_key"],
            base_url=generation_config.get("base_url"),
            model=generation_config["chat_model"],
        )
        parsed = _load_json_object(raw_payload)
        normalized = _normalize_quiz_batch_payload(parsed, citations, query)
        overview = _coerce_string(normalized.get("overview"))
        if overview:
            overview_parts.append(overview)
        for question in normalized["questions"]:
            fingerprint = _flashcard_fingerprint(question.get("question", ""))
            if not fingerprint or fingerprint in seen_questions:
                continue
            seen_questions.add(fingerprint)
            collected_questions.append(question)
            if len(collected_questions) >= _QUIZ_MAX_QUESTIONS:
                break

    if not collected_questions:
        collected_questions = _fallback_quiz_questions(chunks[:_QUIZ_MAX_QUESTIONS], query)

    payload = {
        "overview": _build_quiz_overview(overview_parts, len(collected_questions), len(chunks)),
        "questions": collected_questions[:_QUIZ_MAX_QUESTIONS],
    }
    title = _derive_title(query, report_type)
    report_content = _render_structured_payload_as_markdown(
        report_type=report_type,
        title=title,
        payload=payload,
    )
    prompt_hash = hashlib.sha256(_QUIZ_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]
    all_citations = _unique_citations(citation for item in chunks for citation in [item["citation"]])
    evidence_snapshot = _build_evidence_snapshot(all_citations)

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="report",
        model_id=generation_config["chat_model"],
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": report_type,
            "format": format,
            "query": query,
            "provider": answer_provider,
            "structured_output": True,
            "indexed_chunk_count": len(chunks),
            "generated_question_count": len(payload["questions"]),
            "indexing": indexing_result,
            "evidence_snapshot": evidence_snapshot,
        },
        parent_run_id=parent_run_id,
    )
    report = Report(
        project_id=project_id,
        query=query,
        title=title,
        report_type=report_type,
        format=format,
        content=report_content,
        structured_payload=payload,
        status="completed",
        run_id=run.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    structured_payload = hydrate_report_payload_citations(db, payload)
    citations = hydrate_citations(
        db,
        _unique_citations(
            citation
            for question in payload["questions"]
            for citation in question.get("citations", [])
        ),
    )
    source_ids = list({citation["source_id"] for citation in all_citations if citation.get("source_id")})
    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": report_type,
        "format": format,
        "content": report_content,
        "structured_payload": structured_payload,
        "status": "completed",
        "run_id": str(run.id),
        "source_ids": source_ids,
        "citations": citations,
        "evidence_snapshot": evidence_snapshot,
    }


def _generate_study_guide_report(
    *,
    db: Session,
    project_id: uuid.UUID,
    query: str,
    report_type: str,
    format: str,
    provider: str,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    from app.services.provider_settings_service import (
        ProviderSettingsError,
        normalize_provider,
        resolve_chat_provider_config,
    )

    try:
        answer_provider = normalize_provider(provider)
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise ReportError(str(exc)) from exc

    indexing_result = ensure_project_sources_indexed(
        db,
        project_id=project_id,
        filters=None,
        trigger="study_guide_indexing",
    )
    chunks = _load_flashcard_chunks(db, project_id)
    if not chunks:
        raise ReportError(
            "No indexed chunks are available for study guide generation.",
            code="REPORT_STUDY_GUIDE_NO_CHUNKS",
            status_code=409,
            details={"indexing": indexing_result},
        )

    batches = _chunk_list(chunks, _STUDY_GUIDE_BATCH_SIZE)
    section_limit = max(1, min(3, math.ceil(_STUDY_GUIDE_MAX_SECTIONS / max(len(batches), 1))))
    concept_limit = max(2, min(6, math.ceil(_STUDY_GUIDE_MAX_CONCEPTS / max(len(batches), 1))))
    timeline_limit = max(1, min(4, math.ceil(_STUDY_GUIDE_MAX_TIMELINE_ITEMS / max(len(batches), 1))))
    question_limit = max(2, min(5, math.ceil(_STUDY_GUIDE_MAX_REVIEW_QUESTIONS / max(len(batches), 1))))

    collected_sections: list[dict[str, Any]] = []
    collected_concepts: list[dict[str, Any]] = []
    collected_timeline: list[dict[str, Any]] = []
    collected_questions: list[dict[str, Any]] = []
    seen_sections: set[str] = set()
    seen_concepts: set[str] = set()
    seen_timeline: set[str] = set()
    seen_questions: set[str] = set()
    overview_parts: list[str] = []

    for batch in batches:
        if (
            len(collected_sections) >= _STUDY_GUIDE_MAX_SECTIONS
            and len(collected_concepts) >= _STUDY_GUIDE_MAX_CONCEPTS
            and len(collected_timeline) >= _STUDY_GUIDE_MAX_TIMELINE_ITEMS
            and len(collected_questions) >= _STUDY_GUIDE_MAX_REVIEW_QUESTIONS
        ):
            break
        evidence_blocks, citations = _format_flashcard_evidence(batch)
        prompt = _STUDY_GUIDE_PROMPT_TEMPLATE.format(
            query=query,
            evidence=evidence_blocks,
            section_limit=section_limit,
            concept_limit=concept_limit,
            timeline_limit=timeline_limit,
            question_limit=question_limit,
        )
        raw_payload = _call_llm_json(
            prompt=prompt,
            provider=answer_provider,
            api_key=generation_config["api_key"],
            base_url=generation_config.get("base_url"),
            model=generation_config["chat_model"],
        )
        parsed = _load_json_object(raw_payload)
        normalized = _normalize_study_guide_batch_payload(parsed, citations, query)
        overview = _coerce_string(normalized.get("overview"))
        if overview:
            overview_parts.append(overview)
        _append_unique_study_guide_items(
            target=collected_sections,
            candidates=normalized["sections"],
            seen=seen_sections,
            key_name="title",
            limit=_STUDY_GUIDE_MAX_SECTIONS,
        )
        _append_unique_study_guide_items(
            target=collected_concepts,
            candidates=normalized["key_concepts"],
            seen=seen_concepts,
            key_name="term",
            limit=_STUDY_GUIDE_MAX_CONCEPTS,
        )
        _append_unique_study_guide_items(
            target=collected_timeline,
            candidates=normalized["timeline"],
            seen=seen_timeline,
            key_name="label",
            limit=_STUDY_GUIDE_MAX_TIMELINE_ITEMS,
        )
        _append_unique_study_guide_items(
            target=collected_questions,
            candidates=normalized["review_questions"],
            seen=seen_questions,
            key_name="question",
            limit=_STUDY_GUIDE_MAX_REVIEW_QUESTIONS,
        )

    if not any((collected_sections, collected_concepts, collected_timeline, collected_questions)):
        fallback = _fallback_study_guide(chunks, query)
        collected_sections = fallback["sections"]
        collected_concepts = fallback["key_concepts"]
        collected_timeline = fallback["timeline"]
        collected_questions = fallback["review_questions"]

    payload = {
        "overview": _build_study_guide_overview(
            overview_parts=overview_parts,
            section_count=len(collected_sections),
            concept_count=len(collected_concepts),
            review_question_count=len(collected_questions),
            chunk_count=len(chunks),
        ),
        "sections": collected_sections[:_STUDY_GUIDE_MAX_SECTIONS],
        "key_concepts": collected_concepts[:_STUDY_GUIDE_MAX_CONCEPTS],
        "timeline": collected_timeline[:_STUDY_GUIDE_MAX_TIMELINE_ITEMS],
        "review_questions": collected_questions[:_STUDY_GUIDE_MAX_REVIEW_QUESTIONS],
    }
    title = _derive_title(query, report_type)
    report_content = _render_structured_payload_as_markdown(
        report_type=report_type,
        title=title,
        payload=payload,
    )
    prompt_hash = hashlib.sha256(_STUDY_GUIDE_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]
    all_citations = _unique_citations(citation for item in chunks for citation in [item["citation"]])
    evidence_snapshot = _build_evidence_snapshot(all_citations)

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="report",
        model_id=generation_config["chat_model"],
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": report_type,
            "format": format,
            "query": query,
            "provider": answer_provider,
            "structured_output": True,
            "indexed_chunk_count": len(chunks),
            "generated_section_count": len(payload["sections"]),
            "generated_concept_count": len(payload["key_concepts"]),
            "generated_timeline_count": len(payload["timeline"]),
            "generated_review_question_count": len(payload["review_questions"]),
            "indexing": indexing_result,
            "evidence_snapshot": evidence_snapshot,
        },
        parent_run_id=parent_run_id,
    )
    report = Report(
        project_id=project_id,
        query=query,
        title=title,
        report_type=report_type,
        format=format,
        content=report_content,
        structured_payload=payload,
        status="completed",
        run_id=run.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    structured_payload = hydrate_report_payload_citations(db, payload)
    citations = hydrate_citations(db, _study_guide_payload_citations(payload))
    source_ids = list({citation["source_id"] for citation in all_citations if citation.get("source_id")})
    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": report_type,
        "format": format,
        "content": report_content,
        "structured_payload": structured_payload,
        "status": "completed",
        "run_id": str(run.id),
        "source_ids": source_ids,
        "citations": citations,
        "evidence_snapshot": evidence_snapshot,
    }


def _generate_mind_map_report(
    *,
    db: Session,
    project_id: uuid.UUID,
    query: str,
    report_type: str,
    format: str,
    provider: str,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    from app.services.provider_settings_service import (
        ProviderSettingsError,
        normalize_provider,
        resolve_chat_provider_config,
    )

    try:
        answer_provider = normalize_provider(provider)
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise ReportError(str(exc)) from exc

    indexing_result = ensure_project_sources_indexed(
        db,
        project_id=project_id,
        filters=None,
        trigger="mind_map_indexing",
    )
    chunks = _load_flashcard_chunks(db, project_id)
    if not chunks:
        raise ReportError(
            "No indexed chunks are available for mind map generation.",
            code="REPORT_MIND_MAP_NO_CHUNKS",
            status_code=409,
            details={"indexing": indexing_result},
        )

    batches = _chunk_list(chunks, _MIND_MAP_BATCH_SIZE)
    nodes_per_batch = max(4, min(12, math.ceil(_MIND_MAP_MAX_NODES / max(len(batches), 1))))
    edges_per_batch = max(4, min(16, math.ceil(_MIND_MAP_MAX_EDGES / max(len(batches), 1))))
    collected_nodes: list[dict[str, Any]] = []
    collected_edges: list[dict[str, Any]] = []
    node_id_by_label: dict[str, str] = {}
    used_node_ids: set[str] = set()
    seen_edges: set[str] = set()
    overview_parts: list[str] = []
    central_topic = _preview(query, limit=80) or "Mind Map"

    for batch in batches:
        if len(collected_nodes) >= _MIND_MAP_MAX_NODES and len(collected_edges) >= _MIND_MAP_MAX_EDGES:
            break
        evidence_blocks, citations = _format_flashcard_evidence(batch)
        prompt = _MIND_MAP_PROMPT_TEMPLATE.format(
            query=query,
            evidence=evidence_blocks,
            node_limit=nodes_per_batch,
            edge_limit=edges_per_batch,
            max_depth=_MIND_MAP_MAX_DEPTH,
        )
        raw_payload = _call_llm_json(
            prompt=prompt,
            provider=answer_provider,
            api_key=generation_config["api_key"],
            base_url=generation_config.get("base_url"),
            model=generation_config["chat_model"],
        )
        parsed = _load_json_object(raw_payload)
        normalized = _normalize_mind_map_batch_payload(parsed, citations, query)
        overview = _coerce_string(normalized.get("overview"))
        if overview:
            overview_parts.append(overview)
        central_topic = _coerce_string(normalized.get("central_topic"), central_topic)
        local_to_global = _merge_mind_map_nodes(
            target=collected_nodes,
            candidates=normalized["nodes"],
            node_id_by_label=node_id_by_label,
            used_node_ids=used_node_ids,
            limit=_MIND_MAP_MAX_NODES,
        )
        _merge_mind_map_edges(
            target=collected_edges,
            candidates=normalized["edges"],
            local_to_global=local_to_global,
            seen_edges=seen_edges,
            limit=_MIND_MAP_MAX_EDGES,
        )

    if not collected_nodes:
        fallback = _fallback_mind_map(chunks, query)
        central_topic = fallback["central_topic"]
        collected_nodes = fallback["nodes"]
        collected_edges = fallback["edges"]

    payload = _finalize_mind_map_payload(
        overview=_build_mind_map_overview(overview_parts, len(collected_nodes), len(collected_edges), len(chunks)),
        central_topic=central_topic,
        nodes=collected_nodes[:_MIND_MAP_MAX_NODES],
        edges=collected_edges[:_MIND_MAP_MAX_EDGES],
    )
    title = _derive_title(query, report_type)
    report_content = _render_structured_payload_as_markdown(
        report_type=report_type,
        title=title,
        payload=payload,
    )
    prompt_hash = hashlib.sha256(_MIND_MAP_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]
    all_citations = _unique_citations(citation for item in chunks for citation in [item["citation"]])
    evidence_snapshot = _build_evidence_snapshot(all_citations)

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="report",
        model_id=generation_config["chat_model"],
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": report_type,
            "format": format,
            "query": query,
            "provider": answer_provider,
            "structured_output": True,
            "indexed_chunk_count": len(chunks),
            "generated_node_count": len(payload["nodes"]),
            "generated_edge_count": len(payload["edges"]),
            "indexing": indexing_result,
            "evidence_snapshot": evidence_snapshot,
        },
        parent_run_id=parent_run_id,
    )
    report = Report(
        project_id=project_id,
        query=query,
        title=title,
        report_type=report_type,
        format=format,
        content=report_content,
        structured_payload=payload,
        status="completed",
        run_id=run.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    structured_payload = hydrate_report_payload_citations(db, payload)
    citations = hydrate_citations(db, _mind_map_payload_citations(payload))
    source_ids = list({citation["source_id"] for citation in all_citations if citation.get("source_id")})
    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": report_type,
        "format": format,
        "content": report_content,
        "structured_payload": structured_payload,
        "status": "completed",
        "run_id": str(run.id),
        "source_ids": source_ids,
        "citations": citations,
        "evidence_snapshot": evidence_snapshot,
    }


def is_vietnamese(text: str) -> bool:
    """Detect Vietnamese text so the podcast uses Vietnamese-capable voices."""
    normalized = unicodedata.normalize("NFC", text or "").lower()
    vietnamese_chars = set(
        "àáảãạăằắẳẵặâầấẩẫậ"
        "èéẻẽẹêềếểễệ"
        "ìíỉĩị"
        "òóỏõọôồốổỗộơờớởỡợ"
        "ùúủũụưừứửữự"
        "ỳýỷỹỵđ"
    )
    if any(char in vietnamese_chars for char in normalized):
        return True

    words = set(re.findall(r"\b[a-z]+\b", normalized))
    vietnamese_markers = {
        "ban",
        "cac",
        "cho",
        "chung",
        "cua",
        "dung",
        "duoc",
        "hien",
        "khong",
        "la",
        "lieu",
        "mot",
        "nay",
        "nguoi",
        "nhung",
        "noi",
        "phat",
        "qua",
        "rang",
        "se",
        "ta",
        "tai",
        "the",
        "tieng",
        "trong",
        "va",
        "ve",
        "viet",
        "voi",
    }
    return len(words & vietnamese_markers) >= 3


def _sanitize_podcast_tts_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text or "")
    normalized = re.sub(r"https?://\S+|www\.\S+", "", normalized)
    normalized = re.sub(r"[\*_`#>\[\]{}|~^]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return "".join(
        char
        for char in normalized.strip()
        if unicodedata.category(char)[0] != "C" and unicodedata.category(char) != "So"
    )


def _split_long_tts_text(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    remaining = text.strip()
    while len(remaining) > max_chars:
        split_at = max(
            remaining.rfind(separator, 0, max_chars)
            for separator in (", ", "; ", ": ", " - ", " ")
        )
        if split_at <= 0:
            split_at = max_chars
        chunk = remaining[:split_at].strip(" ,;:-")
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _split_podcast_tts_text(text: str, max_chars: int = 700) -> list[str]:
    sanitized = _sanitize_podcast_tts_text(text)
    if not sanitized:
        return []

    chunks: list[str] = []
    current = ""
    sentences = re.split(r"(?<=[.!?;:])\s+", sanitized)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_long_tts_text(sentence, max_chars))
            continue
        candidate = f"{current} {sentence}".strip()
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = sentence
    if current:
        chunks.append(current)
    return chunks


def _has_mp3_frame(data: bytes) -> bool:
    offset = 0
    if data.startswith(b"ID3") and len(data) >= 10:
        tag_size = (
            ((data[6] & 0x7F) << 21)
            | ((data[7] & 0x7F) << 14)
            | ((data[8] & 0x7F) << 7)
            | (data[9] & 0x7F)
        )
        footer_size = 10 if data[5] & 0x10 else 0
        offset = 10 + tag_size + footer_size
    return any(
        data[index] == 0xFF and (data[index + 1] & 0xE0) == 0xE0
        for index in range(offset, max(offset, len(data) - 1))
    )


def _is_valid_mp3_file(path: str) -> bool:
    if not os.path.exists(path) or os.path.getsize(path) < 128:
        return False
    with open(path, "rb") as file:
        return _has_mp3_frame(file.read(4096))


def podcast_audio_file_is_playable(path: str) -> bool:
    return _is_valid_mp3_file(path)


def _strip_id3v1(data: bytes) -> bytes:
    if len(data) >= 128 and data[-128:-125] == b"TAG":
        return data[:-128]
    return data


def _strip_id3v2(data: bytes) -> bytes:
    if not data.startswith(b"ID3") or len(data) < 10:
        return data
    tag_size = (
        ((data[6] & 0x7F) << 21)
        | ((data[7] & 0x7F) << 14)
        | ((data[8] & 0x7F) << 7)
        | (data[9] & 0x7F)
    )
    footer_size = 10 if data[5] & 0x10 else 0
    return data[10 + tag_size + footer_size :]


def _combine_mp3_segments(segment_paths: list[str], output_path: str) -> None:
    combined = bytearray()
    for index, path in enumerate(segment_paths):
        if not _is_valid_mp3_file(path):
            raise ValueError(f"Generated podcast segment is not a valid MP3: {path}")
        with open(path, "rb") as file:
            data = _strip_id3v1(file.read())
        if index > 0:
            data = _strip_id3v2(data)
        combined.extend(data)
    if not _has_mp3_frame(bytes(combined[:4096])):
        raise ValueError("Combined podcast audio is not a valid MP3 stream.")
    with open(output_path, "wb") as file:
        file.write(combined)


import threading

_podcast_locks: dict[uuid.UUID, threading.Lock] = {}
_podcast_locks_lock = threading.Lock()


def get_podcast_lock(report_id: uuid.UUID) -> threading.Lock:
    with _podcast_locks_lock:
        if report_id not in _podcast_locks:
            _podcast_locks[report_id] = threading.Lock()
        return _podcast_locks[report_id]


def generate_podcast_audio(report_id: uuid.UUID, dialogue_payload: dict[str, Any]) -> str:
    """Generate and concatenate the speech audio for the podcast dialogue using edge-tts.
    Returns the absolute path to the combined MP3 file.
    """
    import asyncio

    import edge_tts

    from app.core.config import get_settings

    # 1. Create uploads/podcasts folder if missing
    podcast_dir = os.path.join(get_settings().upload_dir, "podcasts")
    os.makedirs(podcast_dir, exist_ok=True)

    output_path = os.path.join(podcast_dir, f"{report_id}.mp3")

    # Use a lock per report_id to prevent concurrent generations/writes for the same podcast
    lock = get_podcast_lock(report_id)
    with lock:
        # If already generated, return path immediately
        if _is_valid_mp3_file(output_path):
            return output_path
        if os.path.exists(output_path):
            try:
                os.unlink(output_path)
            except OSError:
                pass

        dialogue = dialogue_payload.get("dialogue") or []
        if not dialogue:
            raise ValueError("Dialogue is empty")

        # Check all dialogue text so Vietnamese without diacritics in early turns still selects Vietnamese voices.
        sample_text = " ".join(_coerce_string(turn.get("text")) for turn in dialogue)
        is_vn = is_vietnamese(sample_text)

        voice_a = "vi-VN-HoaiMyNeural" if is_vn else "en-US-JennyNeural"
        voice_b = "vi-VN-NamMinhNeural" if is_vn else "en-US-GuyNeural"

        # We will generate each speech turn into a unique temp folder per report
        temp_dir = os.path.join(get_settings().upload_dir, f"temp_podcast_{report_id}")
        os.makedirs(temp_dir, exist_ok=True)

        temp_paths: list[str] = []

        async def synthesize_turn(text: str, voice: str, path: str) -> None:
            last_error: Exception | None = None
            for attempt in range(3):
                try:
                    if os.path.exists(path):
                        os.unlink(path)
                    communicate = edge_tts.Communicate(
                        text,
                        voice,
                        receive_timeout=90,
                    )
                    await communicate.save(path)
                    if _is_valid_mp3_file(path):
                        return
                    raise ValueError("edge-tts returned an invalid MP3 segment")
                except Exception as exc:
                    last_error = exc
                    if os.path.exists(path):
                        try:
                            os.unlink(path)
                        except OSError:
                            pass
                    if attempt < 2:
                        await asyncio.sleep(0.75 * (attempt + 1))
            if last_error is not None:
                raise last_error
            raise RuntimeError(f"edge-tts did not return playable audio for voice {voice}")

        async def run_synthesis() -> None:
            for i, turn in enumerate(dialogue):
                speaker = turn.get("speaker", "Host A")
                text_chunks = _split_podcast_tts_text(_coerce_string(turn.get("text")))
                if not text_chunks:
                    continue
                voice = voice_a if speaker == "Host A" else voice_b
                for chunk_index, text_chunk in enumerate(text_chunks):
                    temp_path = os.path.join(
                        temp_dir,
                        f"turn_{i}_{chunk_index}.mp3",
                    )
                    temp_paths.append(temp_path)
                    await synthesize_turn(text_chunk, voice, temp_path)

        temp_output_path = os.path.join(podcast_dir, f"{report_id}.tmp.mp3")

        try:
            asyncio.run(run_synthesis())

            if not temp_paths:
                raise ValueError("Dialogue contains no speakable text")

            _combine_mp3_segments(temp_paths, temp_output_path)
            if not _is_valid_mp3_file(temp_output_path):
                raise ValueError("Combined podcast audio is not a valid MP3 file.")
            os.replace(temp_output_path, output_path)
        finally:
            # Clean up temporary files and folder
            if os.path.exists(temp_output_path):
                try:
                    os.unlink(temp_output_path)
                except OSError:
                    pass
            for path in temp_paths:
                if os.path.exists(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
            if os.path.exists(temp_dir):
                try:
                    for fname in os.listdir(temp_dir):
                        try:
                            os.unlink(os.path.join(temp_dir, fname))
                        except OSError:
                            pass
                    os.rmdir(temp_dir)
                except OSError:
                    pass

        return output_path


def _generate_podcast_report(
    *,
    db: Session,
    project_id: uuid.UUID,
    query: str,
    report_type: str,
    format: str,
    provider: str,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    from app.services.provider_settings_service import (
        ProviderSettingsError,
        normalize_provider,
        resolve_chat_provider_config,
    )

    try:
        answer_provider = normalize_provider(provider)
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError as exc:
        raise ReportError(str(exc)) from exc

    indexing_result = ensure_project_sources_indexed(
        db,
        project_id=project_id,
        filters=None,
        trigger="podcast_indexing",
    )
    chunks = _load_flashcard_chunks(db, project_id)
    if not chunks:
        raise ReportError(
            "No indexed chunks are available for podcast generation.",
            code="REPORT_PODCAST_NO_CHUNKS",
            status_code=409,
            details={"indexing": indexing_result},
        )

    # Take up to 15 chunks for the podcast discussion to keep context compact and relevant
    podcast_chunks = chunks[:15]
    evidence_blocks, citations = _format_flashcard_evidence(podcast_chunks)

    prompt = _PODCAST_PROMPT_TEMPLATE.format(
        query=query,
        evidence=evidence_blocks,
    )

    raw_payload = _call_llm_json(
        prompt=prompt,
        provider=answer_provider,
        api_key=generation_config["api_key"],
        base_url=generation_config.get("base_url"),
        model=generation_config["chat_model"],
    )
    parsed = _load_json_object(raw_payload)

    # Normalize dialogue turn formats
    dialogue_turns = []
    raw_dialogue = parsed.get("dialogue") or []
    if not isinstance(raw_dialogue, list):
        raw_dialogue = []

    for turn in raw_dialogue:
        if not isinstance(turn, dict):
            continue
        speaker = _coerce_string(turn.get("speaker"), "Host A")
        text = _coerce_string(turn.get("text"), "").strip()
        if not text:
            continue
        # Clean markdown formatting characters
        text = re.sub(r'[*_`#\[\]]', '', text)

        # Attach matching citation indexes if mentioned, or just map all citations
        turn_citations = []
        raw_cit_indexes = turn.get("citation_indexes")
        if isinstance(raw_cit_indexes, list):
            for idx in raw_cit_indexes:
                try:
                    c_idx = int(idx) - 1
                    if 0 <= c_idx < len(citations):
                        turn_citations.append(citations[c_idx])
                except (ValueError, TypeError):
                    pass
        if not turn_citations:
            # Default to mapping all citations if none are specifically indexed
            turn_citations = citations

        dialogue_turns.append({
            "speaker": speaker,
            "text": text,
            "citations": _unique_citations(turn_citations)
        })

    payload = {
        "overview": _coerce_string(parsed.get("overview"), "Discussion on project findings."),
        "dialogue": dialogue_turns
    }

    title = _derive_title(query, report_type)

    # Render script as Markdown for standard content display
    markdown_lines = [f"# {title}", f"\n{payload['overview']}\n"]
    for turn in payload["dialogue"]:
        markdown_lines.append(f"**{turn['speaker']}**: {turn['text']}\n")
    report_content = "\n".join(markdown_lines)

    prompt_hash = hashlib.sha256(_PODCAST_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]
    evidence_snapshot = _build_evidence_snapshot(citations)

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="report",
        model_id=generation_config["chat_model"],
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": report_type,
            "format": format,
            "query": query,
            "provider": answer_provider,
            "structured_output": True,
            "indexed_chunk_count": len(chunks),
            "generated_turns_count": len(payload["dialogue"]),
            "indexing": indexing_result,
            "evidence_snapshot": evidence_snapshot,
        },
        parent_run_id=parent_run_id,
    )

    report = Report(
        project_id=project_id,
        query=query,
        title=title,
        report_type=report_type,
        format=format,
        content=report_content,
        structured_payload=payload,
        status="completed",
        run_id=run.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    structured_payload = hydrate_report_payload_citations(db, payload)

    # Collect all unique source IDs
    source_ids = list({citation["source_id"] for citation in citations if citation.get("source_id")})
    hydrated_citations = hydrate_citations(db, citations)

    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": report_type,
        "format": format,
        "content": report_content,
        "structured_payload": structured_payload,
        "status": "completed",
        "run_id": str(run.id),
        "source_ids": source_ids,
        "citations": hydrated_citations,
        "evidence_snapshot": evidence_snapshot,
    }


def update_action_item_status(
    db: Session,
    report_id: uuid.UUID,
    item_id: str,
    status: str,
) -> dict[str, Any]:
    allowed_statuses = {"open", "needs_review", "done"}
    if status not in allowed_statuses:
        raise ReportError(
            "Unsupported action item status.",
            code="REPORT_ACTION_ITEM_STATUS_INVALID",
            status_code=422,
            details={"allowed_statuses": sorted(allowed_statuses)},
        )

    report_repo = ReportRepository(db)
    report = report_repo.get(report_id)
    if not report:
        raise ReportError(
            "Report does not exist.",
            code="REPORT_NOT_FOUND",
            status_code=404,
        )
    if report.report_type != "action_items":
        raise ReportError(
            "Only action item reports support status updates.",
            code="REPORT_ACTION_ITEMS_UNSUPPORTED",
            status_code=409,
        )
    if not isinstance(report.structured_payload, dict):
        raise ReportError(
            "Structured action items payload is missing.",
            code="REPORT_ACTION_ITEMS_MISSING",
            status_code=409,
        )

    raw_items = report.structured_payload.get("items")
    if not isinstance(raw_items, list):
        raise ReportError(
            "Structured action items payload is invalid.",
            code="REPORT_ACTION_ITEMS_INVALID",
            status_code=409,
        )

    updated = False
    normalized_items: list[dict[str, Any]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        normalized_item = dict(raw_item)
        if normalized_item.get("id") == item_id:
            normalized_item["status"] = status
            updated = True
        normalized_items.append(normalized_item)

    if not updated:
        raise ReportError(
            "Action item does not exist on this report.",
            code="REPORT_ACTION_ITEM_NOT_FOUND",
            status_code=404,
            details={"item_id": item_id},
        )

    payload = dict(report.structured_payload)
    payload["items"] = normalized_items
    report.structured_payload = payload
    report.content = _render_structured_payload_as_markdown(
        report_type=report.report_type,
        title=report.title,
        payload=payload,
    )
    report = report_repo.save(report)
    return serialize_report(report, db)


def get_report_lineage(db: Session, report_id: uuid.UUID) -> dict[str, Any]:
    """Return lineage info for a given report."""
    from app.services.lineage_service import get_report_lineage as build_report_lineage

    return build_report_lineage(db, report_id)


def serialize_report(report: Report, db: Session | None = None) -> dict[str, Any]:
    structured_payload = report.structured_payload
    if db is not None:
        structured_payload = hydrate_report_payload_citations(db, structured_payload)
    return {
        "report_id": str(report.id),
        "project_id": str(report.project_id),
        "query": report.query,
        "title": report.title,
        "type": report.report_type,
        "format": report.format,
        "content": report.content,
        "structured_payload": structured_payload,
        "status": report.status,
        "run_id": str(report.run_id) if report.run_id else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


def create_quiz_attempt(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
    answers: dict[str, str],
) -> dict[str, Any]:
    report = db.get(Report, report_id)
    if not report:
        raise ReportError("Report does not exist.", code="REPORT_NOT_FOUND", status_code=404)
    if report.report_type != "quiz":
        raise ReportError(
            "Only quiz reports support attempts.",
            code="REPORT_QUIZ_ATTEMPTS_UNSUPPORTED",
            status_code=409,
        )
    payload = report.structured_payload if isinstance(report.structured_payload, dict) else {}
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise ReportError(
            "Quiz report does not contain questions.",
            code="REPORT_QUIZ_QUESTIONS_MISSING",
            status_code=409,
        )

    sanitized_answers = {
        str(question_id): str(option_id)
        for question_id, option_id in answers.items()
        if question_id and option_id
    }
    score_total = 0
    score_correct = 0
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            continue
        question_id = _coerce_string(raw_question.get("id"))
        correct_option_id = _coerce_string(raw_question.get("correct_option_id"))
        if not question_id or not correct_option_id:
            continue
        score_total += 1
        if sanitized_answers.get(question_id) == correct_option_id:
            score_correct += 1

    score_percent = round((score_correct / score_total) * 100) if score_total else 0
    attempt = QuizAttempt(
        report_id=report_id,
        user_id=user_id,
        answers=sanitized_answers,
        score_correct=score_correct,
        score_total=score_total,
        score_percent=score_percent,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return serialize_quiz_attempt(attempt)


def list_quiz_attempts(
    db: Session,
    *,
    report_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    attempts = (
        db.query(QuizAttempt)
        .filter(QuizAttempt.report_id == report_id, QuizAttempt.user_id == user_id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )
    return [serialize_quiz_attempt(attempt) for attempt in attempts]


def serialize_quiz_attempt(attempt: QuizAttempt) -> dict[str, Any]:
    return {
        "attempt_id": str(attempt.id),
        "report_id": str(attempt.report_id),
        "user_id": str(attempt.user_id),
        "answers": attempt.answers or {},
        "score_correct": attempt.score_correct,
        "score_total": attempt.score_total,
        "score_percent": attempt.score_percent,
        "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _call_llm(prompt: str, provider: str, api_key: str, base_url: str | None, model: str) -> str:
    if provider == "gemini":
        return _call_gemini(prompt, api_key=api_key, model=model)
    return _call_openai(prompt, api_key=api_key, base_url=base_url, model=model)


def _call_llm_json(prompt: str, provider: str, api_key: str, base_url: str | None, model: str) -> str:
    if provider == "gemini":
        return _call_gemini(prompt, api_key=api_key, model=model)
    return _call_openai_json(prompt, api_key=api_key, base_url=base_url, model=model)


def _call_openai(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
    kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content
        return content.strip() if content else ""
    except Exception as exc:
        raise ReportError(
            "OpenAI request failed during report generation.",
            code="REPORT_UPSTREAM_ERROR",
            status_code=502,
            details={"provider": "openai", "reason": str(exc)[:240]},
        ) from exc


def _call_openai_json(prompt: str, api_key: str, base_url: str | None, model: str) -> str:
    kwargs: dict[str, Any] = {"api_key": api_key, "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return content.strip() if content else "{}"
    except Exception as exc:
        raise ReportError(
            "OpenAI request failed during report generation.",
            code="REPORT_UPSTREAM_ERROR",
            status_code=502,
            details={"provider": "openai", "reason": str(exc)[:240]},
        ) from exc


def _call_gemini(prompt: str, api_key: str, model: str) -> str:
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        content = getattr(response, "text", None)
        return content.strip() if content else ""
    except Exception as exc:
        raise ReportError(
            "Gemini request failed during report generation.",
            code="REPORT_UPSTREAM_ERROR",
            status_code=502,
            details={"provider": "gemini", "reason": str(exc)[:240]},
        ) from exc
    finally:
        client.close()


def _format_findings_for_report(insight: dict[str, Any]) -> str:
    """Turn structured insight findings into a readable text block for the report prompt."""
    lines: list[str] = [f"Summary: {insight.get('summary', '')}"]
    for finding in insight.get("findings", []):
        theme = finding.get("theme", "Finding")
        lines.append(f"\n## {theme}")
        for pt in finding.get("points", []):
            lines.append(f"- {pt}")
    used_titles = list({c["title"] for c in insight.get("citations", []) if c.get("title")})
    if used_titles:
        lines.append("\nSources used: " + ", ".join(used_titles))
    return "\n".join(lines)


def _derive_title(query: str, report_type: str) -> str:
    truncated = query[:80].strip()
    label = {
        "research_brief": "Research Brief",
        "summary": "Summary",
        "comparison": "Comparison",
        "action_items": "Action Items",
        "risk_analysis": "Risk Analysis",
        "executive_brief": "Executive Brief",
        "conflict_mesh": "Conflict Mesh",
        "flashcards": "Flashcards",
        "quiz": "Quiz",
        "study_guide": "Study Guide",
        "mind_map": "Mind Map",
    }.get(report_type, "Report")
    return f"{label}: {truncated}"


def _build_evidence_snapshot(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    for index, citation in enumerate(citations, start=1):
        quote = str(citation.get("quote") or "")
        snapshot.append(
            {
                "index": index,
                "citation_id": citation.get("citation_id"),
                "source_id": citation.get("source_id"),
                "document_id": citation.get("document_id"),
                "chunk_id": citation.get("chunk_id"),
                "title": citation.get("title"),
                "url": citation.get("url"),
                "page_number": citation.get("page_number"),
                "quote_hash": hashlib.sha256(quote.encode("utf-8")).hexdigest()[:16]
                if quote
                else None,
                "quote_preview": _preview(quote),
            }
        )
    return snapshot


def _preview(value: str, *, limit: int = 360) -> str:
    clean = " ".join(value.split())
    if len(clean) <= limit:
        return clean
    return f"{clean[: limit - 3]}..."


def _get_actionable_prompt_template(report_type: str) -> str:
    if report_type == "action_items":
        return _ACTION_ITEMS_PROMPT_TEMPLATE
    if report_type == "risk_analysis":
        return _RISK_ANALYSIS_PROMPT_TEMPLATE
    return _EXECUTIVE_BRIEF_PROMPT_TEMPLATE


def _build_evidence_blocks(db: Session, citations: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    chunk_ids: list[uuid.UUID] = []
    citation_by_chunk_id: dict[str, dict[str, Any]] = {}
    for citation in citations:
        chunk_id = citation.get("chunk_id")
        if not chunk_id:
            continue
        try:
            chunk_uuid = uuid.UUID(str(chunk_id))
        except (TypeError, ValueError):
            continue
        chunk_ids.append(chunk_uuid)
        citation_by_chunk_id[str(chunk_uuid)] = citation

    if not chunk_ids:
        return "No evidence snippets available.", citations

    chunks = db.query(Chunk).filter(Chunk.id.in_(chunk_ids)).all()
    chunk_by_id = {str(chunk.id): chunk for chunk in chunks}
    evidence_entries: list[str] = []
    evidence_citations: list[dict[str, Any]] = []

    for index, chunk_id in enumerate(dict.fromkeys(str(item) for item in chunk_ids), start=1):
        citation = citation_by_chunk_id.get(chunk_id)
        chunk = chunk_by_id.get(chunk_id)
        if not citation or not chunk:
            continue
        title = citation.get("title") or f"Source {index}"
        snippet = chunk.content.strip().replace("\n", " ")
        evidence_entries.append(f"[{index}] {title}\n{snippet}")
        evidence_citations.append(citation)

    if not evidence_entries:
        return "No evidence snippets available.", citations
    return "\n\n".join(evidence_entries), evidence_citations


def _load_flashcard_chunks(db: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(Chunk, Document, Source)
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .filter(
            Source.project_id == project_id,
            Chunk.embedding_model == LOCAL_EMBEDDING_MODEL,
        )
        .order_by(Source.created_at.asc(), Document.created_at.asc(), Chunk.chunk_index.asc())
        .all()
    )
    evidence: list[dict[str, Any]] = []
    for chunk, document, source in rows:
        content = _coerce_string(chunk.content)
        if not content:
            continue
        source_metadata = source.source_metadata if isinstance(source.source_metadata, dict) else {}
        chunk_metadata = chunk.chunk_metadata if isinstance(chunk.chunk_metadata, dict) else {}
        title = _coerce_string(
            chunk_metadata.get("title") or document.title or source.original_uri,
            "Imported source",
        )
        citation = {
            "citation_id": str(chunk.id),
            "source_id": str(source.id),
            "source_type": source.type,
            "document_id": str(document.id),
            "chunk_id": str(chunk.id),
            "title": title,
            "url": str(chunk_metadata.get("url") or source_metadata.get("external_url") or ""),
            "page_number": chunk_metadata.get("page_number"),
            "quote": content,
        }
        evidence.append(
            {
                "content": content,
                "chunk_index": chunk.chunk_index,
                "title": title,
                "citation": citation,
            }
        )
    return evidence


def _chunk_list(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _format_flashcard_evidence(batch: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    blocks: list[str] = []
    citations: list[dict[str, Any]] = []
    for index, item in enumerate(batch, start=1):
        citation = item["citation"]
        citations.append(citation)
        page = citation.get("page_number")
        page_label = f" p.{page}" if page else ""
        content = _preview(item["content"], limit=1800)
        blocks.append(f"[{index}] {item['title']}{page_label}\n{content}")
    return "\n\n".join(blocks), citations


def _normalize_flashcards_batch_payload(
    parsed: dict[str, Any],
    citations: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    raw_cards = parsed.get("cards")
    if isinstance(raw_cards, list):
        for raw_card in raw_cards:
            if not isinstance(raw_card, dict):
                continue
            front = _coerce_string(raw_card.get("front") or raw_card.get("question"))
            back = _coerce_string(raw_card.get("back") or raw_card.get("answer"))
            if not front or not back:
                continue
            card_citations = _map_citation_indexes(raw_card.get("citation_indexes"), citations)
            if not card_citations:
                card_citations = citations[:1]
            cards.append(
                {
                    "id": str(uuid.uuid4()),
                    "front": front,
                    "back": back,
                    "explanation": _coerce_string(raw_card.get("explanation"), back),
                    "difficulty": _coerce_enum(
                        raw_card.get("difficulty"),
                        {"easy", "medium", "hard"},
                        "medium",
                    ),
                    "tags": _coerce_string_list(raw_card.get("tags"), max_items=5),
                    "citations": card_citations,
                }
            )
    if cards:
        return {
            "overview": _coerce_string(parsed.get("overview"), f"Flashcards generated for: {query}"),
            "cards": cards,
        }
    return {
        "overview": f"Flashcards generated for: {query}",
        "cards": _fallback_flashcards(
            [{"content": citation.get("quote", ""), "title": citation.get("title", ""), "citation": citation}
             for citation in citations],
            query,
        ),
    }


def _fallback_flashcards(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for item in items:
        citation = item["citation"]
        content = _coerce_string(item.get("content") or citation.get("quote"))
        title = _coerce_string(item.get("title") or citation.get("title"), "this source")
        if not content:
            continue
        cards.append(
            {
                "id": str(uuid.uuid4()),
                "front": f"What is the key point from {title}?",
                "back": _preview(content, limit=180),
                "explanation": _preview(content, limit=360),
                "difficulty": "medium",
                "tags": _fallback_flashcard_tags(query, title),
                "citations": [citation],
            }
        )
        if len(cards) >= _FLASHCARDS_MAX_CARDS:
            break
    return cards


def _fallback_flashcard_tags(query: str, title: str) -> list[str]:
    tags = []
    for value in (query, title):
        cleaned = _coerce_string(value)
        if cleaned:
            tags.append(_preview(cleaned, limit=32))
    return tags[:3]


def _normalize_quiz_batch_payload(
    parsed: dict[str, Any],
    citations: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []
    raw_questions = parsed.get("questions")
    if isinstance(raw_questions, list):
        for raw_question in raw_questions:
            if not isinstance(raw_question, dict):
                continue
            question_text = _coerce_string(raw_question.get("question"))
            if not question_text:
                continue
            question_type = _coerce_enum(
                raw_question.get("type"),
                {"multiple_choice", "true_false"},
                "multiple_choice",
            )
            options = _normalize_quiz_options(raw_question.get("options"), question_type)
            if not options:
                continue
            correct_option_id = _coerce_string(raw_question.get("correct_option_id")).lower()
            option_ids = {option["id"] for option in options}
            if correct_option_id not in option_ids:
                correct_option_id = options[0]["id"]
            question_citations = _map_citation_indexes(raw_question.get("citation_indexes"), citations)
            if not question_citations:
                question_citations = citations[:1]
            questions.append(
                {
                    "id": str(uuid.uuid4()),
                    "type": question_type,
                    "question": question_text,
                    "options": options,
                    "correct_option_id": correct_option_id,
                    "explanation": _coerce_string(raw_question.get("explanation"), question_text),
                    "difficulty": _coerce_enum(
                        raw_question.get("difficulty"),
                        {"easy", "medium", "hard"},
                        "medium",
                    ),
                    "tags": _coerce_string_list(raw_question.get("tags"), max_items=5),
                    "citations": question_citations,
                }
            )
    if questions:
        return {
            "overview": _coerce_string(parsed.get("overview"), f"Quiz generated for: {query}"),
            "questions": questions,
        }
    return {
        "overview": f"Quiz generated for: {query}",
        "questions": _fallback_quiz_questions(
            [{"content": citation.get("quote", ""), "title": citation.get("title", ""), "citation": citation}
             for citation in citations],
            query,
        ),
    }


def _normalize_quiz_options(raw_options: Any, question_type: str) -> list[dict[str, str]]:
    if question_type == "true_false":
        raw_correct = _extract_option_text_by_id(raw_options, {"true", "false"})
        return [
            {"id": "true", "text": raw_correct.get("true", "True")},
            {"id": "false", "text": raw_correct.get("false", "False")},
        ]

    if not isinstance(raw_options, list):
        return []
    normalized: list[dict[str, str]] = []
    allowed_ids = ["a", "b", "c", "d"]
    for index, raw_option in enumerate(raw_options[:4]):
        if isinstance(raw_option, dict):
            text = _coerce_string(raw_option.get("text"))
            option_id = _coerce_string(raw_option.get("id")).lower()
        else:
            text = _coerce_string(raw_option)
            option_id = ""
        if not text:
            continue
        normalized.append(
            {
                "id": option_id if option_id in allowed_ids else allowed_ids[index],
                "text": text,
            }
        )
    seen_ids: set[str] = set()
    deduped: list[dict[str, str]] = []
    for index, option in enumerate(normalized):
        option_id = option["id"]
        if option_id in seen_ids:
            option_id = allowed_ids[index]
        seen_ids.add(option_id)
        deduped.append({"id": option_id, "text": option["text"]})
    return deduped if len(deduped) == 4 else []


def _extract_option_text_by_id(raw_options: Any, allowed_ids: set[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    if not isinstance(raw_options, list):
        return values
    for raw_option in raw_options:
        if not isinstance(raw_option, dict):
            continue
        option_id = _coerce_string(raw_option.get("id")).lower()
        text = _coerce_string(raw_option.get("text"))
        if option_id in allowed_ids and text:
            values[option_id] = text
    return values


def _fallback_quiz_questions(items: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for item in items:
        citation = item["citation"]
        content = _coerce_string(item.get("content") or citation.get("quote"))
        title = _coerce_string(item.get("title") or citation.get("title"), "this source")
        if not content:
            continue
        answer = _preview(content, limit=160)
        questions.append(
            {
                "id": str(uuid.uuid4()),
                "type": "multiple_choice",
                "question": f"What is a key point from {title}?",
                "options": [
                    {"id": "a", "text": answer},
                    {"id": "b", "text": "This is not supported by the indexed source."},
                    {"id": "c", "text": "The source does not discuss this topic."},
                    {"id": "d", "text": "The evidence states the opposite."},
                ],
                "correct_option_id": "a",
                "explanation": _preview(content, limit=360),
                "difficulty": "medium",
                "tags": _fallback_flashcard_tags(query, title),
                "citations": [citation],
            }
        )
        if len(questions) >= _QUIZ_MAX_QUESTIONS:
            break
    return questions


def _normalize_study_guide_batch_payload(
    parsed: dict[str, Any],
    citations: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    sections = _normalize_study_guide_sections(parsed.get("sections"), citations)
    key_concepts = _normalize_study_guide_concepts(parsed.get("key_concepts"), citations)
    timeline = _normalize_study_guide_timeline(parsed.get("timeline"), citations)
    review_questions = _normalize_study_guide_review_questions(parsed.get("review_questions"), citations)
    if any((sections, key_concepts, timeline, review_questions)):
        return {
            "overview": _coerce_string(parsed.get("overview"), f"Study guide generated for: {query}"),
            "sections": sections,
            "key_concepts": key_concepts,
            "timeline": timeline,
            "review_questions": review_questions,
        }
    return {
        "overview": f"Study guide generated for: {query}",
        **_fallback_study_guide(
            [{"content": citation.get("quote", ""), "title": citation.get("title", ""), "citation": citation}
             for citation in citations],
            query,
        ),
    }


def _normalize_study_guide_sections(
    raw_sections: Any,
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if not isinstance(raw_sections, list):
        return sections
    for raw_section in raw_sections:
        if not isinstance(raw_section, dict):
            continue
        title = _coerce_string(raw_section.get("title"))
        summary = _coerce_string(raw_section.get("summary"))
        if not title or not summary:
            continue
        section_citations = _map_citation_indexes(raw_section.get("citation_indexes"), citations)
        if not section_citations:
            section_citations = citations[:1]
        sections.append(
            {
                "id": str(uuid.uuid4()),
                "title": title,
                "summary": summary,
                "key_points": _coerce_string_list(raw_section.get("key_points"), max_items=8),
                "citations": section_citations,
            }
        )
    return sections


def _normalize_study_guide_concepts(
    raw_concepts: Any,
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    concepts: list[dict[str, Any]] = []
    if not isinstance(raw_concepts, list):
        return concepts
    for raw_concept in raw_concepts:
        if not isinstance(raw_concept, dict):
            continue
        term = _coerce_string(raw_concept.get("term"))
        definition = _coerce_string(raw_concept.get("definition"))
        if not term or not definition:
            continue
        concept_citations = _map_citation_indexes(raw_concept.get("citation_indexes"), citations)
        if not concept_citations:
            concept_citations = citations[:1]
        concepts.append(
            {
                "id": str(uuid.uuid4()),
                "term": term,
                "definition": definition,
                "importance": _coerce_string(raw_concept.get("importance"), definition),
                "citations": concept_citations,
            }
        )
    return concepts


def _normalize_study_guide_timeline(
    raw_timeline: Any,
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    if not isinstance(raw_timeline, list):
        return timeline
    for raw_item in raw_timeline:
        if not isinstance(raw_item, dict):
            continue
        label = _coerce_string(raw_item.get("label"))
        description = _coerce_string(raw_item.get("description"))
        if not label or not description:
            continue
        item_citations = _map_citation_indexes(raw_item.get("citation_indexes"), citations)
        if not item_citations:
            item_citations = citations[:1]
        timeline.append(
            {
                "id": str(uuid.uuid4()),
                "label": label,
                "description": description,
                "citations": item_citations,
            }
        )
    return timeline


def _normalize_study_guide_review_questions(
    raw_questions: Any,
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if not isinstance(raw_questions, list):
        return questions
    for raw_question in raw_questions:
        if not isinstance(raw_question, dict):
            continue
        question = _coerce_string(raw_question.get("question"))
        answer = _coerce_string(raw_question.get("answer"))
        if not question or not answer:
            continue
        question_citations = _map_citation_indexes(raw_question.get("citation_indexes"), citations)
        if not question_citations:
            question_citations = citations[:1]
        questions.append(
            {
                "id": str(uuid.uuid4()),
                "question": question,
                "answer": answer,
                "citations": question_citations,
            }
        )
    return questions


def _fallback_study_guide(items: list[dict[str, Any]], query: str) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    concepts: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in items:
        citation = item["citation"]
        content = _coerce_string(item.get("content") or citation.get("quote"))
        title = _coerce_string(item.get("title") or citation.get("title"), "Indexed source")
        if not content:
            continue
        title_key = _flashcard_fingerprint(title)
        if title_key not in seen_titles and len(sections) < _STUDY_GUIDE_MAX_SECTIONS:
            seen_titles.add(title_key)
            sections.append(
                {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "summary": _preview(content, limit=260),
                    "key_points": [_preview(content, limit=180)],
                    "citations": [citation],
                }
            )
        if len(concepts) < _STUDY_GUIDE_MAX_CONCEPTS:
            concepts.append(
                {
                    "id": str(uuid.uuid4()),
                    "term": _preview(title, limit=80),
                    "definition": _preview(content, limit=220),
                    "importance": "This item is directly supported by the indexed source material.",
                    "citations": [citation],
                }
            )
        if len(questions) < _STUDY_GUIDE_MAX_REVIEW_QUESTIONS:
            questions.append(
                {
                    "id": str(uuid.uuid4()),
                    "question": f"What is a key point from {title}?",
                    "answer": _preview(content, limit=220),
                    "citations": [citation],
                }
            )
    if not sections and items:
        first = items[0]
        citation = first["citation"]
        sections.append(
            {
                "id": str(uuid.uuid4()),
                "title": "Indexed source overview",
                "summary": _preview(_coerce_string(first.get("content") or citation.get("quote")), limit=260),
                "key_points": [],
                "citations": [citation],
            }
        )
    return {
        "sections": sections[:_STUDY_GUIDE_MAX_SECTIONS],
        "key_concepts": concepts[:_STUDY_GUIDE_MAX_CONCEPTS],
        "timeline": [],
        "review_questions": questions[:_STUDY_GUIDE_MAX_REVIEW_QUESTIONS],
    }


def _append_unique_study_guide_items(
    *,
    target: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    seen: set[str],
    key_name: str,
    limit: int,
) -> None:
    for item in candidates:
        fingerprint = _flashcard_fingerprint(_coerce_string(item.get(key_name)))
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        target.append(item)
        if len(target) >= limit:
            break


def _build_flashcards_overview(overview_parts: list[str], card_count: int, chunk_count: int) -> str:
    for overview in overview_parts:
        cleaned = _coerce_string(overview)
        if cleaned:
            return f"{cleaned} Generated {card_count} flashcards from {chunk_count} indexed chunks."
    return f"Generated {card_count} flashcards from {chunk_count} indexed chunks."


def _build_quiz_overview(overview_parts: list[str], question_count: int, chunk_count: int) -> str:
    for overview in overview_parts:
        cleaned = _coerce_string(overview)
        if cleaned:
            return f"{cleaned} Generated {question_count} quiz questions from {chunk_count} indexed chunks."
    return f"Generated {question_count} quiz questions from {chunk_count} indexed chunks."


def _build_study_guide_overview(
    *,
    overview_parts: list[str],
    section_count: int,
    concept_count: int,
    review_question_count: int,
    chunk_count: int,
) -> str:
    suffix = (
        f" Generated a study guide from {chunk_count} indexed chunks with "
        f"{section_count} sections, {concept_count} key concepts, and "
        f"{review_question_count} review questions."
    )
    for overview in overview_parts:
        cleaned = _coerce_string(overview)
        if cleaned:
            return f"{cleaned}{suffix}"
    return suffix.strip()


def _study_guide_payload_citations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return _unique_citations(
        citation
        for collection_name in ("sections", "key_concepts", "timeline", "review_questions")
        for item in payload.get(collection_name, [])
        if isinstance(item, dict)
        for citation in item.get("citations", [])
    )


def _normalize_mind_map_batch_payload(
    parsed: dict[str, Any],
    citations: list[dict[str, Any]],
    query: str,
) -> dict[str, Any]:
    central_topic = _coerce_string(parsed.get("central_topic"), _preview(query, limit=80) or "Mind Map")
    nodes = _normalize_mind_map_nodes(parsed.get("nodes"), citations, central_topic)
    edges = _normalize_mind_map_edges(parsed.get("edges"), nodes, citations)
    if nodes:
        return {
            "overview": _coerce_string(parsed.get("overview"), f"Mind map generated for: {query}"),
            "central_topic": central_topic,
            "nodes": nodes,
            "edges": edges,
        }
    fallback = _fallback_mind_map(
        [{"content": citation.get("quote", ""), "title": citation.get("title", ""), "citation": citation}
         for citation in citations],
        query,
    )
    return {"overview": f"Mind map generated for: {query}", **fallback}


def _normalize_mind_map_nodes(
    raw_nodes: Any,
    citations: list[dict[str, Any]],
    central_topic: str,
) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    raw_to_node_id: dict[str, str] = {}
    if isinstance(raw_nodes, list):
        for index, raw_node in enumerate(raw_nodes[:_MIND_MAP_MAX_NODES], start=1):
            if not isinstance(raw_node, dict):
                continue
            label = _coerce_string(raw_node.get("label") or raw_node.get("name"))
            if not label:
                continue
            raw_id = _coerce_string(raw_node.get("id"), label)
            node_id = _mind_map_node_id(raw_id or label, index)
            raw_to_node_id[raw_id] = node_id
            raw_to_node_id[_flashcard_fingerprint(raw_id)] = node_id
            raw_to_node_id[_flashcard_fingerprint(label)] = node_id
            node_citations = _map_citation_indexes(raw_node.get("citation_indexes"), citations)
            if not node_citations:
                node_citations = citations[:1]
            nodes.append(
                {
                    "id": node_id,
                    "label": _preview(label, limit=80),
                    "type": _coerce_mind_map_node_type(raw_node.get("type")),
                    "summary": _coerce_string(raw_node.get("summary") or raw_node.get("description")),
                    "level": _coerce_mind_map_level(raw_node.get("level")),
                    "parent_id": _coerce_string(raw_node.get("parent_id")) or None,
                    "citations": node_citations,
                }
            )

    if nodes and not any(node.get("type") == "central" or node.get("level") == 0 for node in nodes):
        nodes.insert(
            0,
            {
                "id": "central-topic",
                "label": _preview(central_topic, limit=80),
                "type": "central",
                "summary": f"Central topic for this mind map: {central_topic}",
                "level": 0,
                "parent_id": None,
                "citations": citations[:1],
            },
        )
        raw_to_node_id[_flashcard_fingerprint(central_topic)] = "central-topic"

    for node in nodes:
        parent_id = node.get("parent_id")
        if not parent_id:
            continue
        mapped_parent_id = raw_to_node_id.get(str(parent_id)) or raw_to_node_id.get(_flashcard_fingerprint(str(parent_id)))
        node["parent_id"] = mapped_parent_id if mapped_parent_id != node["id"] else None
    return nodes


def _normalize_mind_map_edges(
    raw_edges: Any,
    nodes: list[dict[str, Any]],
    citations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    node_ids = {node["id"] for node in nodes}
    endpoint_by_label = {_flashcard_fingerprint(node.get("label", "")): node["id"] for node in nodes}
    edges: list[dict[str, Any]] = []
    if isinstance(raw_edges, list):
        for index, raw_edge in enumerate(raw_edges[:_MIND_MAP_MAX_EDGES], start=1):
            if not isinstance(raw_edge, dict):
                continue
            source = _resolve_mind_map_endpoint(raw_edge.get("source"), node_ids, endpoint_by_label)
            target = _resolve_mind_map_endpoint(raw_edge.get("target"), node_ids, endpoint_by_label)
            if not source or not target or source == target:
                continue
            edge_citations = _map_citation_indexes(raw_edge.get("citation_indexes"), citations)
            if not edge_citations:
                edge_citations = citations[:1]
            edges.append(
                {
                    "id": _mind_map_edge_id(raw_edge.get("id"), source, target, index),
                    "source": source,
                    "target": target,
                    "type": _coerce_mind_map_edge_type(raw_edge.get("type")),
                    "description": _coerce_string(
                        raw_edge.get("description"),
                        "Related based on indexed project evidence.",
                    ),
                    "citations": edge_citations,
                }
            )

    seen_parent_edges = {
        (edge["source"], edge["target"])
        for edge in edges
        if edge.get("type") == "parent_child"
    }
    for node in nodes:
        parent_id = node.get("parent_id")
        if not parent_id or parent_id not in node_ids or parent_id == node["id"]:
            continue
        if (parent_id, node["id"]) in seen_parent_edges:
            continue
        edges.append(
            {
                "id": f"parent-{parent_id}-{node['id']}"[:80],
                "source": parent_id,
                "target": node["id"],
                "type": "parent_child",
                "description": f"{node['label']} belongs under {parent_id} in the mind map hierarchy.",
                "citations": node.get("citations", [])[:2],
            }
        )
        seen_parent_edges.add((parent_id, node["id"]))
    return edges[:_MIND_MAP_MAX_EDGES]


def _merge_mind_map_nodes(
    *,
    target: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    node_id_by_label: dict[str, str],
    used_node_ids: set[str],
    limit: int,
) -> dict[str, str]:
    local_to_global: dict[str, str] = {}
    node_by_id = {node["id"]: node for node in target}
    pending_parent_updates: list[tuple[str, str]] = []
    for candidate in candidates:
        local_id = str(candidate.get("id") or "")
        fingerprint = _flashcard_fingerprint(candidate.get("label", ""))
        if not fingerprint:
            continue
        existing_id = node_id_by_label.get(fingerprint)
        if existing_id:
            local_to_global[local_id] = existing_id
            existing = node_by_id.get(existing_id)
            if existing:
                existing["citations"] = _unique_citations(
                    [*existing.get("citations", []), *candidate.get("citations", [])]
                )
                if not existing.get("summary") and candidate.get("summary"):
                    existing["summary"] = candidate["summary"]
                existing["level"] = min(int(existing.get("level", _MIND_MAP_MAX_DEPTH)), int(candidate.get("level", 1)))
                if candidate.get("type") == "central":
                    existing["type"] = "central"
            continue
        if len(target) >= limit:
            continue
        global_id = _unique_mind_map_node_id(candidate.get("id") or candidate.get("label"), used_node_ids)
        node = {**candidate, "id": global_id}
        target.append(node)
        node_by_id[global_id] = node
        used_node_ids.add(global_id)
        node_id_by_label[fingerprint] = global_id
        local_to_global[local_id] = global_id
        if candidate.get("parent_id"):
            pending_parent_updates.append((global_id, str(candidate["parent_id"])))

    for global_id, local_parent_id in pending_parent_updates:
        parent_global_id = local_to_global.get(local_parent_id)
        if parent_global_id and parent_global_id != global_id and global_id in node_by_id:
            node_by_id[global_id]["parent_id"] = parent_global_id
    return local_to_global


def _merge_mind_map_edges(
    *,
    target: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    local_to_global: dict[str, str],
    seen_edges: set[str],
    limit: int,
) -> None:
    for candidate in candidates:
        if len(target) >= limit:
            break
        source = local_to_global.get(str(candidate.get("source"))) or str(candidate.get("source") or "")
        target_id = local_to_global.get(str(candidate.get("target"))) or str(candidate.get("target") or "")
        if not source or not target_id or source == target_id:
            continue
        edge_type = _coerce_mind_map_edge_type(candidate.get("type"))
        fingerprint = f"{source}->{target_id}:{edge_type}"
        if fingerprint in seen_edges:
            continue
        seen_edges.add(fingerprint)
        target.append(
            {
                **candidate,
                "id": _unique_mind_map_edge_id(candidate.get("id"), source, target_id, len(target) + 1),
                "source": source,
                "target": target_id,
                "type": edge_type,
            }
        )


def _fallback_mind_map(items: list[dict[str, Any]], query: str) -> dict[str, Any]:
    central_topic = _preview(query, limit=80) or "Mind Map"
    central_node = {
        "id": "central-topic",
        "label": central_topic,
        "type": "central",
        "summary": f"Central topic for this mind map: {central_topic}",
        "level": 0,
        "parent_id": None,
        "citations": [],
    }
    nodes = [central_node]
    edges: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for index, item in enumerate(items[: _MIND_MAP_MAX_NODES - 1], start=1):
        citation = item["citation"]
        content = _coerce_string(item.get("content") or citation.get("quote"))
        title = _coerce_string(item.get("title") or citation.get("title"), f"Source {index}")
        if not content:
            continue
        fingerprint = _flashcard_fingerprint(title)
        if fingerprint in seen_titles:
            continue
        seen_titles.add(fingerprint)
        node_id = _mind_map_node_id(title, index)
        nodes.append(
            {
                "id": node_id,
                "label": _preview(title, limit=80),
                "type": "source",
                "summary": _preview(content, limit=260),
                "level": 1,
                "parent_id": "central-topic",
                "citations": [citation],
            }
        )
        edges.append(
            {
                "id": f"central-{node_id}"[:80],
                "source": "central-topic",
                "target": node_id,
                "type": "parent_child",
                "description": f"{title} supports the mind map topic.",
                "citations": [citation],
            }
        )
    return {
        "overview": f"Generated a fallback mind map from {len(items)} indexed chunks.",
        "central_topic": central_topic,
        "nodes": nodes,
        "edges": edges,
    }


def _finalize_mind_map_payload(
    *,
    overview: str,
    central_topic: str,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> dict[str, Any]:
    if not any(node.get("type") == "central" or node.get("level") == 0 for node in nodes):
        nodes = [
            {
                "id": "central-topic",
                "label": _preview(central_topic, limit=80),
                "type": "central",
                "summary": f"Central topic for this mind map: {central_topic}",
                "level": 0,
                "parent_id": None,
                "citations": [],
            },
            *nodes,
        ]
    valid_node_ids = {node["id"] for node in nodes}
    valid_edges = [
        edge
        for edge in edges
        if edge.get("source") in valid_node_ids and edge.get("target") in valid_node_ids
    ]
    return {
        "overview": overview,
        "central_topic": central_topic,
        "nodes": nodes[:_MIND_MAP_MAX_NODES],
        "edges": valid_edges[:_MIND_MAP_MAX_EDGES],
    }


def _build_mind_map_overview(
    overview_parts: list[str],
    node_count: int,
    edge_count: int,
    chunk_count: int,
) -> str:
    suffix = f" Generated a 2D mind map from {chunk_count} indexed chunks with {node_count} nodes and {edge_count} relationships."
    for overview in overview_parts:
        cleaned = _coerce_string(overview)
        if cleaned:
            return f"{cleaned}{suffix}"
    return suffix.strip()


def _mind_map_payload_citations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return _unique_citations(
        citation
        for collection_name in ("nodes", "edges")
        for item in payload.get(collection_name, [])
        if isinstance(item, dict)
        for citation in item.get("citations", [])
    )


def _mind_map_node_id(value: Any, index: int) -> str:
    fingerprint = _flashcard_fingerprint(_coerce_string(value))
    if not fingerprint:
        return f"node-{index}"
    return re.sub(r"[^a-z0-9]+", "-", fingerprint).strip("-")[:72] or f"node-{index}"


def _unique_mind_map_node_id(value: Any, used_node_ids: set[str]) -> str:
    base = _mind_map_node_id(value, len(used_node_ids) + 1)
    candidate = base
    suffix = 2
    while candidate in used_node_ids:
        candidate = f"{base}-{suffix}"[:80]
        suffix += 1
    return candidate


def _mind_map_edge_id(value: Any, source: str, target: str, index: int) -> str:
    cleaned = _mind_map_node_id(value, index) if _coerce_string(value) else ""
    if cleaned and cleaned != f"node-{index}":
        return cleaned
    return f"edge-{source}-{target}-{index}"[:80]


def _unique_mind_map_edge_id(value: Any, source: str, target: str, index: int) -> str:
    return _mind_map_edge_id(value, source, target, index)


def _resolve_mind_map_endpoint(
    value: Any,
    node_ids: set[str],
    endpoint_by_label: dict[str, str],
) -> str:
    endpoint = _coerce_string(value)
    if endpoint in node_ids:
        return endpoint
    return endpoint_by_label.get(_flashcard_fingerprint(endpoint), "")


def _coerce_mind_map_node_type(value: Any) -> str:
    cleaned = _coerce_string(value).lower()
    if cleaned in {"central", "topic", "subtopic", "concept", "source"}:
        return cleaned
    return "concept"


def _coerce_mind_map_edge_type(value: Any) -> str:
    cleaned = _coerce_string(value).lower()
    if cleaned in {"parent_child", "relates_to", "supports"}:
        return cleaned
    return "relates_to"


def _coerce_mind_map_level(value: Any) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 1
    return max(0, min(level, _MIND_MAP_MAX_DEPTH))


def _flashcard_fingerprint(front: str) -> str:
    normalized = "".join(
        character
        for character in unicodedata.normalize("NFKD", front)
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", normalized.lower()).strip()


def _unique_citations(citations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for citation in citations:
        key = str(citation.get("citation_id") or citation.get("chunk_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique


def _parse_actionable_payload(
    *,
    report_type: str,
    raw: str,
    citations: list[dict[str, Any]],
    insight_result: dict[str, Any],
) -> dict[str, Any]:
    parsed = _load_json_object(raw)
    if report_type == "action_items":
        return _normalize_action_items_payload(parsed, citations, insight_result)
    if report_type == "risk_analysis":
        return _normalize_risk_analysis_payload(parsed, citations, insight_result)
    return _normalize_executive_brief_payload(parsed, citations, insight_result)


def _load_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    for candidate in (text, _extract_json_object_text(text)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def _extract_json_object_text(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text[start:], start=start):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _normalize_action_items_payload(
    parsed: dict[str, Any],
    citations: list[dict[str, Any]],
    insight_result: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    raw_items = parsed.get("items")
    if isinstance(raw_items, list):
        for raw_item in raw_items[:7]:
            if not isinstance(raw_item, dict):
                continue
            items.append(
                {
                    "id": str(uuid.uuid4()),
                    "title": _coerce_string(raw_item.get("title"), "Untitled action"),
                    "description": _coerce_string(raw_item.get("description")),
                    "priority": _coerce_enum(raw_item.get("priority"), {"high", "medium", "low"}, "medium"),
                    "owner_suggested": _coerce_optional_string(raw_item.get("owner_suggested")),
                    "due_date_suggested": _coerce_optional_string(raw_item.get("due_date_suggested")),
                    "status": _coerce_enum(
                        raw_item.get("status"),
                        {"open", "needs_review", "done"},
                        "open",
                    ),
                    "citations": _map_citation_indexes(raw_item.get("citation_indexes"), citations),
                }
            )
    if not items:
        items = _fallback_action_items(insight_result, citations)
    return {
        "overview": _coerce_string(
            parsed.get("overview"),
            insight_result.get("summary", "Suggested actions based on indexed evidence."),
        ),
        "items": items,
    }


def _normalize_risk_analysis_payload(
    parsed: dict[str, Any],
    citations: list[dict[str, Any]],
    insight_result: dict[str, Any],
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    raw_items = parsed.get("items")
    if isinstance(raw_items, list):
        for raw_item in raw_items[:6]:
            if not isinstance(raw_item, dict):
                continue
            items.append(
                {
                    "id": str(uuid.uuid4()),
                    "title": _coerce_string(raw_item.get("title"), "Untitled risk"),
                    "severity": _coerce_enum(raw_item.get("severity"), {"high", "medium", "low"}, "medium"),
                    "why_it_matters": _coerce_string(raw_item.get("why_it_matters")),
                    "recommended_action": _coerce_string(raw_item.get("recommended_action")),
                    "status": _coerce_enum(
                        raw_item.get("status"),
                        {"open", "needs_review", "accepted"},
                        "open",
                    ),
                    "citations": _map_citation_indexes(raw_item.get("citation_indexes"), citations),
                }
            )
    if not items:
        items = _fallback_risk_items(insight_result, citations)
    return {
        "overview": _coerce_string(
            parsed.get("overview"),
            insight_result.get("summary", "Potential risks extracted from indexed evidence."),
        ),
        "items": items,
    }


def _normalize_executive_brief_payload(
    parsed: dict[str, Any],
    citations: list[dict[str, Any]],
    insight_result: dict[str, Any],
) -> dict[str, Any]:
    if parsed:
        payload = {
            "summary": _coerce_string(parsed.get("summary"), insight_result.get("summary", "")),
            "key_points": _coerce_string_list(parsed.get("key_points"), max_items=5),
            "decisions_needed": _coerce_string_list(parsed.get("decisions_needed"), max_items=5),
            "next_steps": _coerce_string_list(parsed.get("next_steps"), max_items=5),
            "citations": _map_citation_indexes(parsed.get("citation_indexes"), citations),
        }
        if payload["summary"] or payload["key_points"] or payload["decisions_needed"] or payload["next_steps"]:
            if not payload["citations"]:
                payload["citations"] = citations[:3]
            return payload
    return _fallback_executive_brief(insight_result, citations)


def _map_citation_indexes(raw_indexes: Any, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(raw_indexes, list):
        return citations[:2]
    mapped: list[dict[str, Any]] = []
    for raw_index in raw_indexes:
        if not isinstance(raw_index, int):
            continue
        offset = raw_index - 1
        if 0 <= offset < len(citations):
            mapped.append(citations[offset])
    unique: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for citation in mapped:
        key = str(citation.get("citation_id") or citation.get("chunk_id") or "")
        if key in seen_ids:
            continue
        seen_ids.add(key)
        unique.append(citation)
    return unique[:3]


def _coerce_string(value: Any, fallback: str = "") -> str:
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return fallback


def _coerce_optional_string(value: Any) -> str | None:
    cleaned = _coerce_string(value)
    return cleaned or None


def _coerce_enum(value: Any, allowed: set[str], fallback: str) -> str:
    cleaned = _coerce_string(value).lower()
    if cleaned in allowed:
        return cleaned
    return fallback


def _coerce_string_list(value: Any, *, max_items: int) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for raw_item in value[:max_items]:
        cleaned = _coerce_string(raw_item)
        if cleaned:
            items.append(cleaned)
    return items


def _fallback_action_items(insight_result: dict[str, Any], citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for finding in insight_result.get("findings", [])[:5]:
        points = finding.get("points", [])
        if not points:
            continue
        items.append(
            {
                "id": str(uuid.uuid4()),
                "title": finding.get("theme", "Follow up"),
                "description": _coerce_string(points[0], "Review the supporting evidence."),
                "priority": "medium",
                "owner_suggested": None,
                "due_date_suggested": None,
                "status": "needs_review",
                "citations": citations[:2],
            }
        )
    if items:
        return items
    return [
        {
            "id": str(uuid.uuid4()),
            "title": "Review indexed evidence",
            "description": "The extracted evidence should be reviewed manually before taking action.",
            "priority": "medium",
            "owner_suggested": None,
            "due_date_suggested": None,
            "status": "needs_review",
            "citations": citations[:2],
        }
    ]


def _fallback_risk_items(insight_result: dict[str, Any], citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for finding in insight_result.get("findings", [])[:5]:
        points = finding.get("points", [])
        if not points:
            continue
        items.append(
            {
                "id": str(uuid.uuid4()),
                "title": finding.get("theme", "Potential risk"),
                "severity": "medium",
                "why_it_matters": _coerce_string(points[0], "This item may require review."),
                "recommended_action": "Validate the supporting evidence and decide on mitigation.",
                "status": "needs_review",
                "citations": citations[:2],
            }
        )
    if items:
        return items
    return [
        {
            "id": str(uuid.uuid4()),
            "title": "Insufficient evidence for risk scoring",
            "severity": "medium",
            "why_it_matters": "The current evidence is not strong enough to infer concrete risks.",
            "recommended_action": "Review the indexed sources manually.",
            "status": "needs_review",
            "citations": citations[:2],
        }
    ]


def _fallback_executive_brief(
    insight_result: dict[str, Any],
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    key_points: list[str] = []
    for finding in insight_result.get("findings", [])[:4]:
        for point in finding.get("points", [])[:1]:
            cleaned = _coerce_string(point)
            if cleaned:
                key_points.append(cleaned)
    return {
        "summary": insight_result.get("summary", "Executive brief generated from indexed evidence."),
        "key_points": key_points[:5],
        "decisions_needed": ["Review the evidence and confirm the recommended direction."],
        "next_steps": ["Share the brief with the team and validate source-backed claims."],
        "citations": citations[:3],
    }


def _render_structured_payload_as_markdown(
    *,
    report_type: str,
    title: str,
    payload: dict[str, Any],
) -> str:
    if report_type == "action_items":
        return _render_action_items_markdown(title, payload)
    if report_type == "risk_analysis":
        return _render_risk_analysis_markdown(title, payload)
    if report_type == "flashcards":
        return _render_flashcards_markdown(title, payload)
    if report_type == "quiz":
        return _render_quiz_markdown(title, payload)
    if report_type == "study_guide":
        return _render_study_guide_markdown(title, payload)
    if report_type == "mind_map":
        return _render_mind_map_markdown(title, payload)
    return _render_executive_brief_markdown(title, payload)


def _render_action_items_markdown(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", "## Overview", payload.get("overview", ""), "", "## Action Items"]
    for index, item in enumerate(payload.get("items", []), start=1):
        lines.extend(
            [
                "",
                f"### {index}. {item.get('title', 'Untitled action')}",
                f"- Priority: {item.get('priority', 'medium')}",
                f"- Status: {item.get('status', 'open')}",
                f"- Owner: {item.get('owner_suggested') or 'Unassigned'}",
                f"- Due: {item.get('due_date_suggested') or 'Not specified'}",
                f"- Detail: {item.get('description', '')}",
                _format_citation_line(item.get("citations", [])),
            ]
        )
    return "\n".join(line for line in lines if line is not None)


def _render_risk_analysis_markdown(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", "## Overview", payload.get("overview", ""), "", "## Risk Register"]
    for index, item in enumerate(payload.get("items", []), start=1):
        lines.extend(
            [
                "",
                f"### {index}. {item.get('title', 'Untitled risk')}",
                f"- Severity: {item.get('severity', 'medium')}",
                f"- Status: {item.get('status', 'open')}",
                f"- Why it matters: {item.get('why_it_matters', '')}",
                f"- Recommended action: {item.get('recommended_action', '')}",
                _format_citation_line(item.get("citations", [])),
            ]
        )
    return "\n".join(line for line in lines if line is not None)


def _render_executive_brief_markdown(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", "## Summary", payload.get("summary", ""), "", "## Key Points"]
    for point in payload.get("key_points", []):
        lines.append(f"- {point}")
    lines.extend(["", "## Decisions Needed"])
    for point in payload.get("decisions_needed", []):
        lines.append(f"- {point}")
    lines.extend(["", "## Next Steps"])
    for point in payload.get("next_steps", []):
        lines.append(f"- {point}")
    lines.extend(["", _format_citation_line(payload.get("citations", []))])
    return "\n".join(line for line in lines if line is not None)


def _render_flashcards_markdown(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", "## Overview", payload.get("overview", ""), "", "## Cards"]
    for index, card in enumerate(payload.get("cards", []), start=1):
        tags = ", ".join(card.get("tags", [])) if isinstance(card.get("tags"), list) else ""
        lines.extend(
            [
                "",
                f"### {index}. {card.get('front', 'Untitled card')}",
                f"- Front: {card.get('front', '')}",
                f"- Back: {card.get('back', '')}",
                f"- Explanation: {card.get('explanation', '')}",
                f"- Difficulty: {card.get('difficulty', 'medium')}",
                f"- Tags: {tags or 'none'}",
                _format_citation_line(card.get("citations", [])),
            ]
        )
    return "\n".join(line for line in lines if line is not None)


def _render_quiz_markdown(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", "## Overview", payload.get("overview", ""), "", "## Questions"]
    for index, question in enumerate(payload.get("questions", []), start=1):
        tags = ", ".join(question.get("tags", [])) if isinstance(question.get("tags"), list) else ""
        options = question.get("options", [])
        correct_option_id = question.get("correct_option_id", "")
        correct_text = ""
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict) and option.get("id") == correct_option_id:
                    correct_text = str(option.get("text") or "")
                    break
        lines.extend(
            [
                "",
                f"### {index}. {question.get('question', 'Untitled question')}",
                f"- Type: {question.get('type', 'multiple_choice')}",
                f"- Difficulty: {question.get('difficulty', 'medium')}",
                f"- Tags: {tags or 'none'}",
                "- Options:",
            ]
        )
        if isinstance(options, list):
            for option in options:
                if isinstance(option, dict):
                    lines.append(f"  - {option.get('id')}: {option.get('text', '')}")
        lines.extend(
            [
                f"- Correct Answer: {correct_option_id} {correct_text}".strip(),
                f"- Explanation: {question.get('explanation', '')}",
                _format_citation_line(question.get("citations", [])),
            ]
        )
    return "\n".join(line for line in lines if line is not None)


def _render_study_guide_markdown(title: str, payload: dict[str, Any]) -> str:
    lines = [f"# {title}", "", "## Overview", payload.get("overview", "")]
    lines.extend(["", "## Sections"])
    for index, section in enumerate(payload.get("sections", []), start=1):
        if not isinstance(section, dict):
            continue
        lines.extend(
            [
                "",
                f"### {index}. {section.get('title', 'Untitled section')}",
                section.get("summary", ""),
            ]
        )
        key_points = section.get("key_points", [])
        if isinstance(key_points, list) and key_points:
            lines.append("")
            lines.append("Key Points:")
            for point in key_points:
                lines.append(f"- {point}")
        lines.append(_format_citation_line(section.get("citations", [])))

    lines.extend(["", "## Key Concepts"])
    for index, concept in enumerate(payload.get("key_concepts", []), start=1):
        if not isinstance(concept, dict):
            continue
        lines.extend(
            [
                "",
                f"### {index}. {concept.get('term', 'Untitled concept')}",
                f"- Definition: {concept.get('definition', '')}",
                f"- Importance: {concept.get('importance', '')}",
                _format_citation_line(concept.get("citations", [])),
            ]
        )

    lines.extend(["", "## Timeline"])
    timeline = payload.get("timeline", [])
    if isinstance(timeline, list) and timeline:
        for index, item in enumerate(timeline, start=1):
            if not isinstance(item, dict):
                continue
            lines.extend(
                [
                    "",
                    f"### {index}. {item.get('label', 'Untitled timeline item')}",
                    item.get("description", ""),
                    _format_citation_line(item.get("citations", [])),
                ]
            )
    else:
        lines.append("No timeline items were found in the indexed evidence.")

    lines.extend(["", "## Review Questions"])
    for index, question in enumerate(payload.get("review_questions", []), start=1):
        if not isinstance(question, dict):
            continue
        lines.extend(
            [
                "",
                f"### {index}. {question.get('question', 'Untitled question')}",
                f"- Answer: {question.get('answer', '')}",
                _format_citation_line(question.get("citations", [])),
            ]
        )
    return "\n".join(line for line in lines if line is not None)


def _render_mind_map_markdown(title: str, payload: dict[str, Any]) -> str:
    lines = [
        f"# {title}",
        "",
        "## Overview",
        payload.get("overview", ""),
        "",
        "## Central Topic",
        payload.get("central_topic", ""),
        "",
        "## Nodes",
    ]
    for index, node in enumerate(payload.get("nodes", []), start=1):
        if not isinstance(node, dict):
            continue
        lines.extend(
            [
                "",
                f"### {index}. {node.get('label', 'Untitled node')}",
                f"- Type: {node.get('type', 'concept')}",
                f"- Level: {node.get('level', 1)}",
                f"- Parent: {node.get('parent_id') or 'none'}",
                f"- Summary: {node.get('summary', '')}",
                _format_citation_line(node.get("citations", [])),
            ]
        )

    lines.extend(["", "## Relationships"])
    for index, edge in enumerate(payload.get("edges", []), start=1):
        if not isinstance(edge, dict):
            continue
        lines.extend(
            [
                "",
                f"### {index}. {edge.get('source', '')} -> {edge.get('target', '')}",
                f"- Type: {edge.get('type', 'relates_to')}",
                f"- Description: {edge.get('description', '')}",
                _format_citation_line(edge.get("citations", [])),
            ]
        )
    return "\n".join(line for line in lines if line is not None)


def _format_citation_line(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "- Sources: none"
    labels = []
    for citation in citations[:3]:
        labels.append(str(citation.get("title") or citation.get("chunk_id") or "Source"))
    return "- Sources: " + ", ".join(labels)
