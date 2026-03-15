import uuid

from fastapi import APIRouter, Request

from app.contracts.common import success_response

router = APIRouter(prefix="/runs")


@router.post("/{run_id}/replay")
def replay_run(run_id: uuid.UUID, request: Request):
    _ = run_id
    return success_response(
        request,
        {"job_id": "job_replay_placeholder", "status": "queued"},
        status_code=202,
    )
