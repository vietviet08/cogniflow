import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import APIError, error_response, success_response
from app.core.config import get_settings
from app.core.security import require_current_user, require_project_role
from app.services.evaluation_service import evaluate_report_quality
from app.services.report_service import (
    ReportError,
    create_quiz_attempt,
    generate_podcast_audio,
    generate_report,
    get_report_lineage,
    list_quiz_attempts,
    podcast_audio_file_is_playable,
    serialize_report,
    update_action_item_status,
)
from app.storage.models import User
from app.storage.repositories.auth_token_repository import AuthTokenRepository
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.report_repository import ReportRepository
from app.storage.repositories.user_repository import UserRepository
from app.workers.tasks import run_job

router = APIRouter(prefix="/reports")


class GenerateReportRequest(BaseModel):
    project_id: uuid.UUID
    type: str = "research_brief"
    query: str
    format: str = "markdown"
    provider: str = "openai"
    mode: str = "sync"


class UpdateActionItemStatusRequest(BaseModel):
    status: str


class CreateQuizAttemptRequest(BaseModel):
    answers: dict[str, str]


@router.post("/generate")
def generate_report_route(
    payload: GenerateReportRequest,
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
    if payload.mode == "async":
        job = JobRepository(db).create(
            project_id=payload.project_id,
            job_type="report_generation",
            status="queued",
            queue_name="report",
            job_payload={
                "project_id": str(payload.project_id),
                "query": payload.query,
                "type": payload.type,
                "format": payload.format,
                "provider": payload.provider,
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
def get_report(
    report_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=report.project_id, user=current_user, minimum_role="viewer")
    return success_response(request, serialize_report(report, db))


@router.get("/{report_id}/quiz-attempts")
def list_report_quiz_attempts_route(
    report_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=report.project_id, user=current_user, minimum_role="viewer")
    attempts = list_quiz_attempts(db, report_id=report_id, user_id=current_user.id)
    return success_response(
        request,
        {
            "items": attempts,
            "total": len(attempts),
        },
    )


@router.post("/{report_id}/quiz-attempts")
def create_report_quiz_attempt_route(
    report_id: uuid.UUID,
    payload: CreateQuizAttemptRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=report.project_id, user=current_user, minimum_role="viewer")
    try:
        result = create_quiz_attempt(
            db,
            report_id=report_id,
            user_id=current_user.id,
            answers=payload.answers,
        )
    except ReportError as exc:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )
    return success_response(request, result, status_code=status.HTTP_201_CREATED)


@router.put("/{report_id}/action-items/{item_id}")
def update_report_action_item_status_route(
    report_id: uuid.UUID,
    item_id: str,
    payload: UpdateActionItemStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=report.project_id, user=current_user, minimum_role="editor")
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
def get_report_lineage_route(
    report_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=report.project_id, user=current_user, minimum_role="viewer")
    lineage = get_report_lineage(db, report_id)
    return success_response(request, lineage)


@router.get("/{report_id}/quality")
def get_report_quality_route(
    report_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    report = ReportRepository(db).get(report_id)
    if not report:
        return error_response(
            request,
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=report.project_id, user=current_user, minimum_role="viewer")
    return success_response(request, evaluate_report_quality(db, report_id))

def require_current_user_podcast(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> User:
    raw_token = token
    if not raw_token:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise APIError(
                code="AUTH_REQUIRED",
                message="Missing bearer token.",
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        raw_token = authorization.split(" ", maxsplit=1)[1]

    token_obj = AuthTokenRepository(db).resolve(raw_token)
    if token_obj is None:
        raise APIError(
            code="AUTH_INVALID_TOKEN",
            message="Bearer token is invalid or revoked.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    user = UserRepository(db).get(token_obj.user_id)
    if user is None or not user.is_active:
        raise APIError(
            code="AUTH_USER_INACTIVE",
            message="Authenticated user is unavailable.",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    return user


@router.get("/{report_id}/podcast-audio")
def get_report_podcast_audio_route(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user_podcast),
):
    report = ReportRepository(db).get(report_id)
    if not report:
        raise APIError(
            code="REPORT_NOT_FOUND",
            message="Report does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    require_project_role(db, project_id=report.project_id, user=current_user, minimum_role="viewer")

    if report.report_type != "podcast":
        raise APIError(
            code="REPORT_TYPE_INVALID",
            message="Audio generation is only supported for podcast reports.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Resolve audio path
    podcast_dir = os.path.join(get_settings().upload_dir, "podcasts")
    audio_path = os.path.join(podcast_dir, f"{report.id}.mp3")

    # If audio does not exist yet or a previous attempt left a corrupt file, generate it on-the-fly.
    if not podcast_audio_file_is_playable(audio_path):
        try:
            generate_podcast_audio(report.id, report.structured_payload or {})
        except Exception as exc:
            raise APIError(
                code="PODCAST_AUDIO_GENERATION_FAILED",
                message="Failed to generate podcast audio with edge-tts.",
                status_code=status.HTTP_502_BAD_GATEWAY,
                details={"reason": exc.__class__.__name__},
            ) from exc

    if not podcast_audio_file_is_playable(audio_path):
        raise APIError(
            code="PODCAST_AUDIO_MISSING",
            message="Podcast audio file could not be found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"podcast-{report_id}.mp3",
        content_disposition_type="inline",
        headers={
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        },
    )
