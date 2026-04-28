import csv
import io
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.config import get_settings
from app.core.security import require_current_user, require_project_role
from app.services.citation_service import hydrate_citations
from app.services.insight_service import InsightError, generate_insight
from app.services.lineage_service import get_insight_lineage
from app.storage.models import User
from app.storage.repositories.insight_repository import InsightRepository
from app.storage.repositories.job_repository import JobRepository
from app.workers.tasks import run_job

router = APIRouter(prefix="/insights")


DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]


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
    db: DBSession,
    current_user: CurrentUser,
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
                "request_id": request.state.request_id,
            },
        )
        if get_settings().worker_inline_execution:
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


@router.get("/{insight_id}/lineage")
def get_insight_lineage_route(
    insight_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
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
    return success_response(request, get_insight_lineage(db, insight_id))


@router.get("/{insight_id}")
def get_insight(
    insight_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
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


@router.get("/project/{project_id}/export")
def export_project_insights(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    format: str = "csv",
):
    require_project_role(
        db,
        project_id=project_id,
        user=current_user,
        minimum_role="viewer",
    )

    repo = InsightRepository(db)
    rows = repo.list_by_project(project_id)
    normalized_format = format.strip().lower()

    serialized = [
        {
            "insight_id": str(row.id),
            "project_id": str(row.project_id),
            "query": row.query,
            "summary": row.summary,
            "provider": row.provider,
            "model": row.model_id,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]

    if normalized_format == "json":
        return success_response(request, {"items": serialized, "total": len(serialized)})
    if normalized_format != "csv":
        return error_response(
            request,
            code="EXPORT_FORMAT_INVALID",
            message="Export format is invalid.",
            status_code=400,
            details={"allowed": ["csv", "json"]},
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "insight_id",
            "project_id",
            "query",
            "summary",
            "provider",
            "model",
            "status",
            "created_at",
        ],
    )
    writer.writeheader()
    for item in serialized:
        writer.writerow(item)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "content-disposition": f'attachment; filename="insights-{project_id}.csv"'
        },
    )
