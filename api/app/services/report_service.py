"""Report service: assemble a research report from insight synthesis."""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

import google.genai as genai
from openai import OpenAI
from sqlalchemy.orm import Session

from app.services.citation_service import hydrate_citations, hydrate_report_payload_citations
from app.services.insight_service import InsightError, generate_insight
from app.storage.models import Chunk, Report, ReportInsight
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

_ACTIONABLE_REPORT_TYPES = {"action_items", "risk_analysis", "executive_brief"}


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
            "structured_output": report_type in _ACTIONABLE_REPORT_TYPES,
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
    }.get(report_type, "Report")
    return f"{label}: {truncated}"


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
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return {}


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


def _format_citation_line(citations: list[dict[str, Any]]) -> str:
    if not citations:
        return "- Sources: none"
    labels = []
    for citation in citations[:3]:
        labels.append(str(citation.get("title") or citation.get("chunk_id") or "Source"))
    return "- Sources: " + ", ".join(labels)
