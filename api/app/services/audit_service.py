from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.storage.models import AuditLog


def log_audit_event(
    db: Session,
    *,
    action: str,
    target_type: str,
    target_id: str | None = None,
    user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    organization_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    row = AuditLog(
        action=action,
        target_type=target_type,
        target_id=target_id,
        user_id=user_id,
        project_id=project_id,
        organization_id=organization_id,
        payload=payload or {},
    )
    db.add(row)
