"""Mesh generation pipeline for extracting concepts and conflict graphs."""

import hashlib
import re
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
    _build_evidence_blocks,
    _build_evidence_snapshot,
    _call_llm_json,
    _derive_title,
    _load_json_object,
)
from app.storage.models import Chunk, Document, Report, ReportInsight, Source
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
        return _create_fallback_source_mesh_report(
            db,
            project_id=project_id,
            query=query,
            provider=provider,
            parent_run_id=parent_run_id,
            fallback_stage="insight",
            fallback_reason=exc.message,
            fallback_details={"code": exc.code, "status_code": exc.status_code, **exc.details},
        )

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
        return _create_fallback_source_mesh_report(
            db,
            project_id=project_id,
            query=query,
            provider=provider,
            parent_run_id=parent_run_id,
            fallback_stage="provider_settings",
            fallback_reason=str(exc),
            fallback_details={},
        )
    except Exception as exc:
        return _create_fallback_source_mesh_report(
            db,
            project_id=project_id,
            query=query,
            provider=provider,
            parent_run_id=parent_run_id,
            fallback_stage="mesh_llm",
            fallback_reason=str(exc)[:240],
            fallback_details={},
        )

    # 3. Parse JSON, normalize graph shape, and guarantee source coverage.
    payload = _normalize_mesh_payload(_load_json_object(raw_payload), fallback_overview=insight_result.get("summary"))
    _map_edge_citations(payload, evidence_citations)
    payload = _merge_project_source_graph(
        db,
        project_id=project_id,
        payload=payload,
        query=query,
    )

    title = _derive_title(query, "conflict_mesh")
    markdown_content = f"# {title}\\n\\n{payload.get('overview', '')}\\n\\n*View this report in the Mesh Graph interactive view.*"

    prompt_hash = hashlib.sha256(_MESH_PROMPT_TEMPLATE.encode()).hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{generation_config['chat_model']}".encode()).hexdigest()[:16]
    evidence_snapshot = insight_result.get("evidence_snapshot") or _build_evidence_snapshot(
        insight_result.get("citations", [])
    )

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
            "evidence_snapshot": evidence_snapshot,
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
        "evidence_snapshot": evidence_snapshot,
    }


