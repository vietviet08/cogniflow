from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.observability.telemetry import get_metrics_snapshot
from app.storage.models import Job

TERMINAL_STATUSES = {"completed", "failed", "dead_letter", "cancelled"}
PROVIDER_FAILURE_MARKERS = ("provider", "openai", "gemini", "upstream", "timeout")


def get_ops_slo_snapshot(db: Session) -> dict[str, Any]:
    settings = get_settings()
    metrics = get_metrics_snapshot()
    status_counts = _job_status_counts(db)
    queue_counts = _queue_counts(db)
    oldest_queued_age_seconds = _oldest_queued_age_seconds(db)
    provider_failures = _provider_failure_count(db)
    failure_rate = _job_failure_rate(status_counts)

    alerts = _build_alerts(
        settings=settings,
        metrics=metrics,
        status_counts=status_counts,
        queued_or_running=sum(
            count for status, count in status_counts.items() if status in {"queued", "running"}
        ),
        oldest_queued_age_seconds=oldest_queued_age_seconds,
        failure_rate=failure_rate,
        provider_failures=provider_failures,
    )

    return {
        "status": _overall_status(alerts),
        "generated_at": datetime.now(UTC).isoformat(),
        "thresholds": {
            "queue_backlog_warning": settings.ops_queue_backlog_warning_threshold,
            "queue_lag_warning_seconds": settings.ops_queue_lag_warning_seconds,
            "job_failure_rate_warning": settings.ops_job_failure_rate_warning,
            "latency_p95_warning_ms": settings.ops_latency_p95_warning_ms,
        },
        "jobs": {
            "status_counts": status_counts,
            "queue_counts": queue_counts,
            "oldest_queued_age_seconds": oldest_queued_age_seconds,
            "failure_rate": failure_rate,
            "provider_failures": provider_failures,
        },
        "latency": {
            "http_latency_ms": metrics.get("http_latency_ms", {}),
            "job_latency_ms": metrics.get("job_latency_ms", {}),
        },
        "alerts": alerts,
    }


def _job_status_counts(db: Session) -> dict[str, int]:
    rows = db.query(Job.status, func.count(Job.id)).group_by(Job.status).all()
    counts = {str(status): int(count) for status, count in rows}
    for status in ["queued", "running", "completed", "failed", "dead_letter", "cancelled"]:
        counts.setdefault(status, 0)
    return counts


def _queue_counts(db: Session) -> list[dict[str, Any]]:
    rows = (
        db.query(Job.queue_name, Job.status, func.count(Job.id))
        .filter(Job.status.in_(["queued", "running"]))
        .group_by(Job.queue_name, Job.status)
        .all()
    )
    by_queue: dict[str, dict[str, Any]] = {}
    for queue_name, status, count in rows:
        queue_key = str(queue_name or "default")
        bucket = by_queue.setdefault(
            queue_key,
            {"queue_name": queue_key, "queued": 0, "running": 0, "backlog": 0},
        )
        bucket[str(status)] = int(count)
        bucket["backlog"] = int(bucket["queued"]) + int(bucket["running"])
    return sorted(by_queue.values(), key=lambda item: item["queue_name"])


def _oldest_queued_age_seconds(db: Session) -> int | None:
    oldest = (
        db.query(Job.created_at)
        .filter(Job.status == "queued")
        .order_by(Job.created_at.asc())
        .limit(1)
        .scalar()
    )
    if oldest is None:
        return None
    created_at = oldest
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    return max(0, int((datetime.now(UTC) - created_at).total_seconds()))


def _provider_failure_count(db: Session) -> int:
    rows = (
        db.query(Job.error_code, Job.error_message)
        .filter(Job.status.in_(["failed", "dead_letter"]))
        .all()
    )
    count = 0
    for code, message in rows:
        haystack = f"{code or ''} {message or ''}".lower()
        if any(marker in haystack for marker in PROVIDER_FAILURE_MARKERS):
            count += 1
    return count


def _job_failure_rate(status_counts: dict[str, int]) -> float:
    terminal_total = sum(status_counts.get(status, 0) for status in TERMINAL_STATUSES)
    if terminal_total == 0:
        return 0.0
    failures = status_counts.get("failed", 0) + status_counts.get("dead_letter", 0)
    return round(failures / terminal_total, 4)


def _build_alerts(
    *,
    settings: Any,
    metrics: dict[str, Any],
    status_counts: dict[str, int],
    queued_or_running: int,
    oldest_queued_age_seconds: int | None,
    failure_rate: float,
    provider_failures: int,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    if queued_or_running > settings.ops_queue_backlog_warning_threshold:
        alerts.append(
            {
                "code": "QUEUE_BACKLOG_HIGH",
                "severity": "warning",
                "message": "Queued/running job backlog is above threshold.",
                "value": queued_or_running,
                "threshold": settings.ops_queue_backlog_warning_threshold,
            }
        )
    if (
        oldest_queued_age_seconds is not None
        and oldest_queued_age_seconds > settings.ops_queue_lag_warning_seconds
    ):
        alerts.append(
            {
                "code": "QUEUE_LAG_HIGH",
                "severity": "warning",
                "message": "Oldest queued job has waited longer than the SLO threshold.",
                "value": oldest_queued_age_seconds,
                "threshold": settings.ops_queue_lag_warning_seconds,
            }
        )
    if failure_rate > settings.ops_job_failure_rate_warning:
        alerts.append(
            {
                "code": "JOB_FAILURE_RATE_HIGH",
                "severity": "critical" if status_counts.get("dead_letter", 0) else "warning",
                "message": "Terminal job failure rate is above threshold.",
                "value": failure_rate,
                "threshold": settings.ops_job_failure_rate_warning,
            }
        )
    if provider_failures > 0:
        alerts.append(
            {
                "code": "PROVIDER_FAILURES_DETECTED",
                "severity": "warning",
                "message": "Recent failed jobs contain provider/upstream failure signals.",
                "value": provider_failures,
                "threshold": 0,
            }
        )

    alerts.extend(_latency_alerts(metrics.get("http_latency_ms", {}), settings, "HTTP"))
    alerts.extend(_latency_alerts(metrics.get("job_latency_ms", {}), settings, "JOB"))
    return alerts


def _latency_alerts(
    latency: dict[str, dict[str, float]],
    settings: Any,
    prefix: str,
) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []
    for name, summary in latency.items():
        p95 = float(summary.get("p95", 0.0))
        if p95 > settings.ops_latency_p95_warning_ms:
            alerts.append(
                {
                    "code": f"{prefix}_P95_LATENCY_HIGH",
                    "severity": "warning",
                    "message": f"{prefix} p95 latency is above threshold.",
                    "target": name,
                    "value": p95,
                    "threshold": settings.ops_latency_p95_warning_ms,
                }
            )
    return alerts


def _overall_status(alerts: list[dict[str, Any]]) -> str:
    if any(alert.get("severity") == "critical" for alert in alerts):
        return "critical"
    if alerts:
        return "warning"
    return "healthy"
