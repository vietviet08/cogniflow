"""Report service: assemble a research report from insight synthesis."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

import google.genai as genai
from openai import OpenAI
from sqlalchemy.orm import Session

from app.services.insight_service import InsightError, generate_insight
from app.storage.models import Report, ReportInsight
from app.storage.repositories.processing_run_repository import ProcessingRunRepository


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


def generate_report(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    report_type: str,
    format: str,
    provider: str,
) -> dict[str, Any]:
    """Generate a structured research report backed by RAG insights."""
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
    prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]
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
            "insight_id": insight_result["insight_id"],
        },
    )

    report = Report(
        project_id=project_id,
        title=title,
        report_type=report_type,
        format=format,
        content=report_content,
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

    return {
        "report_id": str(report.id),
        "title": title,
        "type": report_type,
        "format": format,
        "content": report_content,
        "status": "completed",
        "run_id": str(run.id),
        "insight_id": insight_result["insight_id"],
        "source_ids": source_ids,
        "citations": insight_result["citations"],
    }


def get_report_lineage(db: Session, report_id: uuid.UUID) -> dict[str, Any]:
    """Return lineage info for a given report."""
    from app.storage.models import ReportInsight

    links = db.query(ReportInsight).filter(ReportInsight.report_id == report_id).all()
    insight_ids = [str(l.insight_id) for l in links]

    # Gather source ids from insight citations
    from app.storage.models import InsightCitation

    source_ids_set: set[str] = set()
    for link in links:
        cits = db.query(InsightCitation).filter(InsightCitation.insight_id == link.insight_id).all()
        for c in cits:
            if c.source_id:
                source_ids_set.add(c.source_id)

    # find run_id
    report = db.get(Report, report_id)
    run_id = str(report.run_id) if report and report.run_id else None

    return {
        "report_id": str(report_id),
        "insight_ids": insight_ids,
        "source_ids": list(source_ids_set),
        "run_id": run_id,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _call_llm(prompt: str, provider: str, api_key: str, base_url: str | None, model: str) -> str:
    if provider == "gemini":
        return _call_gemini(prompt, api_key=api_key, model=model)
    return _call_openai(prompt, api_key=api_key, base_url=base_url, model=model)


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
    label = {"research_brief": "Research Brief", "summary": "Summary", "comparison": "Comparison"}.get(
        report_type, "Report"
    )
    return f"{label}: {truncated}"
