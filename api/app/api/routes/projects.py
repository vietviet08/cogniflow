import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.services.audit_service import log_audit_event
from app.storage.models import Chunk, Document, Source, User
from app.storage.repositories.processing_run_repository import ProcessingRunRepository
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/projects")


DBSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(require_current_user)]
PROJECT_NOT_FOUND_MESSAGE = "Project does not exist"


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None
    organization_id: str | None = None


@router.post("")
def create_project(
    payload: CreateProjectRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    if payload.organization_id:
        from app.core.security import require_organization_role
        require_organization_role(
            db, 
            organization_id=uuid.UUID(payload.organization_id), 
            user=current_user, 
            minimum_role="admin"
        )
        
    repo = ProjectRepository(db)
    org_id_uuid = uuid.UUID(payload.organization_id) if payload.organization_id else None
    
    project = repo.create(
        name=payload.name,
        description=payload.description,
        owner_user_id=current_user.id,
        organization_id=org_id_uuid,
    )
    log_audit_event(
        db,
        action="project.create",
        target_type="project",
        target_id=str(project.id),
        user_id=current_user.id,
        project_id=project.id,
        organization_id=org_id_uuid,
        payload={"name": payload.name},
    )
    db.commit()
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
def list_projects(
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    organization_id: str | None = None,
):
    repo = ProjectRepository(db)
    org_uuid = uuid.UUID(organization_id) if organization_id else None
    projects = repo.list_with_stats(current_user.id, org_uuid)
    return success_response(request, {"items": projects, "total": len(projects)})


class UpdateProjectRequest(BaseModel):
    name: str
    description: str | None = None


@router.put("/{project_id}")
def update_project(
    project_id: uuid.UUID,
    payload: UpdateProjectRequest,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    repo = ProjectRepository(db)
    project = repo.update(project_id, name=payload.name, description=payload.description)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            PROJECT_NOT_FOUND_MESSAGE,
            status_code=404,
        )
    log_audit_event(
        db,
        action="project.update",
        target_type="project",
        target_id=str(project.id),
        user_id=current_user.id,
        project_id=project.id,
        organization_id=project.organization_id,
        payload={"name": payload.name, "description": payload.description},
    )
    db.commit()
    return success_response(
        request,
        {
            "id": str(project.id),
            "name": project.name,
            "description": project.description,
        },
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="owner")
    repo = ProjectRepository(db)
    success = repo.delete(project_id)
    if not success:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist or deletion failed",
            status_code=404,
        )
    log_audit_event(
        db,
        action="project.delete",
        target_type="project",
        target_id=str(project_id),
        user_id=current_user.id,
        project_id=None,
    )
    db.commit()
    return success_response(request, {"success": True})


@router.get("/{project_id}/documents")
def list_project_documents(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            PROJECT_NOT_FOUND_MESSAGE,
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
    db: DBSession,
    current_user: CurrentUser,
    source_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    limit: int = 50,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            PROJECT_NOT_FOUND_MESSAGE,
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
def list_processing_runs(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            PROJECT_NOT_FOUND_MESSAGE,
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
def list_project_insights(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            PROJECT_NOT_FOUND_MESSAGE,
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
def list_project_reports(
    project_id: uuid.UUID,
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
):
    from app.storage.models import Report

    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            PROJECT_NOT_FOUND_MESSAGE,
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
                    "query": r.query,
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
