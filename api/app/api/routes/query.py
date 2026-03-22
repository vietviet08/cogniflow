import uuid

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.services.query_service import QueryError, search_knowledge_base
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter(prefix="/query")


class SearchRequest(BaseModel):
    project_id: uuid.UUID
    query: str
    provider: str = "openai"
    filters: dict | None = None
    top_k: int = 8


@router.post("/search")
def search_knowledge(payload: SearchRequest, request: Request, db: Session = Depends(get_db)):
    project = ProjectRepository(db).get(payload.project_id)
    if not project:
        return error_response(
            request,
            code="PROJECT_NOT_FOUND",
            message="Project does not exist",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    try:
        result = search_knowledge_base(
            db=db,
            project_id=payload.project_id,
            query=payload.query,
            provider=payload.provider,
            top_k=payload.top_k,
            filters=payload.filters,
        )
    except QueryError as exc:
        return error_response(
            request,
            code="QUERY_FAILED",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except Exception as exc:
        return error_response(
            request,
            code="QUERY_INTERNAL_ERROR",
            message="Unexpected query failure.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"reason": str(exc)},
        )

    return success_response(
        request,
        result,
    )
