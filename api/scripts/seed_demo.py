from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime, timedelta

from app.core.security import hash_password
from app.services.embedding_service import LOCAL_EMBEDDING_MODEL
from app.storage.db import SessionLocal
from app.storage.models import (
    Approval,
    Chunk,
    Document,
    GtmOutput,
    Insight,
    InsightCitation,
    Organization,
    OrganizationMembership,
    ProcessingRun,
    Project,
    ProjectMembership,
    RadarAction,
    RadarEvent,
    RadarSource,
    Report,
    ReportInsight,
    Source,
    User,
)

DEMO_EMAIL = os.getenv("DEMO_OWNER_EMAIL", "demo@notemesh.local")
DEMO_PASSWORD = os.getenv("DEMO_OWNER_PASSWORD", "notemesh-demo")
DEMO_ORG_NAME = os.getenv("DEMO_ORG_NAME", "Portfolio Demo Workspace")
DEMO_PROJECT_NAME = os.getenv("DEMO_PROJECT_NAME", "NoteMesh Portfolio Demo")


def main() -> int:
    db = SessionLocal()
    try:
        user = _get_or_create_user(db)
        organization = _get_or_create_organization(db, user)
        project = _get_or_create_project(db, organization, user)

        if db.query(Source).filter(Source.project_id == project.id).count() == 0:
            seed_project_story(db, project=project, user=user)
            db.commit()
            status = "created"
        else:
            status = "already_present"

        print(
            "\n".join(
                [
                    f"Demo seed {status}.",
                    f"Email: {DEMO_EMAIL}",
                    f"Password: {DEMO_PASSWORD}",
                    f"Project: {DEMO_PROJECT_NAME}",
                ]
            )
        )
        return 0
    finally:
        db.close()


def _get_or_create_user(db):
    user = db.query(User).filter(User.email == DEMO_EMAIL).one_or_none()
    if user is not None:
        return user

    user = User(
        email=DEMO_EMAIL,
        display_name="Demo Owner",
        password_hash=hash_password(DEMO_PASSWORD),
        role="admin",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _get_or_create_organization(db, user):
    organization = db.query(Organization).filter(Organization.name == DEMO_ORG_NAME).one_or_none()
    if organization is None:
        organization = Organization(name=DEMO_ORG_NAME, slug="portfolio-demo")
        db.add(organization)
        db.commit()
        db.refresh(organization)

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.user_id == user.id,
        )
        .one_or_none()
    )
    if membership is None:
        db.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role="owner"))
        db.commit()
    return organization


def _get_or_create_project(db, organization, user):
    project = db.query(Project).filter(Project.name == DEMO_PROJECT_NAME).one_or_none()
    if project is None:
        project = Project(
            organization_id=organization.id,
            name=DEMO_PROJECT_NAME,
            description="Portfolio-ready demo for evidence-backed market intelligence.",
        )
        db.add(project)
        db.commit()
        db.refresh(project)

    membership = (
        db.query(ProjectMembership)
        .filter(ProjectMembership.project_id == project.id, ProjectMembership.user_id == user.id)
        .one_or_none()
    )
    if membership is None:
        db.add(ProjectMembership(project_id=project.id, user_id=user.id, role="owner"))
        db.commit()
    return project


