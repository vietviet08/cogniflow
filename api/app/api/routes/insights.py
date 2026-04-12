import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.services.citation_service import hydrate_citations
from app.services.insight_service import InsightError, generate_insight
from app.storage.models import User
from app.storage.repositories.insight_repository import InsightRepository
from app.storage.repositories.job_repository import JobRepository
from app.workers.tasks import run_job

router = APIRouter(prefix="/insights")


class GenerateInsightRequest(BaseModel):
    project_id: uuid.UUID
    query: str
    provider: str = "openai"
    evidence_scope: dict | None = None
    mode: str = "sync"


@router.post("/generate", status_code=202)
def generate_insight_route(
    payload: GenerateInsightRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    require_project_role(
        db,
        project_id=payload.project_id,
        user=current_user,
        minimum_role="editor",
    )
    max_sources = 20
    if payload.evidence_scope:
        max_sources = payload.evidence_scope.get("max_sources", 20)

    if payload.mode == "async":
        job = JobRepository(db).create(
            project_id=payload.project_id,
            job_type="insight_generation",
            status="queued",
            queue_name="insight",
            job_payload={
                "project_id": str(payload.project_id),
                "query": payload.query,
                "provider": payload.provider,
                "max_sources": max_sources,
            },
        )
        background_tasks.add_task(run_job, str(job.id))
        return success_response(
            request,
            {
                "job_id": str(job.id),
                "status": job.status,
            },
            status_code=202,
        )

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
    current_user: User = Depends(require_current_user),
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
    require_project_role(
        db,
        project_id=insight.project_id,
        user=current_user,
        minimum_role="viewer",
    )
    citations = hydrate_citations(
        db,
        [
            {
                "citation_id": str(c.id),
                "source_id": c.source_id,
                "source_type": c.source_type,
                "document_id": c.document_id,
                "chunk_id": c.chunk_id,
                "title": c.title,
                "url": c.url,
                "page_number": c.page_number,
            }
            for c in repo.get_citations(insight_id)
        ],
    )
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
            "citations": citations,
        },
    )
