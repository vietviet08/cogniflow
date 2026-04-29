from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.services.lineage_service import get_report_lineage
from app.storage.models import ProcessingRun, Report


def evaluate_report_quality(db: Session, report_id: uuid.UUID) -> dict[str, Any] | None:
    report = db.get(Report, report_id)
    if report is None:
        return None

    lineage = get_report_lineage(db, report_id)
    citations = _collect_citations(report, lineage)
    source_ids = {str(citation.get("source_id")) for citation in citations if citation.get("source_id")}
    chunk_ids = {str(citation.get("chunk_id")) for citation in citations if citation.get("chunk_id")}
    item_metrics = _collect_structured_item_metrics(report.structured_payload)
    run = db.get(ProcessingRun, report.run_id) if report.run_id else None
    evidence_snapshot = _get_evidence_snapshot(run)

    citation_count = len(citations)
    missing_quote_count = sum(1 for citation in citations if not citation.get("quote"))
    citation_coverage = _ratio(item_metrics["items_with_citations"], item_metrics["total_items"])
    fidelity_score = 1.0 - _ratio(missing_quote_count, citation_count)
    source_diversity_score = min(len(source_ids) / 3, 1.0) if source_ids else 0.0
    snapshot_score = min(len(evidence_snapshot) / citation_count, 1.0) if citation_count else 0.0

    overall_score = round(
        100
        * (
            0.35 * citation_coverage
            + 0.30 * fidelity_score
            + 0.20 * source_diversity_score
            + 0.15 * snapshot_score
        )
    )
    status = "pass" if overall_score >= 80 else "warning" if overall_score >= 60 else "fail"

    checks = [
        _build_check(
            code="citation_coverage",
            label="Structured items cite evidence",
            score=citation_coverage,
            pass_threshold=0.8,
            warn_threshold=0.5,
            detail=(
                f"{item_metrics['items_with_citations']} of "
                f"{item_metrics['total_items']} structured items include citations."
            ),
        ),
        _build_check(
            code="citation_fidelity",
            label="Citations resolve to quoted evidence",
            score=fidelity_score,
            pass_threshold=0.9,
            warn_threshold=0.7,
            detail=f"{missing_quote_count} of {citation_count} citations are missing quote text.",
        ),
        _build_check(
            code="source_diversity",
            label="Evidence uses multiple sources",
            score=source_diversity_score,
            pass_threshold=0.67,
            warn_threshold=0.34,
            detail=f"{len(source_ids)} unique sources and {len(chunk_ids)} unique chunks are cited.",
        ),
        _build_check(
            code="evidence_snapshot",
            label="Run stored reproducible evidence snapshot",
            score=snapshot_score,
            pass_threshold=0.9,
            warn_threshold=0.5,
            detail=f"{len(evidence_snapshot)} snapshot entries for {citation_count} citations.",
        ),
    ]

    return {
        "report_id": str(report.id),
        "project_id": str(report.project_id),
        "status": status,
        "overall_score": overall_score,
        "metrics": {
            "citation_count": citation_count,
            "source_count": len(source_ids),
            "chunk_count": len(chunk_ids),
            "structured_item_count": item_metrics["total_items"],
            "items_with_citations": item_metrics["items_with_citations"],
            "missing_quote_count": missing_quote_count,
            "evidence_snapshot_count": len(evidence_snapshot),
        },
        "scores": {
            "citation_coverage": round(citation_coverage, 3),
            "citation_fidelity": round(fidelity_score, 3),
            "source_diversity": round(source_diversity_score, 3),
            "evidence_snapshot": round(snapshot_score, 3),
        },
        "checks": checks,
        "recommendations": _build_recommendations(checks),
    }


def _collect_citations(report: Report, lineage: dict[str, Any]) -> list[dict[str, Any]]:
    lineage_citations = lineage.get("citations")
    if isinstance(lineage_citations, list) and lineage_citations:
        return [citation for citation in lineage_citations if isinstance(citation, dict)]

    payload = report.structured_payload if isinstance(report.structured_payload, dict) else {}
    citations: list[dict[str, Any]] = []
    payload_citations = payload.get("citations")
    if isinstance(payload_citations, list):
        citations.extend(citation for citation in payload_citations if isinstance(citation, dict))
    items = payload.get("items")
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            item_citations = item.get("citations")
            if isinstance(item_citations, list):
                citations.extend(citation for citation in item_citations if isinstance(citation, dict))
    return _dedupe_citations(citations)


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for citation in citations:
        key = str(citation.get("chunk_id") or citation.get("citation_id") or citation)
        if key in seen:
            continue
        seen.add(key)
        unique.append(citation)
    return unique


def _collect_structured_item_metrics(payload: dict[str, Any] | None) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {"total_items": 1, "items_with_citations": 0}

    items = payload.get("items")
    if isinstance(items, list) and items:
        total = 0
        grounded = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            total += 1
            citations = item.get("citations")
            if isinstance(citations, list) and citations:
                grounded += 1
        return {"total_items": total, "items_with_citations": grounded}

    citations = payload.get("citations")
    if isinstance(citations, list) and citations:
        return {"total_items": 1, "items_with_citations": 1}
    return {"total_items": 1, "items_with_citations": 0}


def _get_evidence_snapshot(run: ProcessingRun | None) -> list[dict[str, Any]]:
    if run is None or not isinstance(run.run_metadata, dict):
        return []
    snapshot = run.run_metadata.get("evidence_snapshot")
    if not isinstance(snapshot, list):
        return []
    return [entry for entry in snapshot if isinstance(entry, dict)]


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _build_check(
    *,
    code: str,
    label: str,
    score: float,
    pass_threshold: float,
    warn_threshold: float,
    detail: str,
) -> dict[str, Any]:
    status = "pass" if score >= pass_threshold else "warning" if score >= warn_threshold else "fail"
    return {
        "code": code,
        "label": label,
        "status": status,
        "score": round(score, 3),
        "detail": detail,
    }


def _build_recommendations(checks: list[dict[str, Any]]) -> list[str]:
    failed = {check["code"] for check in checks if check["status"] != "pass"}
    recommendations: list[str] = []
    if "citation_coverage" in failed:
        recommendations.append("Regenerate or edit the report so every structured item cites at least one source.")
    if "citation_fidelity" in failed:
        recommendations.append("Reprocess sources or refresh lineage so each citation resolves to a quote.")
    if "source_diversity" in failed:
        recommendations.append("Add or select more independent sources before treating this output as decision-ready.")
    if "evidence_snapshot" in failed:
        recommendations.append("Regenerate the report with evidence snapshots enabled for reproducible review.")
    return recommendations
