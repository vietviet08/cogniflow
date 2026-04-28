"""Mesh generation pipeline for extracting concepts and conflict graphs."""

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.services.citation_service import hydrate_citations, hydrate_report_payload_citations
from app.services.insight_service import InsightError, generate_insight
from app.services.provider_settings_service import (
    ProviderSettingsError,
    normalize_provider,
    resolve_chat_provider_config,
)
from app.services.report_service import (
    ReportError,
    _build_evidence_blocks,
    _call_llm_json,
    _derive_title,
)
from app.storage.models import Report, ReportInsight
from app.storage.repositories.processing_run_repository import ProcessingRunRepository

_MESH_PROMPT_TEMPLATE = """\
You are an expert knowledge engineer. Your task is to extract a Knowledge Graph highlighting conflicts and relationships from the provided evidence.

Return a JSON object with EXACTLY this shape:
{{
  "overview": "<short summary of the conflicts or main themes>",
  "nodes": [
    {{
      "id": "<unique_string_id>",
      "label": "<short concept name>",
      "type": "concept"
    }}
  ],
  "edges": [
    {{
      "id": "<unique_string_id>",
      "source": "<node_id>",
      "target": "<node_id>",
      "type": "agrees_with|contradicts|relates_to",
      "description": "<why they relate or conflict, with concrete metrics from texts if available>",
      "citation_indexes": [1, 2]
    }}
  ]
}}

Rules:
- Extract 5 to 15 key nodes maximum. Keep labels very short (1-3 words).
- Extract edges between nodes. Pay SPECIAL attention to generating a "contradicts" edge if two sources disagree on a concept or metric.
- Every edge must have a description and citation_indexes to trace back exactly where the information is.
- Use ONLY the evidence provided below. Do not hallucinate external facts.

User Request: {query}

Evidence:
{evidence}
"""

def generate_conflict_mesh(
    db: Session,
    project_id: uuid.UUID,
    query: str,
    provider: str,
    parent_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    # 1. Insight Generation (RAG)
    try:
        insight_result = generate_insight(
            db=db,
            project_id=project_id,
            query=query,
            provider=provider,
            max_sources=20,
        )
    except InsightError as exc:
        raise ReportError(
            exc.message,
            code="REPORT_INSIGHT_ERROR",
            status_code=exc.status_code,
            details=exc.details,
        ) from exc

    # 2. Build Context
    evidence_blocks, evidence_citations = _build_evidence_blocks(db, insight_result.get("citations", []))
    prompt = _MESH_PROMPT_TEMPLATE.format(query=query, evidence=evidence_blocks)

    try:
        answer_provider = normalize_provider(provider)
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)

        raw_payload = _call_llm_json(
            prompt=prompt,
            provider=answer_provider,
            api_key=generation_config["api_key"],
            base_url=generation_config.get("base_url"),
            model=generation_config["chat_model"],
        )
    except ProviderSettingsError as exc:
        raise ReportError(str(exc)) from exc
    except Exception as exc:
        raise ReportError(
            "LLM call failed during mesh generation.",
            code="REPORT_UPSTREAM_ERROR",
            status_code=502,
            details={"reason": str(exc)[:240]},
        ) from exc

    # 3. Parse JSON & Mapped Citations
    try:
        payload = json.loads(raw_payload)
    except Exception:
        payload = {"overview": "Failed to parse mesh output.", "nodes": [], "edges": []}

    for edge in payload.get("edges", []):
        raw_indexes = edge.get("citation_indexes", [])
        mapped_citations = []
        for raw_index in raw_indexes:
            if isinstance(raw_index, int) and 0 <= raw_index - 1 < len(evidence_citations):
                mapped_citations.append(evidence_citations[raw_index - 1])
        
        unique_cits = []
        seen = set()
        for c in mapped_citations:
            k = str(c.get("citation_id") or c.get("chunk_id") or "")
            if k not in seen:
                seen.add(k)
                unique_cits.append(c)
        edge["citations"] = unique_cits

    title = _derive_title(query, "conflict_mesh")
    markdown_content = f"# {title}\\n\\n{payload.get('overview', '')}\\n\\n*View this report in the Mesh Graph interactive view.*"

    prompt_hash = hashlib.sha256(_MESH_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]

    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="mesh",
        model_id=generation_config["chat_model"],
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": "conflict_mesh",
            "format": "json",
            "query": query,
            "provider": answer_provider,
            "insight_id": insight_result["insight_id"],
            "structured_output": True,
        },
        parent_run_id=parent_run_id,
    )

    report = Report(
        project_id=project_id,
        query=query,
        title=title,
        report_type="conflict_mesh",
        format="json",
        content=markdown_content,
        structured_payload=payload,
        status="completed",
        run_id=run.id,
    )
    db.add(report)
    db.flush()

    link = ReportInsight(
        report_id=report.id,
        insight_id=uuid.UUID(insight_result["insight_id"]),
    )
    db.add(link)
    db.commit()
    db.refresh(report)

    source_ids = list({c["source_id"] for c in insight_result["citations"] if c.get("source_id")})
    structured_payload = hydrate_report_payload_citations(db, payload)
    citations = hydrate_citations(db, insight_result["citations"])

    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": "conflict_mesh",
        "format": "json",
        "content": markdown_content,
        "structured_payload": structured_payload,
        "status": "completed",
        "run_id": str(run.id),
        "insight_id": insight_result["insight_id"],
        "source_ids": source_ids,
        "citations": citations,
    }
