import uuid

from sqlalchemy.orm import Session

from app.storage.models import ProviderCredential
from app.storage.repositories.base import BaseRepository


class ProviderCredentialRepository(BaseRepository[ProviderCredential]):
    def __init__(self, db: Session):
        super().__init__(db)

    def get_by_project_provider(
        self,
        project_id: uuid.UUID,
        provider: str,
    ) -> ProviderCredential | None:
        return (
            self.db.query(ProviderCredential)
            .filter(
                ProviderCredential.project_id == project_id,
                ProviderCredential.provider == provider,
            )
            .one_or_none()
        )

    def list_by_project(self, project_id: uuid.UUID) -> list[ProviderCredential]:
        return (
            self.db.query(ProviderCredential)
            .filter(ProviderCredential.project_id == project_id)
            .order_by(ProviderCredential.provider.asc())
            .all()
        )

    def upsert(
        self,
        project_id: uuid.UUID,
        provider: str,
        api_key: str,
        chat_model: str | None,
        embedding_model: str | None,
    ) -> ProviderCredential:
        credential = self.get_by_project_provider(project_id, provider)
        if credential is None:
            credential = ProviderCredential(
                project_id=project_id,
                provider=provider,
                api_key=api_key,
                chat_model=chat_model,
                embedding_model=embedding_model,
            )
        else:
            credential.api_key = api_key
            credential.chat_model = chat_model
            credential.embedding_model = embedding_model

        self.db.add(credential)
        self.db.commit()
        self.db.refresh(credential)
        return credential

    def delete_by_project_provider(self, project_id: uuid.UUID, provider: str) -> bool:
        credential = self.get_by_project_provider(project_id, provider)
        if credential is None:
            return False

        self.db.delete(credential)
        self.db.commit()
        return True
