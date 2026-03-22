import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.services.insight_service import InsightError, generate_insight
from app.storage.repositories.insight_repository import InsightRepository

router = APIRouter(prefix="/insights")


class GenerateInsightRequest(BaseModel):
    project_id: uuid.UUID
    query: str
    provider: str = "openai"
    evidence_scope: dict | None = None


@router.post("/generate", status_code=202)
def generate_insight_route(
    payload: GenerateInsightRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    max_sources = 20
    if payload.evidence_scope:
        max_sources = payload.evidence_scope.get("max_sources", 20)

    try:
        result = generate_insight(
            db=db,
            project_id=payload.project_id,
            query=payload.query,
            provider=payload.provider,
            max_sources=max_sources,
        )
    except InsightError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    return success_response(request, result, status_code=200)


@router.get("/{insight_id}")
def get_insight(
    insight_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
):
    repo = InsightRepository(db)
    insight = repo.get(insight_id)
    if not insight:
        return error_response(
            request,
            code="INSIGHT_NOT_FOUND",
            message="Insight does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    citations = repo.get_citations(insight_id)
    return success_response(
        request,
        {
            "insight_id": str(insight.id),
            "project_id": str(insight.project_id),
            "query": insight.query,
            "summary": insight.summary,
            "findings": insight.findings or [],
            "provider": insight.provider,
            "model": insight.model_id,
            "run_id": str(insight.run_id) if insight.run_id else None,
            "status": insight.status,
            "created_at": insight.created_at.isoformat(),
            "citations": [
                {
                    "source_id": c.source_id,
                    "document_id": c.document_id,
                    "chunk_id": c.chunk_id,
                    "title": c.title,
                    "url": c.url,
                }
                for c in citations
            ],
        },
    )
