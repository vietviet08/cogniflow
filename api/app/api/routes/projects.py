import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.storage.models import Chunk, Document, Source
from app.storage.repositories.processing_run_repository import ProcessingRunRepository
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/projects")


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None


@router.post("")
def create_project(payload: CreateProjectRequest, request: Request, db: Session = Depends(get_db)):
    repo = ProjectRepository(db)
    project = repo.create(name=payload.name, description=payload.description)
    return success_response(
        request,
        {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
            "created_at": project.created_at.isoformat() if project.created_at else None,
        },
        status_code=201,
    )


@router.get("")
def list_projects(request: Request, db: Session = Depends(get_db)):
    repo = ProjectRepository(db)
    projects = repo.list_with_stats()
    return success_response(request, {"items": projects, "total": len(projects)})


class UpdateProjectRequest(BaseModel):
    name: str
    description: str | None = None


@router.put("/{project_id}")
def update_project(project_id: uuid.UUID, payload: UpdateProjectRequest, request: Request, db: Session = Depends(get_db)):
    repo = ProjectRepository(db)
    project = repo.update(project_id, name=payload.name, description=payload.description)
    if not project:
        return error_response(request, "PROJECT_NOT_FOUND", "Project does not exist", status_code=404)
    return success_response(request, {"id": str(project.id), "name": project.name, "description": project.description})


@router.delete("/{project_id}")
def delete_project(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    repo = ProjectRepository(db)
    success = repo.delete(project_id)
    if not success:
        return error_response(request, "PROJECT_NOT_FOUND", "Project does not exist or deletion failed", status_code=404)
    return success_response(request, {"success": True})


@router.get("/{project_id}/documents")
def list_project_documents(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist",
            status_code=404,
        )

    rows = (
        db.query(Document, Source, func.count(Chunk.id).label("chunk_count"))
        .join(Source, Document.source_id == Source.id)
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .filter(Source.project_id == project_id)
        .group_by(Document.id, Source.id)
        .order_by(Document.created_at.desc())
        .all()
    )

    return success_response(
        request,
        {
            "items": [
                {
                    "document_id": str(document.id),
                    "source_id": str(source.id),
                    "title": document.title,
                    "source_type": source.type,
                    "original_uri": source.original_uri,
                    "token_count": document.token_count,
                    "chunk_count": chunk_count,
                    "created_at": document.created_at.isoformat() if document.created_at else None,
                }
                for document, source, chunk_count in rows
            ],
            "total": len(rows),
        },
    )


@router.get("/{project_id}/chunks")
def list_project_chunks(
    project_id: uuid.UUID,
    request: Request,
    source_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist",
            status_code=404,
        )

    query = (
        db.query(Chunk, Document, Source)
        .join(Document, Chunk.document_id == Document.id)
        .join(Source, Document.source_id == Source.id)
        .filter(Source.project_id == project_id)
    )
    if source_id:
        query = query.filter(Source.id == source_id)
    if document_id:
        query = query.filter(Document.id == document_id)

    rows = (
        query.order_by(Document.created_at.desc(), Chunk.chunk_index.asc())
        .limit(max(1, min(limit, 200)))
        .all()
    )

    return success_response(
        request,
        {
            "items": [
                {
                    "chunk_id": str(chunk.id),
                    "document_id": str(document.id),
                    "source_id": str(source.id),
                    "chunk_index": chunk.chunk_index,
                    "embedding_model": chunk.embedding_model,
                    "metadata": chunk.chunk_metadata or {},
                    "preview": chunk.content[:240],
                    "title": document.title,
                }
                for chunk, document, source in rows
            ],
            "total": len(rows),
            "limit": max(1, min(limit, 200)),
        },
    )


@router.get("/{project_id}/processing-runs")
def list_processing_runs(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist",
            status_code=404,
        )

    runs = ProcessingRunRepository(db).list_by_project(project_id)
    return success_response(
        request,
        {
            "items": [
                {
                    "run_id": str(run.id),
                    "job_id": str(run.job_id) if run.job_id else None,
                    "run_type": run.run_type,
                    "model_id": run.model_id,
                    "config_hash": run.config_hash,
                    "run_metadata": run.run_metadata or {},
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                }
                for run in runs
            ],
            "total": len(runs),
        },
    )


@router.get("/{project_id}/insights")
def list_project_insights(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist",
            status_code=404,
        )

    from app.storage.repositories.insight_repository import InsightRepository

    insights = InsightRepository(db).list_by_project(project_id)
    return success_response(
        request,
        {
            "items": [
                {
                    "insight_id": str(i.id),
                    "query": i.query,
                    "summary": i.summary,
                    "provider": i.provider,
                    "model": i.model_id,
                    "status": i.status,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in insights
            ],
            "total": len(insights),
        },
    )


@router.get("/{project_id}/reports")
def list_project_reports(project_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    from app.storage.models import Report

    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist",
            status_code=404,
        )

    reports = (
        db.query(Report)
        .filter(Report.project_id == project_id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return success_response(
        request,
        {
            "items": [
                {
                    "report_id": str(r.id),
                    "title": r.title,
                    "type": r.report_type,
                    "format": r.format,
                    "structured_payload": r.structured_payload,
                    "status": r.status,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in reports
            ],
            "total": len(reports),
        },
    )
