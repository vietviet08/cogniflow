import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.storage.repositories.report_repository import ReportRepository

router = APIRouter(prefix="/reports")


class GenerateReportRequest(BaseModel):
    project_id: uuid.UUID
    type: str
    query: str
    format: str = "markdown"


@router.post("/generate")
def generate_report(payload: GenerateReportRequest, request: Request):
    _ = payload
    return success_response(
        request,
        {
            "job_id": "job_report_placeholder",
            "status": "queued",
        },
        status_code=202,
    )


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

    return success_response(
        request,
        {
            "id": str(report.id),
            "project_id": str(report.project_id),
            "title": report.title,
            "type": report.report_type,
            "format": report.format,
            "content": report.content,
            "status": report.status,
        },
    )


@router.get("/{report_id}/lineage")
def get_report_lineage(report_id: uuid.UUID, request: Request):
    return success_response(
        request,
        {
            "report_id": str(report_id),
            "insight_ids": [],
            "source_ids": [],
            "run_id": "run_report_placeholder",
        },
    )
