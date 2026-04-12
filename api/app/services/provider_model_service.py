from __future__ import annotations

from typing import Any

import requests

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class ProviderModelDiscoveryError(Exception):
    pass


def discover_provider_models(
    provider: str,
    api_key: str,
    base_url: str | None = None,
) -> dict[str, list[str]]:
    normalized_provider = provider.strip().lower()
    cleaned_key = api_key.strip()
    if not cleaned_key:
        raise ProviderModelDiscoveryError("api_key must not be empty.")

    if normalized_provider == "openai":
        return _discover_openai_models(cleaned_key, base_url)
    if normalized_provider == "gemini":
        return _discover_gemini_models(cleaned_key)

    raise ProviderModelDiscoveryError(f"Unsupported provider '{provider}'.")


def _discover_openai_models(
    api_key: str,
    base_url: str | None,
) -> dict[str, list[str]]:
    resolved_base_url = (base_url or DEFAULT_OPENAI_BASE_URL).rstrip("/")
    is_custom_base_url = resolved_base_url != DEFAULT_OPENAI_BASE_URL
    try:
        response = requests.get(
            f"{resolved_base_url}/models",
            headers={
                "Authorization": f"Bearer {api_key}",
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderModelDiscoveryError("Failed to fetch models from OpenAI.") from exc

    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list):
        raise ProviderModelDiscoveryError("OpenAI model discovery returned an invalid payload.")

    model_ids = sorted(
        {
            str(item.get("id", "")).strip()
            for item in data
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        },
    )
    if is_custom_base_url:
        # Compatible gateways may expose non-OpenAI naming conventions.
        # For custom base URLs, keep all non-embedding models selectable as chat models.
        chat_models = [model_id for model_id in model_ids if not _is_openai_embedding_model(model_id)]
    else:
        chat_models = [model_id for model_id in model_ids if _is_openai_chat_model(model_id)]
    embedding_models = [model_id for model_id in model_ids if _is_openai_embedding_model(model_id)]
    return {
        "chat_models": chat_models,
        "embedding_models": embedding_models,
    }


def _discover_gemini_models(api_key: str) -> dict[str, list[str]]:
    models: list[dict[str, Any]] = []
    page_token: str | None = None

    while True:
        params: dict[str, str] = {}
        if page_token:
            params["pageToken"] = page_token
        try:
            response = requests.get(
                f"{DEFAULT_GEMINI_BASE_URL}/models",
                headers={"x-goog-api-key": api_key},
                params=params,
                timeout=20,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ProviderModelDiscoveryError("Failed to fetch models from Gemini.") from exc

        payload = response.json()
        page_models = payload.get("models")
        if isinstance(page_models, list):
            models.extend(item for item in page_models if isinstance(item, dict))

        next_page_token = payload.get("nextPageToken")
        if not isinstance(next_page_token, str) or not next_page_token.strip():
            break
        page_token = next_page_token.strip()

    chat_models: list[str] = []
    embedding_models: list[str] = []

    for item in models:
        raw_name = str(item.get("name", "")).strip()
        if not raw_name:
            continue
        model_name = raw_name.removeprefix("models/")
        methods = item.get("supportedGenerationMethods")
        if not isinstance(methods, list):
            continue
        normalized_methods = {str(method).strip() for method in methods if str(method).strip()}
        if "generateContent" in normalized_methods:
            chat_models.append(model_name)
        if "embedContent" in normalized_methods:
            embedding_models.append(model_name)

    return {
        "chat_models": sorted(set(chat_models)),
        "embedding_models": sorted(set(embedding_models)),
    }


def _is_openai_embedding_model(model_id: str) -> bool:
    return "embedding" in model_id.lower()


def _is_openai_chat_model(model_id: str) -> bool:
    normalized = model_id.lower()
    if _is_openai_embedding_model(normalized):
        return False
    excluded_tokens = (
        "audio",
        "image",
        "moderation",
        "omni-moderation",
        "realtime",
        "search",
        "similarity",
        "transcribe",
        "tts",
        "whisper",
    )
    if any(token in normalized for token in excluded_tokens):
        return False
    return normalized.startswith(("chatgpt-", "gpt-", "o1", "o3", "o4"))
