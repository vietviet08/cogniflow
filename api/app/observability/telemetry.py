from __future__ import annotations

import math
from collections import Counter, defaultdict, deque
from threading import Lock
from typing import Any

_lock = Lock()
_http_requests: Counter[str] = Counter()
_http_errors: Counter[str] = Counter()
_http_latency_ms: defaultdict[str, list[float]] = defaultdict(list)
_job_runs: Counter[str] = Counter()
_job_latency_ms: defaultdict[str, list[float]] = defaultdict(list)
_trace_events: deque[dict[str, Any]] = deque(maxlen=200)


def emit_event(name: str, payload: dict | None = None) -> None:
    with _lock:
        _trace_events.append({"name": name, "payload": payload or {}})


def record_http_request(*, route: str, method: str, status_code: int, duration_ms: float) -> None:
    key = f"{method} {route}"
    with _lock:
        _http_requests[key] += 1
        _http_latency_ms[key].append(duration_ms)
        if status_code >= 400:
            _http_errors[key] += 1


def record_job_run(*, job_type: str, status: str, duration_ms: float) -> None:
    key = f"{job_type}:{status}"
    with _lock:
        _job_runs[key] += 1
        _job_latency_ms[job_type].append(duration_ms)


def get_metrics_snapshot() -> dict[str, Any]:
    with _lock:
        return {
            "http_requests_total": dict(_http_requests),
            "http_errors_total": dict(_http_errors),
            "http_latency_ms": {
                route: _summarize(samples)
                for route, samples in _http_latency_ms.items()
            },
            "job_runs_total": dict(_job_runs),
            "job_latency_ms": {
                job_type: _summarize(samples)
                for job_type, samples in _job_latency_ms.items()
            },
            "recent_events": list(_trace_events),
        }


def reset_metrics() -> None:
    with _lock:
        _http_requests.clear()
        _http_errors.clear()
        _http_latency_ms.clear()
        _job_runs.clear()
        _job_latency_ms.clear()
        _trace_events.clear()


def _summarize(samples: list[float]) -> dict[str, float]:
    ordered = sorted(samples)
    count = len(ordered)
    if not ordered:
        return {"count": 0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": float(count),
        "p50": round(_percentile(ordered, 0.50), 3),
        "p95": round(_percentile(ordered, 0.95), 3),
        "max": round(ordered[-1], 3),
    }


def _percentile(ordered: list[float], percentile: float) -> float:
    if len(ordered) == 1:
        return ordered[0]
    rank = percentile * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
