import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


USERS_ID_FK = "users.id"
PROJECTS_ID_FK = "projects.id"
PROCESSING_RUNS_ID_FK = "processing_runs.id"
RADAR_EVENTS_ID_FK = "radar_events.id"
ORGANIZATIONS_ID_FK = "organizations.id"


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_memberships_org_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(ORGANIZATIONS_ID_FK), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(USERS_ID_FK), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="member") # owner, admin, member
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(ORGANIZATIONS_ID_FK), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="admin")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(USERS_ID_FK), nullable=False)
    token_name: Mapped[str] = mapped_column(String(255), default="default")
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    token_last_four: Mapped[str] = mapped_column(String(4))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    type: Mapped[str] = mapped_column(String(50))
    original_uri: Mapped[str | None] = mapped_column(Text())
    storage_path: Mapped[str | None] = mapped_column(Text())
    checksum: Mapped[str | None] = mapped_column(String(128))
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON())
    status: Mapped[str] = mapped_column(String(50), default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint("project_id", "provider", name="uq_integration_connections_project"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    provider: Mapped[str] = mapped_column(String(50))
    account_label: Mapped[str | None] = mapped_column(String(255))
    access_token: Mapped[str] = mapped_column(Text())
    base_url: Mapped[str | None] = mapped_column(Text())
    connection_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON())
    status: Mapped[str] = mapped_column(String(20), default="connected")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProviderCredential(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint("project_id", "provider", name="uq_provider_credentials_project"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    provider: Mapped[str] = mapped_column(String(50))
    api_key: Mapped[str] = mapped_column(Text())
    base_url: Mapped[str | None] = mapped_column(Text())
    chat_model: Mapped[str | None] = mapped_column(String(128))
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sources.id"), nullable=True)
    job_type: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    queue_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    job_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ProcessingRun(Base):
    __tablename__ = "processing_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    run_type: Mapped[str] = mapped_column(String(50))
    model_id: Mapped[str | None] = mapped_column(Text())
    prompt_hash: Mapped[str | None] = mapped_column(Text())
    config_hash: Mapped[str | None] = mapped_column(Text())
    retrieval_config: Mapped[dict | None] = mapped_column(JSON())
    run_metadata: Mapped[dict | None] = mapped_column(JSON())
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(PROCESSING_RUNS_ID_FK),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectMembership(Base):
    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_memberships_project_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(USERS_ID_FK), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text())
    raw_path: Mapped[str | None] = mapped_column(Text())
    clean_text: Mapped[str] = mapped_column(Text())
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text())
    chroma_id: Mapped[str | None] = mapped_column(Text())
    embedding_model: Mapped[str | None] = mapped_column(String(128))
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QueryRun(Base):
    __tablename__ = "query_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    query_text: Mapped[str] = mapped_column(Text())
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    filters: Mapped[dict | None] = mapped_column(JSON())
    answer_text: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    query: Mapped[str] = mapped_column(Text())
    title: Mapped[str] = mapped_column(String(255))
    report_type: Mapped[str] = mapped_column(String(50))
    format: Mapped[str] = mapped_column(String(50), default="markdown")
    content: Mapped[str | None] = mapped_column(Text())
    structured_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON())
    status: Mapped[str] = mapped_column(String(20), default="completed")
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(PROCESSING_RUNS_ID_FK),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Insight(Base):
    __tablename__ = "insights"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    query: Mapped[str] = mapped_column(Text())
    summary: Mapped[str | None] = mapped_column(Text())
    findings: Mapped[dict | None] = mapped_column(JSON())  # list of {theme, points}
    provider: Mapped[str | None] = mapped_column(String(50))
    model_id: Mapped[str | None] = mapped_column(String(128))
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey(PROCESSING_RUNS_ID_FK),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InsightCitation(Base):
    __tablename__ = "insight_citations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    insight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("insights.id"), nullable=False)
    source_id: Mapped[str | None] = mapped_column(Text())
    source_type: Mapped[str | None] = mapped_column(String(50))
    document_id: Mapped[str | None] = mapped_column(Text())
    chunk_id: Mapped[str | None] = mapped_column(Text())
    title: Mapped[str | None] = mapped_column(Text())
    url: Mapped[str | None] = mapped_column(Text())
    page_number: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportInsight(Base):
    """Junction table connecting a Report to the Insights it was generated from."""

    __tablename__ = "report_insights"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("reports.id"), nullable=False)
    insight_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("insights.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50))  # 'user' or 'assistant'
    content: Mapped[str] = mapped_column(Text())
    citations: Mapped[list[dict] | None] = mapped_column(JSON())
    is_bookmarked: Mapped[bool] = mapped_column(default=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 for up, -1 for down
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RadarSource(Base):
    __tablename__ = "radar_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(Text())
    category: Mapped[str] = mapped_column(String(50), default="general")
    default_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_snapshot_excerpt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class RadarEvent(Base):
    __tablename__ = "radar_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("radar_sources.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), default="change_detected")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text())
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON())
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RadarAction(Base):
    __tablename__ = "radar_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(RADAR_EVENTS_ID_FK), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text())
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date_suggested: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="open")
    channel_targets: Mapped[dict[str, Any] | None] = mapped_column(JSON())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(USERS_ID_FK), nullable=True)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(USERS_ID_FK), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GtmOutput(Base):
    __tablename__ = "gtm_outputs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(RADAR_EVENTS_ID_FK), nullable=True)
    output_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text())
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AlertDelivery(Base):
    __tablename__ = "alert_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey(PROJECTS_ID_FK), nullable=False)
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey(RADAR_EVENTS_ID_FK), nullable=True)
    action_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("radar_actions.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(50))
    destination: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_excerpt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1)
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
