from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class Meta(BaseModel):
    request_id: str
    timestamp: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class SuccessEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow")

    data: Any
    meta: Meta


class ErrorEnvelope(BaseModel):
    error: ErrorBody
    meta: Meta


class APIError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _build_meta(request: Request) -> Meta:
    request_id = request.headers.get("x-request-id", str(uuid4()))
    return Meta(
        request_id=request_id,
        timestamp=datetime.now(UTC).isoformat(),
    )


def success_response(request: Request, data: Any, status_code: int = 200) -> JSONResponse:
    payload = SuccessEnvelope(data=data, meta=_build_meta(request))
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def error_response(
    request: Request,
    code: str,
    message: str,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorBody(code=code, message=message, details=details or {}),
        meta=_build_meta(request),
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))
