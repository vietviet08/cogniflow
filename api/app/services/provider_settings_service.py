from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.storage.models import ProviderCredential
from app.storage.repositories.provider_credential_repository import ProviderCredentialRepository

SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "display_name": "OpenAI",
        "supports": ["embeddings", "chat"],
        "chat_models": ["gpt-4o", "gpt-4o-mini"],
        "embedding_models": ["text-embedding-3-small", "text-embedding-3-large"],
    },
    "gemini": {
        "display_name": "Gemini",
        "supports": ["chat"],
        "chat_models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "embedding_models": [],
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
    chat_model: str | None,
    embedding_model: str | None,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    cleaned_key = api_key.strip()
    if not cleaned_key:
        raise ProviderSettingsError("api_key must not be empty.")
    validated_chat_model = validate_chat_model(normalized_provider, chat_model)
    validated_embedding_model = validate_embedding_model(normalized_provider, embedding_model)

    credential = ProviderCredentialRepository(db).upsert(
        project_id=project_id,
        provider=normalized_provider,
        api_key=cleaned_key,
        chat_model=validated_chat_model,
        embedding_model=validated_embedding_model,
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
    return resolve_chat_provider_config(db, project_id, provider)["api_key"]


def resolve_chat_provider_config(
    db: Session,
    project_id: uuid.UUID,
    provider: str,
) -> dict[str, str]:
    normalized_provider = normalize_provider(provider)
    credential = ProviderCredentialRepository(db).get_by_project_provider(
        project_id=project_id,
        provider=normalized_provider,
    )
    if credential is None or not credential.api_key.strip():
        raise ProviderSettingsError(
            f"{SUPPORTED_PROVIDERS[normalized_provider]['display_name']} API key is required. "
            "Configure it in project settings.",
        )
    if not credential.chat_model:
        raise ProviderSettingsError(
            f"{SUPPORTED_PROVIDERS[normalized_provider]['display_name']} chat model is required. "
            "Configure it in project settings.",
        )
    return {"api_key": credential.api_key.strip(), "chat_model": credential.chat_model}


def resolve_embedding_provider_config(
    db: Session,
    project_id: uuid.UUID,
    provider: str,
) -> dict[str, str]:
    normalized_provider = normalize_provider(provider)
    credential = ProviderCredentialRepository(db).get_by_project_provider(
        project_id=project_id,
        provider=normalized_provider,
    )
    if credential is None or not credential.api_key.strip():
        raise ProviderSettingsError(
            f"{SUPPORTED_PROVIDERS[normalized_provider]['display_name']} API key is required. "
            "Configure it in project settings.",
        )
    if not credential.embedding_model:
        raise ProviderSettingsError(
            f"{SUPPORTED_PROVIDERS[normalized_provider]['display_name']} "
            "embedding model is required. "
            "Configure it in project settings.",
        )
    return {
        "api_key": credential.api_key.strip(),
        "embedding_model": credential.embedding_model,
    }


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ProviderSettingsError(
            f"Unsupported provider '{provider}'. "
            f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}.",
        )
    return normalized


def validate_chat_model(provider: str, chat_model: str | None) -> str:
    cleaned = (chat_model or "").strip()
    if not cleaned:
        raise ProviderSettingsError("chat_model must not be empty.")

    available_chat_models = SUPPORTED_PROVIDERS[provider]["chat_models"]
    if cleaned not in available_chat_models:
        raise ProviderSettingsError(
            f"Unsupported chat model '{cleaned}' for provider '{provider}'.",
        )
    return cleaned


def validate_embedding_model(provider: str, embedding_model: str | None) -> str | None:
    available_embedding_models = SUPPORTED_PROVIDERS[provider]["embedding_models"]
    cleaned = (embedding_model or "").strip()
    if not available_embedding_models:
        return None
    if not cleaned:
        raise ProviderSettingsError("embedding_model must not be empty.")
    if cleaned not in available_embedding_models:
        raise ProviderSettingsError(
            f"Unsupported embedding model '{cleaned}' for provider '{provider}'.",
        )
    return cleaned


def _serialize_provider_status(
    provider: str,
    credential: ProviderCredential | None,
) -> dict[str, Any]:
    provider_config = SUPPORTED_PROVIDERS[provider]
    configured_source = "missing"
    configured = False
    masked_api_key: str | None = None
    updated_at: str | None = None
    chat_model: str | None = None
    embedding_model: str | None = None

    if credential is not None and credential.api_key.strip():
        has_chat_model = bool(credential.chat_model)
        requires_embedding_model = bool(provider_config["embedding_models"])
        has_embedding_model = bool(credential.embedding_model) if requires_embedding_model else True
        configured = has_chat_model and has_embedding_model
        configured_source = "project"
        masked_api_key = mask_api_key(credential.api_key)
        updated_at = credential.updated_at.isoformat() if credential.updated_at else None
        chat_model = credential.chat_model
        embedding_model = credential.embedding_model

    return {
        "provider": provider,
        "display_name": provider_config["display_name"],
        "supports": provider_config["supports"],
        "configured": configured,
        "configured_source": configured_source,
        "masked_api_key": masked_api_key,
        "chat_model": chat_model,
        "embedding_model": embedding_model,
        "available_chat_models": provider_config["chat_models"],
        "available_embedding_models": provider_config["embedding_models"],
        "updated_at": updated_at,
    }


def mask_api_key(api_key: str) -> str:
    cleaned = api_key.strip()
    if len(cleaned) <= 8:
        return "*" * len(cleaned)
    return f"{cleaned[:4]}...{cleaned[-4:]}"
