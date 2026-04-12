from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    status: str
    progress: int
    attempt_count: int
    max_retries: int
    queue_name: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    error: dict | None = None
    result: dict | None = None
