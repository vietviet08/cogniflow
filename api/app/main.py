import logging
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.contracts.common import APIError, error_response
from app.core.config import get_settings
from app.core.logging import bind_request_id, clear_request_id, configure_logging
from app.observability.telemetry import emit_event, record_http_request


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()
    http_logger = logging.getLogger("app.http")
    app = FastAPI(title="Cogniflow API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def telemetry_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid4())
        request.state.request_id = request_id
        token = bind_request_id(request_id)
        started_at = time.perf_counter()
        route_path = request.url.path

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            record_http_request(
                route=route_path,
                method=request.method,
                status_code=500,
                duration_ms=duration_ms,
            )
            emit_event(
                "http_request_failed",
                {
                    "route": route_path,
                    "method": request.method,
                    "duration_ms": round(duration_ms, 3),
                },
            )
            http_logger.exception(
                "request_failed",
                extra={"route": route_path, "method": request.method},
            )
            clear_request_id(token)
            raise

        resolved_route = request.scope.get("route")
        if resolved_route is not None:
            route_path = getattr(resolved_route, "path", route_path)

        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["x-request-id"] = request_id
        record_http_request(
            route=route_path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        emit_event(
            "http_request_completed",
            {
                "route": route_path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 3),
            },
        )
        http_logger.info(
            "request_completed",
            extra={
                "route": route_path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": round(duration_ms, 3),
            },
        )
        clear_request_id(token)
        return response

    app.include_router(api_router)

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return error_response(
            request,
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            details=exc.details,
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP request failed."
        return error_response(
            request,
            code="HTTP_ERROR",
            message=detail,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_exception(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return error_response(
            request,
            code="VALIDATION_ERROR",
            message="Request validation failed.",
            status_code=422,
            details={"errors": exc.errors()},
        )
    return app


app = create_app()
