from fastapi import APIRouter, Request

from app.contracts.common import success_response

router = APIRouter()


@router.get("/health")
def health_check(request: Request):
    return success_response(request, {"status": "ok", "service": "notemesh-api"})
