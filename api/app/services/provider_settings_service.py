from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.storage.models import ProviderCredential
from app.storage.repositories.provider_credential_repository import ProviderCredentialRepository

SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "display_name": "OpenAI",
        "supports": ["embeddings", "chat"],
        "env_alias": "OPENAI_API_KEY",
    },
    "gemini": {
        "display_name": "Gemini",
        "supports": ["chat"],
        "env_alias": "GEMINI_API_KEY",
    },
}


class ProviderSettingsError(Exception):
    pass


def list_provider_statuses(db: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    repository = ProviderCredentialRepository(db)
    credentials = {
        credential.provider: credential
        for credential in repository.list_by_project(project_id)
    }
    return [
        _serialize_provider_status(
            provider=provider,
            credential=credentials.get(provider),
        )
        for provider in SUPPORTED_PROVIDERS
    ]


def upsert_provider_key(
    db: Session,
    project_id: uuid.UUID,
    provider: str,
    api_key: str,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    cleaned_key = api_key.strip()
    if not cleaned_key:
        raise ProviderSettingsError("api_key must not be empty.")

    credential = ProviderCredentialRepository(db).upsert(
        project_id=project_id,
        provider=normalized_provider,
        api_key=cleaned_key,
    )
    return _serialize_provider_status(provider=normalized_provider, credential=credential)


def delete_provider_key(
    db: Session,
    project_id: uuid.UUID,
    provider: str,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    removed = ProviderCredentialRepository(db).delete_by_project_provider(
        project_id=project_id,
        provider=normalized_provider,
    )
    payload = _serialize_provider_status(provider=normalized_provider, credential=None)
    payload["removed"] = removed
    return payload


def resolve_provider_api_key(
    db: Session,
    project_id: uuid.UUID,
    provider: str,
) -> str:
    normalized_provider = normalize_provider(provider)
    credential = ProviderCredentialRepository(db).get_by_project_provider(
        project_id=project_id,
        provider=normalized_provider,
    )
    if credential is not None and credential.api_key.strip():
        return credential.api_key.strip()

    settings = get_settings()
    environment_api_key = _environment_api_key(settings, normalized_provider)
    if environment_api_key:
        return environment_api_key

    provider_config = SUPPORTED_PROVIDERS[normalized_provider]
    raise ProviderSettingsError(
        f"{provider_config['display_name']} API key is required. "
        f"Configure it in project settings or set {provider_config['env_alias']}."
    )


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ProviderSettingsError(
            f"Unsupported provider '{provider}'. "
            f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}.",
        )
    return normalized


def _serialize_provider_status(
    provider: str,
    credential: ProviderCredential | None,
) -> dict[str, Any]:
    provider_config = SUPPORTED_PROVIDERS[provider]
    settings = get_settings()
    environment_api_key = _environment_api_key(settings, provider)

    configured_source = "missing"
    configured = False
    masked_api_key: str | None = None
    updated_at: str | None = None

    if credential is not None and credential.api_key.strip():
        configured = True
        configured_source = "project"
        masked_api_key = mask_api_key(credential.api_key)
        updated_at = credential.updated_at.isoformat() if credential.updated_at else None
    elif environment_api_key:
        configured = True
        configured_source = "environment"

    return {
        "provider": provider,
        "display_name": provider_config["display_name"],
        "supports": provider_config["supports"],
        "configured": configured,
        "configured_source": configured_source,
        "masked_api_key": masked_api_key,
        "updated_at": updated_at,
    }


def _environment_api_key(settings: Mapping[str, Any] | Any, provider: str) -> str:
    if provider == "openai":
        return str(getattr(settings, "openai_api_key", "") or "")
    if provider == "gemini":
        return str(getattr(settings, "gemini_api_key", "") or "")
    return ""


def mask_api_key(api_key: str) -> str:
    cleaned = api_key.strip()
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"