def seed_project_story(db, *, project, user) -> None:
    now = datetime.now(UTC)
    source_specs = [
        {
            "title": "Competitor Pricing Page",
            "uri": "https://competitor.example/pricing",
            "text": (
                "Competitor Alpha raised the Pro plan from 49 USD to 69 USD and added "
                "team analytics only to enterprise contracts. The change creates a "
                "positioning gap for mid-market teams that need audit-ready research."
            ),
            "category": "pricing",
        },
        {
            "title": "Customer Review Digest",
            "uri": "https://reviews.example/notemesh-category",
            "text": (
                "Analysts praise fast summarization, but repeatedly ask for source "
                "traceability, report lineage, and explicit confidence indicators before "
                "sharing outputs with leadership."
            ),
            "category": "review",
        },
        {
            "title": "Policy Update Brief",
            "uri": "https://policy.example/ai-recordkeeping",
            "text": (
                "New AI recordkeeping guidance requires teams to retain evidence, model "
                "configuration, timestamps, and operator context for generated business "
                "recommendations."
            ),
            "category": "policy",
        },
    ]

    chunks = []
    source_ids = []
    for index, spec in enumerate(source_specs):
        source = Source(
            project_id=project.id,
            type="url",
            original_uri=spec["uri"],
            storage_path=None,
            checksum=f"demo-checksum-{index}",
            source_metadata={"title": spec["title"], "category": spec["category"]},
            status="completed",
        )
        db.add(source)
        db.flush()
        source_ids.append(str(source.id))

        document = Document(
            source_id=source.id,
            title=spec["title"],
            raw_path=None,
            clean_text=spec["text"],
            token_count=len(spec["text"].split()),
        )
        db.add(document)
        db.flush()

        chunk = Chunk(
            document_id=document.id,
            chunk_index=0,
            content=spec["text"],
            chroma_id=f"demo-{source.id}",
            embedding_model=LOCAL_EMBEDDING_MODEL,
            chunk_metadata={
                "source_id": str(source.id),
                "source_type": "url",
                "document_id": str(document.id),
                "chunk_id": "",
                "title": spec["title"],
                "url": spec["uri"],
                "quote": spec["text"],
            },
        )
        db.add(chunk)
        db.flush()
        chunk.chunk_metadata = {**chunk.chunk_metadata, "chunk_id": str(chunk.id)}
        chunks.append((source, document, chunk, spec))

    processing_run = ProcessingRun(
        project_id=project.id,
        run_type="processing",
        model_id=LOCAL_EMBEDDING_MODEL,
        config_hash="demo-processing-config",
        run_metadata={
            "source_ids": source_ids,
            "source_count": len(source_ids),
            "chunk_size": 800,
            "chunk_overlap": 120,
            "documents_created": len(chunks),
            "chunks_created": len(chunks),
        },
    )
    db.add(processing_run)
    db.flush()

    insight_run = ProcessingRun(
        project_id=project.id,
        run_type="insight",
        model_id="gpt-4o-mini",
        prompt_hash="demo-insight-prompt",
        config_hash="demo-insight-config",
        retrieval_config={"embedding_model": LOCAL_EMBEDDING_MODEL, "top_k": 3},
        run_metadata={
            "query": "What changed in the market this week?",
            "provider": "openai",
            "max_sources": 20,
            "sources_used": len(chunks),
        },
    )
    db.add(insight_run)
    db.flush()

    insight = Insight(
        project_id=project.id,
        query="What changed in the market this week?",
        summary=(
            "Pricing pressure, audit requirements, and buyer demand for traceability "
            "create a clear opening for evidence-first research workflows."
        ),
        findings=[
            {
                "theme": "Market pressure",
                "points": [
                    "Competitor Alpha moved analytics upmarket.",
                    "Mid-market teams still need trustworthy research output.",
                ],
            },
            {
                "theme": "Trust and governance",
                "points": [
                    "Reviews ask for lineage and confidence indicators.",
                    "Policy guidance increases pressure to retain run metadata.",
                ],
            },
        ],
        provider="openai",
        model_id="gpt-4o-mini",
        run_id=insight_run.id,
        status="completed",
    )
    db.add(insight)
    db.flush()

    citations = []
    for source, document, chunk, spec in chunks:
        citation = InsightCitation(
            insight_id=insight.id,
            source_id=str(source.id),
            source_type="url",
            document_id=str(document.id),
            chunk_id=str(chunk.id),
            title=spec["title"],
            url=spec["uri"],
            page_number=None,
        )
        db.add(citation)
        citations.append(_citation_payload(source, document, chunk, spec))

    report_run = ProcessingRun(
        project_id=project.id,
        run_type="report",
        model_id="gpt-4o-mini",
        prompt_hash="demo-report-prompt",
        config_hash="demo-report-config",
        run_metadata={
            "report_type": "action_items",
            "format": "markdown",
            "query": "What should the GTM team do next?",
            "provider": "openai",
            "insight_id": str(insight.id),
            "structured_output": True,
        },
    )
    db.add(report_run)
    db.flush()

    structured_payload = {
        "overview": "Turn the market signal into a focused trust-led GTM response.",
        "items": [
            {
                "id": str(uuid.uuid4()),
                "title": "Publish evidence-first positioning brief",
                "description": (
                    "Frame NoteMesh around traceable research outputs, lineage, and "
                    "audit-ready run metadata."
                ),
                "priority": "high",
                "owner_suggested": "Product Marketing",
                "due_date_suggested": "This week",
                "status": "open",
                "citations": citations[:2],
            },
            {
                "id": str(uuid.uuid4()),
                "title": "Prepare competitor pricing response",
                "description": "Create a battlecard for teams evaluating Alpha Pro.",
                "priority": "medium",
                "owner_suggested": "Sales Enablement",
                "due_date_suggested": "Next week",
                "status": "needs_review",
                "citations": citations[:1],
            },
        ],
    }

    report = Report(
        project_id=project.id,
        query="What should the GTM team do next?",
        title="Action Items: GTM Trust Response",
        report_type="action_items",
        format="markdown",
        content=(
            "# Action Items: GTM Trust Response\n\n"
            "## Action Items\n\n"
            "- Publish evidence-first positioning brief\n"
            "- Prepare competitor pricing response\n"
        ),
        structured_payload=structured_payload,
        status="completed",
        run_id=report_run.id,
    )
    db.add(report)
    db.flush()
    db.add(ReportInsight(report_id=report.id, insight_id=insight.id))

    radar_source = RadarSource(
        project_id=project.id,
        name="Competitor Alpha Pricing",
        source_url="https://competitor.example/pricing",
        category="pricing",
        default_owner="Growth PM",
        is_active=True,
        poll_interval_minutes=1440,
        last_checked_at=now - timedelta(hours=2),
        last_content_hash="demo-current",
        last_snapshot_excerpt="Pro plan now starts at 69 USD with analytics gated.",
    )
    db.add(radar_source)
    db.flush()

    radar_event = RadarEvent(
        project_id=project.id,
        source_id=radar_source.id,
        event_type="price_change",
        severity="high",
        title="Competitor Alpha raised Pro pricing",
        summary="Pro pricing moved from 49 USD to 69 USD and analytics moved upmarket.",
        event_metadata={"old_price": "49 USD", "new_price": "69 USD"},
        detected_at=now - timedelta(hours=1),
    )
    db.add(radar_event)
    db.flush()

    action = RadarAction(
        project_id=project.id,
        event_id=radar_event.id,
        assigned_user_id=user.id,
        owner=user.display_name,
        title="Update Alpha battlecard",
        description="Add pricing delta, analytics gating, and trust-led objection handling.",
        due_date_suggested="Tomorrow",
        priority="high",
        status="in_progress",
        channel_targets={"slack": "#gtm-intel"},
    )
    db.add(action)

    output = GtmOutput(
        project_id=project.id,
        event_id=radar_event.id,
        output_type="battlecard",
        title="Alpha Pricing Response Battlecard",
        content=(
            "Lead with evidence lineage, lower operational risk, and faster audit-ready "
            "reporting for mid-market teams."
        ),
        status="draft",
    )
    db.add(output)
    db.flush()

    db.add(
        Approval(
            project_id=project.id,
            target_type="gtm_output",
            target_id=str(output.id),
            status="pending",
            requested_by_user_id=user.id,
        )
    )


def _citation_payload(source, document, chunk, spec):
    return {
        "citation_id": str(chunk.id),
        "source_id": str(source.id),
        "source_type": "url",
        "document_id": str(document.id),
        "chunk_id": str(chunk.id),
        "title": spec["title"],
        "url": spec["uri"],
        "page_number": None,
        "quote": spec["text"],
    }


if __name__ == "__main__":
    raise SystemExit(main())
