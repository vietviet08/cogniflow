import uuid

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.storage.models import Insight, InsightCitation
from app.storage.repositories.base import BaseRepository


class InsightRepository(BaseRepository[Insight]):
    def __init__(self, db: Session):
        super().__init__(db)

    def create(
        self,
        project_id: uuid.UUID,
        query: str,
        summary: str | None,
        findings: list | None,
        provider: str | None,
        model_id: str | None,
        run_id: uuid.UUID | None,
    ) -> Insight:
        insight = Insight(
            project_id=project_id,
            query=query,
            summary=summary,
            findings=findings,
            provider=provider,
            model_id=model_id,
            run_id=run_id,
            status="completed",
        )
        self.db.add(insight)
        self.db.commit()
        self.db.refresh(insight)
        return insight

    def get(self, insight_id: uuid.UUID) -> Insight | None:
        return self.db.get(Insight, insight_id)

    def list_by_project(self, project_id: uuid.UUID) -> list[Insight]:
        return (
            self.db.query(Insight)
            .filter(Insight.project_id == project_id)
            .order_by(desc(Insight.created_at))
            .all()
        )

    def add_citations(
        self,
        insight: Insight,
        citations: list[dict],
    ) -> list[InsightCitation]:
        rows = [
            InsightCitation(
                insight_id=insight.id,
                source_id=c.get("source_id"),
                source_type=c.get("source_type"),
                document_id=c.get("document_id"),
                chunk_id=c.get("chunk_id"),
                title=c.get("title"),
                url=c.get("url"),
                page_number=c.get("page_number"),
            )
            for c in citations
        ]
        self.db.add_all(rows)
        self.db.commit()
        return rows

    def get_citations(self, insight_id: uuid.UUID) -> list[InsightCitation]:
        return (
            self.db.query(InsightCitation)
            .filter(InsightCitation.insight_id == insight_id)
            .all()
        )
