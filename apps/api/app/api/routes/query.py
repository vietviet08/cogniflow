import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import success_response

router = APIRouter(prefix="/query")


class SearchRequest(BaseModel):
    project_id: uuid.UUID
    query: str
    filters: dict | None = None
    top_k: int = 8


@router.post("/search")
def search_knowledge(payload: SearchRequest, request: Request, db: Session = Depends(get_db)):
    _ = (payload, db)
    return success_response(
        request,
        {
            "answer": "Search pipeline scaffold is active. Retrieval implementation is pending.",
            "citations": [],
            "run_id": "run_query_placeholder",
        },
    )
