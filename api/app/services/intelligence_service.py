from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.storage.models import (
    Approval,
    GtmOutput,
    IntegrationConnection,
    RadarAction,
    RadarEvent,
    RadarSource,
)


class IntelligenceError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "INTELLIGENCE_ERROR",
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
_ALLOWED_SEVERITIES = set(SEVERITY_RANK.keys())
_ALLOWED_OUTPUT_TYPES = {"battlecard", "talking_points", "response_plan", "outreach_draft"}
_ALLOWED_ACTION_STATUSES = {"open", "in_progress", "done", "escalated"}
_ALLOWED_APPROVAL_STATUSES = {"pending", "approved", "rejected"}


@dataclass
class SourceSnapshot:
    content_hash: str
    excerpt: str


# Public operations


def list_sources(db: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(RadarSource)
        .filter(RadarSource.project_id == project_id)
        .order_by(RadarSource.created_at.desc())
        .all()
    )
    return [_serialize_source(row) for row in rows]


def create_source(
    db: Session,
    *,
    project_id: uuid.UUID,
    name: str,
    source_url: str,
    category: str,
    poll_interval_minutes: int,
    is_active: bool,
) -> dict[str, Any]:
    normalized_name = name.strip()
    normalized_url = source_url.strip()
    if not normalized_name:
        raise IntelligenceError("Source name must not be empty.", code="RADAR_SOURCE_NAME_INVALID")
    if not normalized_url.startswith(("http://", "https://")):
        raise IntelligenceError(
            "Source URL must start with http:// or https://.",
            code="RADAR_SOURCE_URL_INVALID",
        )
    if poll_interval_minutes < 5:
        raise IntelligenceError(
            "Poll interval must be at least 5 minutes.",
            code="RADAR_SOURCE_INTERVAL_INVALID",
        )

    row = RadarSource(
        project_id=project_id,
        name=normalized_name,
        source_url=normalized_url,
        category=(category or "general").strip() or "general",
        poll_interval_minutes=poll_interval_minutes,
        is_active=is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_source(row)


def update_source(
    db: Session,
    *,
    project_id: uuid.UUID,
    source_id: uuid.UUID,
    patch: dict[str, Any],
) -> dict[str, Any]:
    row = _get_source_or_raise(db, project_id, source_id)
    _apply_source_patch(row, patch)

    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_source(row)


def scan_project_sources(
    db: Session,
    *,
    project_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None = None,
    threshold: str = "medium",
) -> dict[str, Any]:
    normalized_threshold = _normalize_severity(threshold)
    query = db.query(RadarSource).filter(
        RadarSource.project_id == project_id,
        RadarSource.is_active.is_(True),
    )
    if source_ids:
        query = query.filter(RadarSource.id.in_(source_ids))

    sources = query.order_by(RadarSource.created_at.asc()).all()

    now = datetime.now(UTC)
    checked = 0
    new_events: list[RadarEvent] = []

    for source in sources:
        checked += 1
        snapshot = _fetch_source_snapshot(source.source_url)

        is_first_snapshot = source.last_content_hash is None
        has_changed = source.last_content_hash is not None and source.last_content_hash != snapshot.content_hash

        if is_first_snapshot:
            event = RadarEvent(
                project_id=project_id,
                source_id=source.id,
                event_type="baseline_captured",
                severity="low",
                title=f"Baseline captured: {source.name}",
                summary="Initial snapshot was captured for continuous monitoring.",
                event_metadata={"url": source.source_url},
                detected_at=now,
            )
            db.add(event)
            new_events.append(event)

        if has_changed:
            event = _build_change_event(source=source, snapshot=snapshot, project_id=project_id, detected_at=now)
            db.add(event)
            new_events.append(event)

        source.last_checked_at = now
        source.last_content_hash = snapshot.content_hash
        source.last_snapshot_excerpt = snapshot.excerpt
        db.add(source)

    db.commit()

    events_payload = [_serialize_event(event) for event in new_events]
    alerts_payload = [
        event
        for event in events_payload
        if SEVERITY_RANK.get(event["severity"], 1) >= SEVERITY_RANK[normalized_threshold]
        and event["event_type"] == "change_detected"
    ]

    return {
        "checked_sources": checked,
        "events_created": len(events_payload),
        "alerts_triggered": len(alerts_payload),
        "threshold": normalized_threshold,
        "items": events_payload,
    }


def list_events(
    db: Session,
    *,
    project_id: uuid.UUID,
    since_hours: int = 24,
    minimum_severity: str = "low",
) -> list[dict[str, Any]]:
    threshold = _normalize_severity(minimum_severity)
    since = datetime.now(UTC) - timedelta(hours=max(1, since_hours))

    rows = (
        db.query(RadarEvent)
        .filter(
            RadarEvent.project_id == project_id,
            RadarEvent.detected_at >= since,
        )
        .order_by(RadarEvent.detected_at.desc())
        .all()
    )

    return [
        _serialize_event(row)
        for row in rows
        if SEVERITY_RANK.get(row.severity, 1) >= SEVERITY_RANK[threshold]
    ]


def acknowledge_event(db: Session, *, project_id: uuid.UUID, event_id: uuid.UUID) -> dict[str, Any]:
    row = _get_event_or_raise(db, project_id, event_id)
    row.acknowledged_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_event(row)


def get_today_digest(db: Session, *, project_id: uuid.UUID) -> dict[str, Any]:
    now = datetime.now(UTC)
    start = datetime(now.year, now.month, now.day, tzinfo=UTC)

    rows = (
        db.query(RadarEvent)
        .filter(
            RadarEvent.project_id == project_id,
            RadarEvent.detected_at >= start,
        )
        .order_by(RadarEvent.detected_at.desc())
        .all()
    )

    severity_counts = Counter(row.severity for row in rows)
    acknowledged = sum(1 for row in rows if row.acknowledged_at is not None)
    open_actions = (
        db.query(RadarAction)
        .filter(
            RadarAction.project_id == project_id,
            RadarAction.status.in_(["open", "in_progress", "escalated"]),
        )
        .count()
    )

    return {
        "date": start.date().isoformat(),
        "summary": {
            "events_total": len(rows),
            "high": severity_counts.get("high", 0),
            "medium": severity_counts.get("medium", 0),
            "low": severity_counts.get("low", 0),
            "acknowledged": acknowledged,
            "open_actions": open_actions,
        },
        "items": [_serialize_event(row) for row in rows[:50]],
    }


def create_action(
    db: Session,
    *,
    project_id: uuid.UUID,
    title: str,
    description: str,
    event_id: uuid.UUID | None,
    owner: str | None,
    due_date_suggested: str | None,
    priority: str,
) -> dict[str, Any]:
    if event_id is not None:
        _get_event_or_raise(db, project_id, event_id)
    normalized_priority = _normalize_severity(priority)

    row = RadarAction(
        project_id=project_id,
        event_id=event_id,
        title=title.strip() or "Untitled action",
        description=description.strip(),
        owner=(owner or "").strip() or None,
        due_date_suggested=(due_date_suggested or "").strip() or None,
        priority=normalized_priority,
        status="open",
        channel_targets={},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_action(row)


def list_actions(db: Session, *, project_id: uuid.UUID, status: str | None = None) -> list[dict[str, Any]]:
    query = db.query(RadarAction).filter(RadarAction.project_id == project_id)
    if status:
        query = query.filter(RadarAction.status == status)
    rows = query.order_by(RadarAction.created_at.desc()).all()
    return [_serialize_action(row) for row in rows]


def update_action(
    db: Session,
    *,
    project_id: uuid.UUID,
    action_id: uuid.UUID,
    patch: dict[str, Any],
) -> dict[str, Any]:
    row = _get_action_or_raise(db, project_id, action_id)
    _apply_action_patch(row, patch)

    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_action(row)


def dispatch_action(
    db: Session,
    *,
    project_id: uuid.UUID,
    action_id: uuid.UUID,
    provider: str,
    destination: str | None,
) -> dict[str, Any]:
    action = _get_action_or_raise(db, project_id, action_id)
    provider_key = provider.strip().lower()

    connection = (
        db.query(IntegrationConnection)
        .filter(
            IntegrationConnection.project_id == project_id,
            IntegrationConnection.provider == provider_key,
            IntegrationConnection.status == "connected",
        )
        .first()
    )
    if connection is None:
        raise IntelligenceError(
            f"Integration '{provider_key}' is not connected for this project.",
            code="INTELLIGENCE_INTEGRATION_NOT_CONNECTED",
            status_code=409,
        )

    targets = dict(action.channel_targets or {})
    targets[provider_key] = {
        "destination": (destination or "").strip() or connection.account_label,
        "dispatched_at": datetime.now(UTC).isoformat(),
    }
    action.channel_targets = targets
    db.add(action)
    db.commit()
    db.refresh(action)

    return {
        "action": _serialize_action(action),
        "dispatch": {
            "provider": provider_key,
            "destination": targets[provider_key]["destination"],
            "status": "queued",
        },
    }


def list_integration_statuses(db: Session, *, project_id: uuid.UUID) -> dict[str, Any]:
    required = ["jira", "slack", "email", "crm"]
    rows = (
        db.query(IntegrationConnection)
        .filter(IntegrationConnection.project_id == project_id)
        .all()
    )
    index = {row.provider.lower(): row for row in rows}

    return {
        "items": [
            {
                "provider": provider,
                "connected": provider in index and index[provider].status == "connected",
                "status": index[provider].status if provider in index else "missing",
                "account_label": index[provider].account_label if provider in index else None,
                "updated_at": (
                    index[provider].updated_at.isoformat() if provider in index and index[provider].updated_at else None
                ),
            }
            for provider in required
        ]
    }


def create_output(
    db: Session,
    *,
    project_id: uuid.UUID,
    output_type: str,
    event_id: uuid.UUID | None,
    context: str | None,
) -> dict[str, Any]:
    normalized_type = output_type.strip().lower()
    if normalized_type not in _ALLOWED_OUTPUT_TYPES:
        raise IntelligenceError(
            "Output type is invalid.",
            code="GTM_OUTPUT_TYPE_INVALID",
            details={"allowed": sorted(_ALLOWED_OUTPUT_TYPES)},
        )

    event: RadarEvent | None = None
    if event_id is not None:
        event = _get_event_or_raise(db, project_id, event_id)

    title, content = _build_output_content(
        output_type=normalized_type,
        event=event,
        context=(context or "").strip(),
    )

    row = GtmOutput(
        project_id=project_id,
        event_id=event_id,
        output_type=normalized_type,
        title=title,
        content=content,
        status="draft",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_output(row)


def list_outputs(db: Session, *, project_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(GtmOutput)
        .filter(GtmOutput.project_id == project_id)
        .order_by(GtmOutput.created_at.desc())
        .all()
    )
    return [_serialize_output(row) for row in rows]


def request_approval(
    db: Session,
    *,
    project_id: uuid.UUID,
    target_type: str,
    target_id: str,
    requested_by_user_id: uuid.UUID | None,
) -> dict[str, Any]:
    row = Approval(
        project_id=project_id,
        target_type=target_type.strip().lower() or "report",
        target_id=target_id.strip(),
        status="pending",
        requested_by_user_id=requested_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_approval(row)


def review_approval(
    db: Session,
    *,
    project_id: uuid.UUID,
    approval_id: uuid.UUID,
    status: str,
    review_notes: str | None,
    reviewed_by_user_id: uuid.UUID,
) -> dict[str, Any]:
    row = _get_approval_or_raise(db, project_id, approval_id)
    next_status = status.strip().lower()
    if next_status not in {"approved", "rejected"}:
        raise IntelligenceError(
            "Review status is invalid.",
            code="APPROVAL_STATUS_INVALID",
            details={"allowed": ["approved", "rejected"]},
        )

    row.status = next_status
    row.review_notes = (review_notes or "").strip() or None
    row.reviewed_by_user_id = reviewed_by_user_id
    row.reviewed_at = datetime.now(UTC)
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize_approval(row)


def list_approvals(db: Session, *, project_id: uuid.UUID, status: str | None = None) -> list[dict[str, Any]]:
    query = db.query(Approval).filter(Approval.project_id == project_id)
    if status:
        next_status = status.strip().lower()
        if next_status not in _ALLOWED_APPROVAL_STATUSES:
            raise IntelligenceError(
                "Approval status is invalid.",
                code="APPROVAL_STATUS_INVALID",
                details={"allowed": sorted(_ALLOWED_APPROVAL_STATUSES)},
            )
        query = query.filter(Approval.status == next_status)

    rows = query.order_by(Approval.created_at.desc()).all()
    return [_serialize_approval(row) for row in rows]


def get_roi_dashboard(db: Session, *, project_id: uuid.UUID, window_days: int = 30) -> dict[str, Any]:
    days = max(7, min(window_days, 90))
    since = datetime.now(UTC) - timedelta(days=days)

    events = (
        db.query(RadarEvent)
        .filter(
            RadarEvent.project_id == project_id,
            RadarEvent.detected_at >= since,
        )
        .all()
    )
    actions = (
        db.query(RadarAction)
        .filter(
            RadarAction.project_id == project_id,
            RadarAction.created_at >= since,
        )
        .all()
    )
    outputs = (
        db.query(GtmOutput)
        .filter(
            GtmOutput.project_id == project_id,
            GtmOutput.created_at >= since,
        )
        .count()
    )

    completed = [row for row in actions if row.status == "done" and row.completed_at is not None]
    completion_hours: list[float] = []
    for row in completed:
        if row.created_at and row.completed_at:
            completion_hours.append((row.completed_at - row.created_at).total_seconds() / 3600)

    total_events = len(events)
    acknowledged = len([row for row in events if row.acknowledged_at is not None])
    high_events = len([row for row in events if row.severity == "high"])
    done_actions = len(completed)

    return {
        "window_days": days,
        "events_total": total_events,
        "high_events": high_events,
        "acknowledged_rate": round(acknowledged / total_events, 4) if total_events else 0.0,
        "actions_total": len(actions),
        "actions_completed": done_actions,
        "action_completion_rate": round(done_actions / len(actions), 4) if actions else 0.0,
        "avg_action_completion_hours": (
            round(sum(completion_hours) / len(completion_hours), 2) if completion_hours else None
        ),
        "outputs_generated": outputs,
    }


# Internal helpers


def _build_change_event(
    *,
    source: RadarSource,
    snapshot: SourceSnapshot,
    project_id: uuid.UUID,
    detected_at: datetime,
) -> RadarEvent:
    old_excerpt = source.last_snapshot_excerpt or ""
    ratio = SequenceMatcher(None, old_excerpt, snapshot.excerpt).ratio() if old_excerpt else 0.0

    severity = "medium"
    if ratio < 0.55:
        severity = "high"
    elif ratio > 0.85:
        severity = "low"

    if re.search(r"\b(price|pricing|plan|compliance|policy|security)\b", snapshot.excerpt, re.IGNORECASE):
        severity = "high"

    title = f"Change detected: {source.name}"
    summary = (
        f"Observed content change on {source.source_url}. Similarity score={ratio:.2f}. "
        f"Category={source.category}."
    )

    return RadarEvent(
        project_id=project_id,
        source_id=source.id,
        event_type="change_detected",
        severity=severity,
        title=title,
        summary=summary,
        event_metadata={
            "similarity": round(ratio, 4),
            "url": source.source_url,
            "category": source.category,
            "current_excerpt": snapshot.excerpt,
            "previous_excerpt": old_excerpt,
        },
        detected_at=detected_at,
    )


def _apply_source_patch(row: RadarSource, patch: dict[str, Any]) -> None:
    handlers = {
        "name": _set_source_name,
        "source_url": _set_source_url,
        "category": _set_source_category,
        "poll_interval_minutes": _set_source_interval,
        "is_active": _set_source_active,
    }
    for key, handler in handlers.items():
        if key in patch and patch[key] is not None:
            handler(row, patch[key])


def _set_source_name(row: RadarSource, value: Any) -> None:
    next_name = str(value).strip()
    if not next_name:
        raise IntelligenceError("Source name must not be empty.", code="RADAR_SOURCE_NAME_INVALID")
    row.name = next_name


def _set_source_url(row: RadarSource, value: Any) -> None:
    next_url = str(value).strip()
    if not next_url.startswith(("http://", "https://")):
        raise IntelligenceError(
            "Source URL must start with http:// or https://.",
            code="RADAR_SOURCE_URL_INVALID",
        )
    row.source_url = next_url


def _set_source_category(row: RadarSource, value: Any) -> None:
    row.category = str(value).strip() or "general"


def _set_source_interval(row: RadarSource, value: Any) -> None:
    interval = int(value)
    if interval < 5:
        raise IntelligenceError(
            "Poll interval must be at least 5 minutes.",
            code="RADAR_SOURCE_INTERVAL_INVALID",
        )
    row.poll_interval_minutes = interval


def _set_source_active(row: RadarSource, value: Any) -> None:
    row.is_active = bool(value)


def _apply_action_patch(row: RadarAction, patch: dict[str, Any]) -> None:
    handlers = {
        "title": _set_action_title,
        "description": _set_action_description,
        "owner": _set_action_owner,
        "due_date_suggested": _set_action_due_date,
        "priority": _set_action_priority,
        "status": _set_action_status,
    }
    for key, handler in handlers.items():
        if key in patch:
            handler(row, patch[key])


def _set_action_title(row: RadarAction, value: Any) -> None:
    if value is not None:
        row.title = str(value).strip() or row.title


def _set_action_description(row: RadarAction, value: Any) -> None:
    if value is not None:
        row.description = str(value).strip() or row.description


def _set_action_owner(row: RadarAction, value: Any) -> None:
    row.owner = str(value).strip() if value else None


def _set_action_due_date(row: RadarAction, value: Any) -> None:
    row.due_date_suggested = str(value).strip() if value else None


def _set_action_priority(row: RadarAction, value: Any) -> None:
    if value is not None:
        row.priority = _normalize_severity(str(value))


def _set_action_status(row: RadarAction, value: Any) -> None:
    if value is None:
        return
    next_status = str(value)
    if next_status not in _ALLOWED_ACTION_STATUSES:
        raise IntelligenceError(
            "Action status is invalid.",
            code="RADAR_ACTION_STATUS_INVALID",
            details={"allowed": sorted(_ALLOWED_ACTION_STATUSES)},
        )
    row.status = next_status
    if next_status == "done":
        row.completed_at = datetime.now(UTC)


def _fetch_source_snapshot(source_url: str) -> SourceSnapshot:
    response = requests.get(source_url, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    text = " ".join(s.strip() for s in soup.stripped_strings)
    condensed = re.sub(r"\s+", " ", text).strip()

    excerpt = condensed[:800]
    content_hash = hashlib.sha256(condensed.encode("utf-8")).hexdigest()
    return SourceSnapshot(content_hash=content_hash, excerpt=excerpt)


def _normalize_severity(value: str) -> str:
    normalized = (value or "medium").strip().lower()
    if normalized not in _ALLOWED_SEVERITIES:
        raise IntelligenceError(
            "Severity is invalid.",
            code="INTELLIGENCE_SEVERITY_INVALID",
            details={"allowed": sorted(_ALLOWED_SEVERITIES)},
        )
    return normalized


def _get_source_or_raise(db: Session, project_id: uuid.UUID, source_id: uuid.UUID) -> RadarSource:
    row = (
        db.query(RadarSource)
        .filter(
            RadarSource.id == source_id,
            RadarSource.project_id == project_id,
        )
        .first()
    )
    if row is None:
        raise IntelligenceError(
            "Radar source does not exist.",
            code="RADAR_SOURCE_NOT_FOUND",
            status_code=404,
        )
    return row


def _get_event_or_raise(db: Session, project_id: uuid.UUID, event_id: uuid.UUID) -> RadarEvent:
    row = (
        db.query(RadarEvent)
        .filter(
            RadarEvent.id == event_id,
            RadarEvent.project_id == project_id,
        )
        .first()
    )
    if row is None:
        raise IntelligenceError(
            "Radar event does not exist.",
            code="RADAR_EVENT_NOT_FOUND",
            status_code=404,
        )
    return row


def _get_action_or_raise(db: Session, project_id: uuid.UUID, action_id: uuid.UUID) -> RadarAction:
    row = (
        db.query(RadarAction)
        .filter(
            RadarAction.id == action_id,
            RadarAction.project_id == project_id,
        )
        .first()
    )
    if row is None:
        raise IntelligenceError(
            "Radar action does not exist.",
            code="RADAR_ACTION_NOT_FOUND",
            status_code=404,
        )
    return row


def _get_approval_or_raise(db: Session, project_id: uuid.UUID, approval_id: uuid.UUID) -> Approval:
    row = (
        db.query(Approval)
        .filter(
            Approval.id == approval_id,
            Approval.project_id == project_id,
        )
        .first()
    )
    if row is None:
        raise IntelligenceError(
            "Approval does not exist.",
            code="APPROVAL_NOT_FOUND",
            status_code=404,
        )
    return row


def _build_output_content(output_type: str, event: RadarEvent | None, context: str) -> tuple[str, str]:
    anchor = context.strip() or (event.summary if event else "No additional context.")
    event_title = event.title if event else "Observed market change"

    if output_type == "battlecard":
        return (
            f"Battlecard: {event_title}",
            "\n".join(
                [
                    "## Situation",
                    anchor,
                    "",
                    "## Risks",
                    "- Competitor narrative shift",
                    "- Potential pricing pressure",
                    "",
                    "## Recommended Response",
                    "- Align messaging with value differentiation",
                    "- Prepare objection handling for sales calls",
                ]
            ),
        )

    if output_type == "talking_points":
        return (
            f"Talking Points: {event_title}",
            "\n".join(
                [
                    "## Core Message",
                    anchor,
                    "",
                    "## Sales Talking Points",
                    "- Why this change matters to customers",
                    "- How our offering responds better",
                    "- What to say in competitive scenarios",
                ]
            ),
        )

    if output_type == "response_plan":
        return (
            f"Response Plan: {event_title}",
            "\n".join(
                [
                    "## Trigger",
                    anchor,
                    "",
                    "## 7-Day Plan",
                    "1. Validate impact with product and sales leads",
                    "2. Update sales enablement assets",
                    "3. Brief customer-facing teams",
                    "4. Track outcome metrics",
                ]
            ),
        )

    return (
        f"Outreach Draft: {event_title}",
        "\n".join(
            [
                "Subject: Quick update relevant to your roadmap",
                "",
                "Hello team,",
                "",
                anchor,
                "",
                "If useful, we can share a short session on concrete implications and options.",
                "",
                "Best regards,",
                "Your team",
            ]
        ),
    )


def _serialize_source(row: RadarSource) -> dict[str, Any]:
    return {
        "source_id": str(row.id),
        "project_id": str(row.project_id),
        "name": row.name,
        "source_url": row.source_url,
        "category": row.category,
        "is_active": row.is_active,
        "poll_interval_minutes": row.poll_interval_minutes,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "last_content_hash": row.last_content_hash,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_event(row: RadarEvent) -> dict[str, Any]:
    return {
        "event_id": str(row.id),
        "project_id": str(row.project_id),
        "source_id": str(row.source_id) if row.source_id else None,
        "event_type": row.event_type,
        "severity": row.severity,
        "title": row.title,
        "summary": row.summary,
        "metadata": row.event_metadata or {},
        "detected_at": row.detected_at.isoformat() if row.detected_at else None,
        "acknowledged_at": row.acknowledged_at.isoformat() if row.acknowledged_at else None,
    }


def _serialize_action(row: RadarAction) -> dict[str, Any]:
    return {
        "action_id": str(row.id),
        "project_id": str(row.project_id),
        "event_id": str(row.event_id) if row.event_id else None,
        "title": row.title,
        "description": row.description,
        "owner": row.owner,
        "due_date_suggested": row.due_date_suggested,
        "priority": row.priority,
        "status": row.status,
        "channel_targets": row.channel_targets or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }


def _serialize_output(row: GtmOutput) -> dict[str, Any]:
    return {
        "output_id": str(row.id),
        "project_id": str(row.project_id),
        "event_id": str(row.event_id) if row.event_id else None,
        "output_type": row.output_type,
        "title": row.title,
        "content": row.content,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_approval(row: Approval) -> dict[str, Any]:
    return {
        "approval_id": str(row.id),
        "project_id": str(row.project_id),
        "target_type": row.target_type,
        "target_id": row.target_id,
        "status": row.status,
        "requested_by_user_id": str(row.requested_by_user_id) if row.requested_by_user_id else None,
        "reviewed_by_user_id": str(row.reviewed_by_user_id) if row.reviewed_by_user_id else None,
        "review_notes": row.review_notes,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "reviewed_at": row.reviewed_at.isoformat() if row.reviewed_at else None,
    }
