from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import success_response
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