def _create_fallback_source_mesh_report(
    db: Session,
    *,
    project_id: uuid.UUID,
    query: str,
    provider: str,
    parent_run_id: uuid.UUID | None,
    fallback_stage: str,
    fallback_reason: str,
    fallback_details: dict[str, Any],
) -> dict[str, Any]:
    answer_provider, model_id = _resolve_generation_identity(db, project_id=project_id, provider=provider)
    payload = _merge_project_source_graph(
        db,
        project_id=project_id,
        payload={"overview": "", "nodes": [], "edges": []},
        query=query,
    )
    title = _derive_title(query, "conflict_mesh")
    markdown_content = f"# {title}\n\n{payload.get('overview', '')}\n\n*View this report in the Mesh Graph interactive view.*"
    citations = _collect_mesh_payload_citations(payload)
    evidence_snapshot = _build_evidence_snapshot(citations)
    source_ids = [str(source_id) for (source_id,) in db.query(Source.id).filter(Source.project_id == project_id).all()]

    prompt_hash = hashlib.sha256(b"fallback_source_mesh").hexdigest()[:16]
    config_hash = hashlib.sha256(f"{answer_provider}:{model_id or 'source-graph'}".encode()).hexdigest()[:16]
    run = ProcessingRunRepository(db).create(
        project_id=project_id,
        job_id=None,
        run_type="mesh",
        model_id=model_id,
        prompt_hash=prompt_hash,
        config_hash=config_hash,
        retrieval_config=None,
        run_metadata={
            "report_type": "conflict_mesh",
            "format": "json",
            "query": query,
            "provider": answer_provider,
            "structured_output": True,
            "fallback": True,
            "fallback_stage": fallback_stage,
            "fallback_reason": fallback_reason,
            "fallback_details": fallback_details,
            "evidence_snapshot": evidence_snapshot,
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
    db.commit()
    db.refresh(report)

    return {
        "report_id": str(report.id),
        "query": query,
        "title": title,
        "type": "conflict_mesh",
        "format": "json",
        "content": markdown_content,
        "structured_payload": hydrate_report_payload_citations(db, payload),
        "status": "completed",
        "run_id": str(run.id),
        "insight_id": None,
        "source_ids": source_ids,
        "citations": hydrate_citations(db, citations),
        "evidence_snapshot": evidence_snapshot,
        "fallback": True,
    }


def _resolve_generation_identity(
    db: Session,
    *,
    project_id: uuid.UUID,
    provider: str,
) -> tuple[str, str | None]:
    try:
        answer_provider = normalize_provider(provider)
    except ProviderSettingsError:
        return provider, None

    try:
        generation_config = resolve_chat_provider_config(db, project_id, answer_provider)
    except ProviderSettingsError:
        return answer_provider, None
    return answer_provider, generation_config.get("chat_model")


def _collect_mesh_payload_citations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for edge in payload.get("edges", []):
        if not isinstance(edge, dict) or not isinstance(edge.get("citations"), list):
            continue
        for citation in edge["citations"]:
            if not isinstance(citation, dict):
                continue
            key = str(citation.get("citation_id") or citation.get("chunk_id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            citations.append(citation)
    return citations


def _normalize_mesh_payload(
    parsed: dict[str, Any],
    *,
    fallback_overview: str | None = None,
) -> dict[str, Any]:
    nodes = _normalize_mesh_nodes(parsed.get("nodes"))
    edges = _normalize_mesh_edges(parsed.get("edges"), nodes)
    overview = str(parsed.get("overview") or fallback_overview or "").strip()
    if not overview:
        overview = "Knowledge graph generated from project sources."
    return {"overview": overview, "nodes": nodes, "edges": edges}


def _normalize_mesh_nodes(raw_nodes: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list):
        return []

    nodes: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_node in enumerate(raw_nodes[:30], start=1):
        if not isinstance(raw_node, dict):
            continue
        label = _clean_label(raw_node.get("label") or raw_node.get("name"))
        if not label:
            continue
        node_id = _clean_node_id(raw_node.get("id")) or f"node-{index}"
        if node_id in seen_ids:
            node_id = f"{node_id}-{index}"
        seen_ids.add(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": label,
                "type": _clean_label(raw_node.get("type")) or "concept",
            }
        )
    return nodes


def _normalize_mesh_edges(
    raw_edges: Any,
    nodes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(raw_edges, list):
        return []

    node_ids = {node["id"] for node in nodes}
    edges: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_edge in enumerate(raw_edges[:60], start=1):
        if not isinstance(raw_edge, dict):
            continue
        source = _clean_node_id(raw_edge.get("source"))
        target = _clean_node_id(raw_edge.get("target"))
        if not source or not target or source == target:
            continue
        if source not in node_ids or target not in node_ids:
            continue
        edge_id = _clean_node_id(raw_edge.get("id")) or f"edge-{index}"
        if edge_id in seen_ids:
            edge_id = f"{edge_id}-{index}"
        seen_ids.add(edge_id)
        edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": _coerce_edge_type(raw_edge.get("type")),
                "description": _clean_description(raw_edge.get("description")),
                "citation_indexes": raw_edge.get("citation_indexes", []),
            }
        )
    return edges


def _map_edge_citations(
    payload: dict[str, Any],
    evidence_citations: list[dict[str, Any]],
) -> None:
    for edge in payload.get("edges", []):
        raw_indexes = edge.get("citation_indexes", [])
        mapped_citations = []
        for raw_index in raw_indexes:
            if isinstance(raw_index, int) and 0 <= raw_index - 1 < len(evidence_citations):
                mapped_citations.append(evidence_citations[raw_index - 1])

        unique_cits = []
        seen = set()
        for citation in mapped_citations:
            key = str(citation.get("citation_id") or citation.get("chunk_id") or "")
            if key in seen:
                continue
            seen.add(key)
            unique_cits.append(citation)
        edge["citations"] = unique_cits


def _merge_project_source_graph(
    db: Session,
    *,
    project_id: uuid.UUID,
    payload: dict[str, Any],
    query: str,
) -> dict[str, Any]:
    source_nodes, source_edges = _build_project_source_graph(db, project_id=project_id)
    source_graph_has_citations = any(edge.get("citations") for edge in source_edges)
    if not source_nodes:
        if not payload.get("nodes"):
            payload["overview"] = "No indexed source data is available for this project."
        return payload

    nodes = list(payload.get("nodes") or [])
    edges = list(payload.get("edges") or [])
    label_to_node_id = {
        _normalize_label_for_match(node.get("label")): str(node.get("id"))
        for node in nodes
        if node.get("label") and node.get("id")
    }
    node_labels = set(label_to_node_id)
    node_ids = {str(node.get("id")) for node in nodes}
    source_node_id_map: dict[str, str] = {}

    for source_node in source_nodes:
        normalized_label = _normalize_label_for_match(source_node["label"])
        if normalized_label in label_to_node_id:
            source_node_id_map[source_node["id"]] = label_to_node_id[normalized_label]
            continue
        source_node_id_map[source_node["id"]] = source_node["id"]
        if source_node["id"] in node_ids:
            continue
        nodes.append(source_node)
        node_ids.add(source_node["id"])
        node_labels.add(normalized_label)
        label_to_node_id[normalized_label] = source_node["id"]

    edge_ids = {str(edge.get("id")) for edge in edges}
    for source_edge in source_edges:
        merged_edge = {
            **source_edge,
            "source": source_node_id_map.get(source_edge["source"], source_edge["source"]),
            "target": source_node_id_map.get(source_edge["target"], source_edge["target"]),
        }
        if merged_edge["id"] in edge_ids:
            continue
        if merged_edge["source"] not in node_ids or merged_edge["target"] not in node_ids:
            continue
        edges.append(merged_edge)
        edge_ids.add(merged_edge["id"])

    if not payload.get("edges") and source_edges:
        payload["overview"] = _source_graph_overview(source_nodes, query, has_citations=source_graph_has_citations)
    elif not payload.get("nodes"):
        payload["overview"] = _source_graph_overview(source_nodes, query, has_citations=source_graph_has_citations)

    return {
        "overview": payload.get("overview")
        or _source_graph_overview(source_nodes, query, has_citations=source_graph_has_citations),
        "nodes": nodes,
        "edges": edges,
    }


def _build_project_source_graph(
    db: Session,
    *,
    project_id: uuid.UUID,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sources = (
        db.query(Source)
        .filter(Source.project_id == project_id)
        .order_by(Source.created_at.asc(), Source.original_uri.asc())
        .all()
    )
    if not sources:
        return [], []

    first_citation_by_source = _load_first_chunk_citations(db, sources)
    sorted_sources = sorted(sources, key=_source_sort_key)
    nodes = [
        {
            "id": _source_node_id(source),
            "label": _source_label(source),
            "type": "chapter" if _looks_like_chapter(source) else "source",
        }
        for source in sorted_sources
    ]
    edges: list[dict[str, Any]] = []
    for index, (left, right) in enumerate(zip(sorted_sources, sorted_sources[1:], strict=False), start=1):
        citations = [
            citation
            for citation in (
                first_citation_by_source.get(left.id),
                first_citation_by_source.get(right.id),
            )
            if citation
        ]
        description = (
            f"{_source_label(left)} and {_source_label(right)} are adjacent project sources."
        )
        if not citations:
            description += " Process these sources to add content-backed relationship evidence."
        edges.append(
            {
                "id": f"source-edge-{index}",
                "source": _source_node_id(left),
                "target": _source_node_id(right),
                "type": "relates_to",
                "description": description,
                "citation_indexes": [],
                "citations": citations,
            }
        )
    return nodes, edges


def _load_first_chunk_citations(
    db: Session,
    sources: list[Source],
) -> dict[uuid.UUID, dict[str, Any]]:
    source_ids = [source.id for source in sources]
    if not source_ids:
        return {}

    rows = (
        db.query(Source, Document, Chunk)
        .join(Document, Document.source_id == Source.id)
        .join(Chunk, Chunk.document_id == Document.id)
        .filter(Source.id.in_(source_ids))
        .order_by(Source.created_at.asc(), Document.created_at.asc(), Chunk.chunk_index.asc())
        .all()
    )

    citations: dict[uuid.UUID, dict[str, Any]] = {}
    for source, document, chunk in rows:
        if source.id in citations:
            continue
        metadata = chunk.chunk_metadata if isinstance(chunk.chunk_metadata, dict) else {}
        citations[source.id] = {
            "citation_id": str(chunk.id),
            "source_id": str(source.id),
            "source_type": source.type,
            "document_id": str(document.id),
            "chunk_id": str(chunk.id),
            "title": document.title or source.original_uri or "Source",
            "url": metadata.get("url") or source.original_uri or "",
            "page_number": metadata.get("page_number"),
            "quote": chunk.content,
        }
    return citations


def _source_graph_overview(source_nodes: list[dict[str, Any]], query: str, *, has_citations: bool = False) -> str:
    detail = (
        "Edges include citations from indexed chunks."
        if has_citations
        else "Run source processing to enrich edges with content-backed citations."
    )
    return f"Generated a source-level graph with {len(source_nodes)} nodes for '{query}'. {detail}"


def _source_sort_key(source: Source) -> tuple[int, str]:
    label = _source_label(source)
    match = re.search(r"(\d+)", label)
    number = int(match.group(1)) if match else 10_000
    return (number, label.casefold())


def _source_node_id(source: Source) -> str:
    return f"source-{source.id}"


def _source_label(source: Source) -> str:
    raw = (source.source_metadata or {}).get("title") if isinstance(source.source_metadata, dict) else None
    label = str(raw or source.original_uri or source.id).strip()
    return re.sub(r"\.[A-Za-z0-9]{1,8}$", "", label).strip() or str(source.id)


def _looks_like_chapter(source: Source) -> bool:
    return bool(re.search(r"\b(chuong|chương|chapter)\b|\d+", _source_label(source), re.IGNORECASE))


def _clean_label(value: Any) -> str:
    return str(value or "").strip()[:80]


def _clean_description(value: Any) -> str:
    return str(value or "Related based on indexed project evidence.").strip()[:500]


def _clean_node_id(value: Any) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip())
    return cleaned.strip("-")[:80]


def _coerce_edge_type(value: Any) -> str:
    edge_type = str(value or "").strip()
    if edge_type in {"agrees_with", "contradicts", "relates_to"}:
        return edge_type
    return "relates_to"


def _normalize_label_for_match(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())
