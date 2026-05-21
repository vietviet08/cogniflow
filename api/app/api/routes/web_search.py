"""
Web Search routes — search internet sources and preview URLs.

Endpoints:
    GET /web-search?q=<query>&limit=10
    GET /web-search/preview?url=<url>

These routes are read-only (no DB writes) and require only viewer authentication.
Adding discovered sources to a project is done via the existing POST /sources/urls endpoint.
"""
import uuid

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user
from app.services.web_search_service import (
    WebPreviewError,
    WebSearchError,
    fetch_web_preview,
    search_web,
)
from app.storage.models import User
from sqlalchemy.orm import Session

router = APIRouter(prefix="/web-search")


@router.get("")
def search_web_sources(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    limit: int = Query(default=10, ge=1, le=20, description="Max results to return"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    """
    Search the web for sources related to the given query.
    Returns a list of results with title, URL, snippet and domain.
    """
    try:
        results = search_web(query=q, limit=limit)
    except WebSearchError as exc:
        return error_response(
            request,
            code="WEB_SEARCH_FAILED",
            message=str(exc),
            status_code=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as exc:
        return error_response(
            request,
            code="WEB_SEARCH_ERROR",
            message="An unexpected error occurred during web search.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"reason": str(exc)[:200]},
        )

    return success_response(
        request,
        {
            "query": q,
            "items": [r.to_dict() for r in results],
            "total": len(results),
        },
    )


@router.get("/preview")
def preview_web_url(
    url: str = Query(..., min_length=4, max_length=2000, description="URL to preview"),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    """
    Fetch and scrape a URL to generate a rich preview card.
    Returns title, description, content preview, author, tags, etc.
    """
    if not url.startswith(("http://", "https://")):
        return error_response(
            request,
            code="INVALID_URL",
            message="URL must start with http:// or https://",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        preview = fetch_web_preview(url)
    except WebPreviewError as exc:
        return error_response(
            request,
            code="WEB_PREVIEW_FAILED",
            message=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except Exception as exc:
        return error_response(
            request,
            code="WEB_PREVIEW_ERROR",
            message="An unexpected error occurred while fetching the preview.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={"reason": str(exc)[:200]},
        )

    return success_response(request, preview.to_dict())
