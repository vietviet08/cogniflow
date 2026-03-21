from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    status: str
    progress: int
    error: dict | None = None
