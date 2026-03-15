import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import success_response

router = APIRouter(prefix="/insights")


class GenerateInsightRequest(BaseModel):
    project_id: uuid.UUID
    query: str
    evidence_scope: dict | None = None


@router.post("/generate")
def generate_insight(
    payload: GenerateInsightRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _ = (payload, db)
    return success_response(
        request,
        {"job_id": "job_insight_placeholder", "status": "queued"},
        status_code=202,
    )
