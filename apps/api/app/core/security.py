from fastapi import Header, HTTPException, status


def require_bearer_token(authorization: str | None = Header(default=None)) -> str:
    """Minimal auth guard placeholder for write endpoints."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return authorization.split(" ", maxsplit=1)[1]
