from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user
from app.observability.telemetry import get_metrics_snapshot
from app.services.ops_service import get_ops_slo_snapshot
from app.storage.models import User

router = APIRouter()


@router.get("/health")
def health_check(request: Request):
    return success_response(request, {"status": "ok", "service": "cogniflow-api"})


@router.get("/metrics")
def metrics_snapshot(request: Request):
    return success_response(request, {"metrics": get_metrics_snapshot()})


@router.get("/ops/slo")
def ops_slo_snapshot(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    if current_user.role != "admin":
        return error_response(
            request,
            code="OPS_FORBIDDEN",
            message="Operational SLO data requires admin access.",
            status_code=status.HTTP_403_FORBIDDEN,
        )
    return success_response(request, get_ops_slo_snapshot(db))
