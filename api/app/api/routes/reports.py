import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.services.report_service import (
    ReportError,
    generate_report,
    get_report_lineage,
    serialize_report,
    update_action_item_status,
)
from app.storage.repositories.report_repository import ReportRepository

router = APIRouter(prefix="/reports")


class GenerateReportRequest(BaseModel):
    project_id: uuid.UUID
    type: str = "research_brief"
    query: str
    format: str = "markdown"
    provider: str = "openai"


class UpdateActionItemStatusRequest(BaseModel):
    status: str


@router.post("/generate")
def generate_report_route(
    payload: GenerateReportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        result = generate_report(
            db=db,
            project_id=payload.project_id,
            query=payload.query,
            report_type=payload.type,
            format=payload.format,
            provider=payload.provider,
        )
    except ReportError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
    return success_response(request, result)


@router.get("/{report_id}")
def get_report(report_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return success_response(request, serialize_report(report))


@router.put("/{report_id}/action-items/{item_id}")
def update_report_action_item_status_route(
    report_id: uuid.UUID,
    item_id: str,
    payload: UpdateActionItemStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        result = update_action_item_status(
            db=db,
            report_id=report_id,
            item_id=item_id,
            status=payload.status,
        )
    except ReportError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
    return success_response(request, result)


@router.get("/{report_id}/lineage")
def get_report_lineage_route(report_id: uuid.UUID, request: Request, db: Session = Depends(get_db)):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    lineage = get_report_lineage(db, report_id)
    return success_response(request, lineage)
