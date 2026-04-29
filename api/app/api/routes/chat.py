import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.contracts.common import error_response, success_response
from app.core.security import require_current_user, require_project_role
from app.services.citation_service import hydrate_citations
from app.services.query_service import QueryError, search_knowledge_base
from app.storage.models import ChatMessage, ChatSession, User
from app.storage.repositories.project_repository import ProjectRepository

router = APIRouter()


class CreateChatSessionRequest(BaseModel):
    title: str | None = None


@router.post("/projects/{project_id}/chat/sessions")
def create_chat_session(
    project_id: uuid.UUID,
    payload: CreateChatSessionRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="editor")
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist",
            status_code=404,
        )

    session = ChatSession(
        project_id=project_id,
        title=payload.title or "New Chat"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return success_response(
        request,
        {
            "id": str(session.id),
            "project_id": str(session.project_id),
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
        },
        status_code=201,
    )


@router.get("/projects/{project_id}/chat/sessions")
def list_chat_sessions(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    require_project_role(db, project_id=project_id, user=current_user, minimum_role="viewer")
    # Verify project exists
    project = ProjectRepository(db).get(project_id)
    if not project:
        return error_response(
            request,
            "PROJECT_NOT_FOUND",
            "Project does not exist",
            status_code=404,
        )

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.project_id == project_id)
        .order_by(ChatSession.created_at.desc())
        .all()
    )
    return success_response(
        request,
        {
            "items": [
                {
                    "id": str(s.id),
                    "project_id": str(s.project_id),
                    "title": s.title,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in sessions
            ],
            "total": len(sessions),
        },
    )


@router.get("/chat/sessions/{session_id}/messages")
def list_chat_messages(
    session_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = db.get(ChatSession, session_id)
    if not session:
        return error_response(
            request,
            "SESSION_NOT_FOUND",
            "Chat session does not exist",
            status_code=404,
        )
    require_project_role(
        db,
        project_id=session.project_id,
        user=current_user,
        minimum_role="viewer",
    )

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return success_response(
        request,
        {
            "items": [
                {
                    "id": str(m.id),
                    "session_id": str(m.session_id),
                    "role": m.role,
                    "content": m.content,
                    "citations": hydrate_citations(db, m.citations or []),
                    "is_bookmarked": m.is_bookmarked,
                    "rating": m.rating,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in messages
            ],
            "total": len(messages),
        },
    )


class SendChatMessageRequest(BaseModel):
    content: str
    provider: str = "openai"
    top_k: int = 5


@router.post("/chat/sessions/{session_id}/messages")
def send_chat_message(
    session_id: uuid.UUID,
    payload: SendChatMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    session = db.get(ChatSession, session_id)
    if not session:
        return error_response(
            request,
            "SESSION_NOT_FOUND",
            "Chat session does not exist",
            status_code=404,
        )
    require_project_role(
        db,
        project_id=session.project_id,
        user=current_user,
        minimum_role="editor",
    )

    history_context = _load_recent_chat_context(db, session_id)
    contextual_query = _build_contextual_query(payload.content, history_context)

    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=payload.content,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user_msg)
    db.commit()

    try:
        rag_result = search_knowledge_base(
            db=db,
            project_id=session.project_id,
            query=contextual_query,
            provider=payload.provider,
            top_k=payload.top_k,
            conversation_context=[
                *history_context,
                {"role": "user", "content": payload.content},
            ],
        )
    except QueryError as e:
        return error_response(
            request,
            e.code,
            e.message,
            status_code=e.status_code,
            details=e.details,
        )
    except Exception as e:
        return error_response(request, "RAG_ERROR", str(e), status_code=500)

    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=rag_result["answer"],
        citations=rag_result["citations"],
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)
    
    # 5. Optional auto-title: If this is the first message, rename the session
    first_msg_check = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
    if first_msg_check <= 2 and session.title == "New Chat":
        session.title = payload.content[:50] + ("..." if len(payload.content) > 50 else "")

    db.commit()
    db.refresh(assistant_msg)
    db.refresh(user_msg)

    return success_response(
        request,
        {
            "user_message": {
                "id": str(user_msg.id),
                "role": user_msg.role,
                "content": user_msg.content,
            },
            "assistant_message": {
                "id": str(assistant_msg.id),
                "role": assistant_msg.role,
                "content": assistant_msg.content,
                "citations": assistant_msg.citations,
                "retrieval": rag_result.get("retrieval"),
            },
            "context": {
                "history_turns_used": len(history_context),
                "history_aware_retrieval": contextual_query != payload.content,
            },
        },
        status_code=201,
    )


def _load_recent_chat_context(
    db: Session,
    session_id: uuid.UUID,
    *,
    limit: int = 8,
) -> list[dict[str, str]]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    ordered = list(reversed(messages))
    return [
        {
            "role": message.role,
            "content": _compact_chat_context(message.content),
        }
        for message in ordered
        if message.role in {"user", "assistant"} and message.content.strip()
    ]


def _build_contextual_query(
    current_query: str,
    history_context: list[dict[str, str]],
) -> str:
    if not history_context:
        return current_query

    context_lines = [
        f"[{message['role']}] {message['content']}"
        for message in history_context[-6:]
        if message.get("content")
    ]
    if not context_lines:
        return current_query
    return (
        f"{current_query}\n\n"
        "Recent conversation context for resolving follow-up references:\n"
        f"{'\n'.join(context_lines)}"
    )


def _compact_chat_context(value: str, *, limit: int = 500) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3]}..."


class UpdateMessageRequest(BaseModel):
    is_bookmarked: bool | None = None
    rating: int | None = None


@router.put("/chat/messages/{message_id}")
def update_chat_message(
    message_id: uuid.UUID,
    payload: UpdateMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_current_user),
):
    msg = db.get(ChatMessage, message_id)
    if not msg:
        return error_response(
            request,
            "MESSAGE_NOT_FOUND",
            "Chat message does not exist",
            status_code=404,
        )
    session = db.get(ChatSession, msg.session_id)
    if session:
        require_project_role(
            db,
            project_id=session.project_id,
            user=current_user,
            minimum_role="editor",
        )

    if payload.is_bookmarked is not None:
        msg.is_bookmarked = payload.is_bookmarked
    
    if payload.rating is not None:
        msg.rating = payload.rating

    db.commit()
    return success_response(request, {"success": True})
