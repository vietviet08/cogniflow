import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import success_response
from app.core.security import require_current_user, require_project_role
from app.storage.models import ProcessingRun, User

router = APIRouter(prefix="/runs")


@router.post("/{run_id}/replay")
def replay_run(
    run_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    run = db.get(ProcessingRun, run_id)
    if run:
        require_project_role(
            db,
            project_id=run.project_id,
            user=current_user,
            minimum_role="editor",
        )
    return success_response(
        request,
        {"job_id": "job_replay_placeholder", "status": "queued"},
        status_code=202,
    )
