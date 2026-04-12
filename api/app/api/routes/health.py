from fastapi import APIRouter, Request

from app.contracts.common import success_response
from app.observability.telemetry import get_metrics_snapshot

router = APIRouter()


@router.get("/health")
def health_check(request: Request):
    return success_response(request, {"status": "ok", "service": "cogniflow-api"})


@router.get("/metrics")
def metrics_snapshot(request: Request):
    return success_response(request, {"metrics": get_metrics_snapshot()})
