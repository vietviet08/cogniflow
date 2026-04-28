from __future__ import annotations

import uuid
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.services.provider_model_service import (
    ProviderModelDiscoveryError,
    discover_provider_models,
)
from app.storage.models import ProviderCredential
from app.storage.repositories.provider_credential_repository import ProviderCredentialRepository

SUPPORTED_PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {
        "display_name": "OpenAI",
        "supports": ["chat"],
        "supports_base_url": True,
    },
    "gemini": {
        "display_name": "Gemini",
        "supports": ["chat"],
        "supports_base_url": False,
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
    items: list[dict[str, Any]] = []
    for provider in SUPPORTED_PROVIDERS:
        credential = credentials.get(provider)
        discovered_models: dict[str, list[str]] | None = None
        model_discovery_error: str | None = None
        if credential is not None and decrypt_secret(credential.api_key).strip():
            try:
                discovered_models = discover_provider_models(
                    provider=provider,
                    api_key=decrypt_secret(credential.api_key),
                    base_url=credential.base_url,
                )
            except ProviderModelDiscoveryError as exc:
                model_discovery_error = str(exc)
        items.append(
            _serialize_provider_status(
                provider=provider,
                credential=credential,
                discovered_models=discovered_models,
                model_discovery_error=model_discovery_error,
            )
        )
    return items


def upsert_provider_key(
    db: Session,
    project_id: uuid.UUID,
    provider: str,
    api_key: str,
    base_url: str | None,
    chat_model: str | None,
    embedding_model: str | None,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    cleaned_key = api_key.strip()
    if not cleaned_key:
        raise ProviderSettingsError("api_key must not be empty.")
    validated_base_url = validate_base_url(normalized_provider, base_url)
    discovered_models = _discover_models_for_provider(
        provider=normalized_provider,
        api_key=cleaned_key,
        base_url=validated_base_url,
    )
    validated_chat_model = validate_chat_model(chat_model, discovered_models["chat_models"])
    if "embeddings" in SUPPORTED_PROVIDERS[normalized_provider]["supports"]:
        validated_embedding_model = validate_embedding_model(
            embedding_model,
            discovered_models["embedding_models"],
        )
    else:
        validated_embedding_model = None

    credential = ProviderCredentialRepository(db).upsert(
        project_id=project_id,
        provider=normalized_provider,
        api_key=encrypt_secret(cleaned_key),
        base_url=validated_base_url,
        chat_model=validated_chat_model,
        embedding_model=validated_embedding_model,
    )
    return _serialize_provider_status(
        provider=normalized_provider,
        credential=credential,
        discovered_models=discovered_models,
        model_discovery_error=None,
    )


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
    decrypted_api_key = decrypt_secret(credential.api_key) if credential is not None else ""
    if credential is None or not decrypted_api_key.strip():
        raise ProviderSettingsError(
            f"{SUPPORTED_PROVIDERS[normalized_provider]['display_name']} API key is required. "
            "Configure it in project settings.",
        )
    if not credential.chat_model:
        raise ProviderSettingsError(
            f"{SUPPORTED_PROVIDERS[normalized_provider]['display_name']} chat model is required. "
            "Configure it in project settings.",
        )
    payload = {
        "api_key": decrypted_api_key.strip(),
        "chat_model": credential.chat_model,
    }
    if credential.base_url:
        payload["base_url"] = credential.base_url
    return payload


def normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PROVIDERS:
        raise ProviderSettingsError(
            f"Unsupported provider '{provider}'. "
            f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}.",
        )
    return normalized


def discover_provider_models_for_request(
    db: Session,
    project_id: uuid.UUID,
    provider: str,
    api_key: str | None,
    base_url: str | None,
) -> dict[str, Any]:
    normalized_provider = normalize_provider(provider)
    credential = ProviderCredentialRepository(db).get_by_project_provider(
        project_id=project_id,
        provider=normalized_provider,
    )

    payload_key = (api_key or "").strip()
    stored_api_key = decrypt_secret(credential.api_key) if credential else ""
    resolved_api_key = payload_key or stored_api_key.strip()
    if not resolved_api_key:
        raise ProviderSettingsError(
            f"{SUPPORTED_PROVIDERS[normalized_provider]['display_name']} API key is required "
            "to load models.",
        )

    payload_base_url = (base_url or "").strip()
    resolved_base_url = payload_base_url or (credential.base_url if credential else None)
    validated_base_url = validate_base_url(normalized_provider, resolved_base_url)
    discovered_models = _discover_models_for_provider(
        provider=normalized_provider,
        api_key=resolved_api_key,
        base_url=validated_base_url,
    )
    return {
        "provider": normalized_provider,
        "display_name": SUPPORTED_PROVIDERS[normalized_provider]["display_name"],
        "supports_base_url": SUPPORTED_PROVIDERS[normalized_provider]["supports_base_url"],
        "base_url": validated_base_url,
        "available_chat_models": discovered_models["chat_models"],
        "available_embedding_models": (
            discovered_models["embedding_models"]
            if "embeddings" in SUPPORTED_PROVIDERS[normalized_provider]["supports"]
            else []
        ),
        "source": "payload" if payload_key or payload_base_url else "project",
    }


def validate_chat_model(chat_model: str | None, available_chat_models: list[str]) -> str:
    cleaned = (chat_model or "").strip()
    if not cleaned:
        raise ProviderSettingsError("chat_model must not be empty.")
    if cleaned not in available_chat_models:
        raise ProviderSettingsError(
            f"Selected chat model '{cleaned}' is not available for this provider.",
        )
    return cleaned


def validate_embedding_model(
    embedding_model: str | None,
    available_embedding_models: list[str],
) -> str | None:
    cleaned = (embedding_model or "").strip()
    if not available_embedding_models:
        return None
    if not cleaned:
        raise ProviderSettingsError("embedding_model must not be empty.")
    if cleaned not in available_embedding_models:
        raise ProviderSettingsError(
            f"Selected embedding model '{cleaned}' is not available for this provider.",
        )
    return cleaned


def validate_base_url(provider: str, base_url: str | None) -> str | None:
    cleaned = (base_url or "").strip()
    if not cleaned:
        return None

    if not SUPPORTED_PROVIDERS[provider]["supports_base_url"]:
        raise ProviderSettingsError(
            f"base_url is not supported for provider '{provider}'.",
        )

    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ProviderSettingsError("base_url must be a valid absolute http(s) URL.")

    return cleaned.rstrip("/")


def _serialize_provider_status(
    provider: str,
    credential: ProviderCredential | None,
    discovered_models: dict[str, list[str]] | None = None,
    model_discovery_error: str | None = None,
) -> dict[str, Any]:
    provider_config = SUPPORTED_PROVIDERS[provider]
    configured_source = "missing"
    configured = False
    masked_api_key: str | None = None
    updated_at: str | None = None
    chat_model: str | None = None
    embedding_model: str | None = None
    base_url: str | None = None
    available_chat_models = discovered_models["chat_models"] if discovered_models else []
    available_embedding_models = (
        discovered_models["embedding_models"]
        if discovered_models and "embeddings" in provider_config["supports"]
        else []
    )

    decrypted_api_key = decrypt_secret(credential.api_key) if credential is not None else ""
    if credential is not None and decrypted_api_key.strip():
        has_chat_model = bool(credential.chat_model)
        requires_embedding_model = "embeddings" in provider_config["supports"]
        has_embedding_model = bool(credential.embedding_model) if requires_embedding_model else True
        configured = has_chat_model and has_embedding_model
        configured_source = "project"
        masked_api_key = mask_api_key(decrypted_api_key)
        updated_at = credential.updated_at.isoformat() if credential.updated_at else None
        chat_model = credential.chat_model
        if requires_embedding_model:
            embedding_model = credential.embedding_model
        base_url = credential.base_url

    return {
        "provider": provider,
        "display_name": provider_config["display_name"],
        "supports": provider_config["supports"],
        "supports_base_url": provider_config["supports_base_url"],
        "configured": configured,
        "configured_source": configured_source,
        "masked_api_key": masked_api_key,
        "base_url": base_url,
        "chat_model": chat_model,
        "embedding_model": embedding_model,
        "available_chat_models": available_chat_models,
        "available_embedding_models": available_embedding_models,
        "model_discovery_error": model_discovery_error,
        "updated_at": updated_at,
    }


def mask_api_key(api_key: str) -> str:
    return mask_secret(api_key) or ""


def _discover_models_for_provider(
    provider: str,
    api_key: str,
    base_url: str | None,
) -> dict[str, list[str]]:
    try:
        return discover_provider_models(
            provider=provider,
            api_key=api_key,
            base_url=base_url,
        )
    except ProviderModelDiscoveryError as exc:
        raise ProviderSettingsError(str(exc)) from exc
