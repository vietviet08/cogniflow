from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.services.ingestion_service import save_source_bytes, save_source_snapshot
from app.storage.models import IntegrationConnection
from app.storage.repositories.integration_connection_repository import (
    IntegrationConnectionRepository,
)
from app.storage.repositories.job_repository import JobRepository
from app.storage.repositories.source_repository import SourceRepository

NOTION_VERSION = "2022-06-28"
GOOGLE_DRIVE_API_BASE = "https://www.googleapis.com/drive/v3"
NOTION_API_BASE = "https://api.notion.com/v1"
SLACK_API_BASE = "https://slack.com/api"

INTEGRATION_PROVIDERS: dict[str, dict[str, Any]] = {
    "google_drive": {
        "display_name": "Google Drive",
        "supports_base_url": False,
        "reference_label": "File URL or ID",
        "description": "Import a Drive PDF or Google Doc snapshot into this project.",
    },
    "notion": {
        "display_name": "Notion",
        "supports_base_url": False,
        "reference_label": "Page URL or ID",
        "description": "Import a Notion page as a text snapshot.",
    },
    "slack": {
        "display_name": "Slack",
        "supports_base_url": False,
        "reference_label": "Thread permalink",
        "description": "Import a Slack thread transcript into this project.",
    },
    "confluence": {
        "display_name": "Confluence",
        "supports_base_url": True,
        "reference_label": "Page URL or ID",
        "description": "Import a Confluence page snapshot using the site API.",
    },
}

GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
GOOGLE_PDF_MIME = "application/pdf"


class IntegrationError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str = "INTEGRATION_FAILED",
        status_code: int = 422,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


@dataclass
class ImportedSourcePayload:
    source_type: str
    original_uri: str
    storage_kind: str  # "file" | "snapshot"
    file_bytes: bytes | None
    snapshot_payload: dict[str, Any] | None
    source_metadata: dict[str, Any]


def list_integration_statuses(db: Session, project_id: uuid.UUID) -> list[dict[str, Any]]:
    repo = IntegrationConnectionRepository(db)
    configured = {connection.provider: connection for connection in repo.list_by_project(project_id)}
    items: list[dict[str, Any]] = []

    for provider, metadata in INTEGRATION_PROVIDERS.items():
        connection = configured.get(provider)
        items.append(_serialize_connection_status(provider, metadata, connection))

    return items


def upsert_integration_connection(
    db: Session,
    *,
    project_id: uuid.UUID,
    provider: str,
    access_token: str | None,
    account_label: str | None,
    base_url: str | None,
    connection_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    cleaned_base_url = _normalize_base_url(base_url)
    if INTEGRATION_PROVIDERS[normalized_provider]["supports_base_url"] and not cleaned_base_url:
        raise IntegrationError(
            "This integration requires a base URL.",
            code="INTEGRATION_CONNECTION_INVALID",
        )

    repo = IntegrationConnectionRepository(db)
    connection = repo.get_by_project_and_provider(project_id, normalized_provider)
    cleaned_token = (access_token or "").strip()
    if not cleaned_token and connection is None:
        raise IntegrationError(
            "An access token is required to connect this integration.",
            code="INTEGRATION_CONNECTION_INVALID",
        )

    if connection is None:
        connection = IntegrationConnection(
            project_id=project_id,
            provider=normalized_provider,
            account_label=(account_label or "").strip() or None,
            access_token=cleaned_token,
            base_url=cleaned_base_url,
            connection_metadata=connection_metadata or {},
            status="connected",
        )
    else:
        connection.account_label = (account_label or "").strip() or None
        if cleaned_token:
            connection.access_token = cleaned_token
        connection.base_url = cleaned_base_url
        connection.connection_metadata = connection_metadata or {}
        connection.status = "connected"

    repo.save(connection)
    return _serialize_connection_status(
        normalized_provider,
        INTEGRATION_PROVIDERS[normalized_provider],
        connection,
    )


def delete_integration_connection(
    db: Session,
    *,
    project_id: uuid.UUID,
    provider: str,
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    repo = IntegrationConnectionRepository(db)
    connection = repo.get_by_project_and_provider(project_id, normalized_provider)
    if connection:
        repo.delete(connection)
    return _serialize_connection_status(
        normalized_provider,
        INTEGRATION_PROVIDERS[normalized_provider],
        None,
    )


def import_integration_source(
    db: Session,
    *,
    project_id: uuid.UUID,
    provider: str,
    item_reference: str,
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    reference = item_reference.strip()
    if not reference:
        raise IntegrationError(
            "Provide a page URL, file URL, or item identifier to import.",
            code="INTEGRATION_IMPORT_INVALID",
        )

    connection = IntegrationConnectionRepository(db).get_by_project_and_provider(
        project_id,
        normalized_provider,
    )
    if connection is None:
        raise IntegrationError(
            "Connect this integration before importing content.",
            code="INTEGRATION_NOT_CONNECTED",
            status_code=409,
        )

    imported = _fetch_imported_source(connection, reference)
    source = SourceRepository(db).create(
        project_id=project_id,
        source_type=imported.source_type,
        original_uri=imported.original_uri,
        source_metadata=imported.source_metadata,
        status="queued",
    )

    if imported.storage_kind == "file":
        storage_path, checksum = save_source_bytes(
            source.id,
            imported.original_uri,
            imported.file_bytes or b"",
        )
    else:
        storage_path, checksum = save_source_snapshot(
            source.id,
            imported.snapshot_payload or {},
        )

    source.storage_path = storage_path
    source.checksum = checksum
    source.status = "completed"
    db.add(source)
    db.commit()
    db.refresh(source)

    job = JobRepository(db).create(
        project_id=project_id,
        source_id=source.id,
        job_type="integration_ingestion",
        status="completed",
        progress=100,
    )

    return {
        "source_id": str(source.id),
        "job_id": str(job.id),
        "status": job.status,
        "source_type": source.type,
        "filename": source.original_uri,
        "provider": normalized_provider,
    }


def _fetch_imported_source(
    connection: IntegrationConnection,
    item_reference: str,
) -> ImportedSourcePayload:
    if connection.provider == "google_drive":
        return _import_google_drive_source(connection, item_reference)
    if connection.provider == "notion":
        return _import_notion_source(connection, item_reference)
    if connection.provider == "slack":
        return _import_slack_source(connection, item_reference)
    if connection.provider == "confluence":
        return _import_confluence_source(connection, item_reference)
    raise IntegrationError("Unsupported integration provider.")


def _import_google_drive_source(
    connection: IntegrationConnection,
    item_reference: str,
) -> ImportedSourcePayload:
    file_id = _extract_google_drive_file_id(item_reference)
    headers = {"Authorization": f"Bearer {connection.access_token}"}
    metadata_response = requests.get(
        f"{GOOGLE_DRIVE_API_BASE}/files/{file_id}",
        params={"fields": "id,name,mimeType,webViewLink"},
        headers=headers,
        timeout=20,
    )
    _raise_for_status(metadata_response, "Google Drive metadata request failed.")
    metadata = metadata_response.json()

    name = str(metadata.get("name") or f"{file_id}.txt")
    mime_type = str(metadata.get("mimeType") or "")
    web_url = str(metadata.get("webViewLink") or item_reference)
    source_metadata = {
        "provider": "google_drive",
        "external_id": file_id,
        "external_url": web_url,
        "mime_type": mime_type,
        "imported_at": _utc_iso_now(),
    }

    if mime_type == GOOGLE_DOC_MIME:
        export_response = requests.get(
            f"{GOOGLE_DRIVE_API_BASE}/files/{file_id}/export",
            params={"mimeType": "text/plain"},
            headers=headers,
            timeout=20,
        )
        _raise_for_status(export_response, "Google Doc export failed.")
        text = export_response.text.strip()
        if not text:
            raise IntegrationError("Google Doc returned empty content.")
        return ImportedSourcePayload(
            source_type="google_drive",
            original_uri=f"{name}.txt" if not name.lower().endswith(".txt") else name,
            storage_kind="snapshot",
            file_bytes=None,
            snapshot_payload={
                "title": name,
                "content": text,
                "url": web_url,
                "source": "google_drive",
                "external_id": file_id,
            },
            source_metadata=source_metadata,
        )

    if mime_type == GOOGLE_PDF_MIME or name.lower().endswith(".pdf"):
        file_response = requests.get(
            f"{GOOGLE_DRIVE_API_BASE}/files/{file_id}",
            params={"alt": "media"},
            headers=headers,
            timeout=30,
        )
        _raise_for_status(file_response, "Google Drive file download failed.")
        filename = name if name.lower().endswith(".pdf") else f"{name}.pdf"
        return ImportedSourcePayload(
            source_type="file",
            original_uri=filename,
            storage_kind="file",
            file_bytes=file_response.content,
            snapshot_payload=None,
            source_metadata=source_metadata,
        )

    if name.lower().endswith((".txt", ".md")) or mime_type.startswith("text/"):
        file_response = requests.get(
            f"{GOOGLE_DRIVE_API_BASE}/files/{file_id}",
            params={"alt": "media"},
            headers=headers,
            timeout=30,
        )
        _raise_for_status(file_response, "Google Drive text file download failed.")
        return ImportedSourcePayload(
            source_type="file",
            original_uri=name,
            storage_kind="file",
            file_bytes=file_response.content,
            snapshot_payload=None,
            source_metadata=source_metadata,
        )

    raise IntegrationError(
        "Google Drive MVP currently supports Google Docs, PDF files, and plain text files.",
        code="INTEGRATION_IMPORT_UNSUPPORTED",
    )


def _import_notion_source(
    connection: IntegrationConnection,
    item_reference: str,
) -> ImportedSourcePayload:
    page_id = _extract_notion_page_id(item_reference)
    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Notion-Version": NOTION_VERSION,
    }
    page_response = requests.get(
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=headers,
        timeout=20,
    )
    _raise_for_status(page_response, "Notion page request failed.")
    page = page_response.json()

    title = _extract_notion_page_title(page) or "Notion Page"
    content = _collect_notion_block_text(page_id, headers)
    if not content.strip():
        raise IntegrationError("Notion page returned no readable text.")

    url = str(page.get("url") or item_reference)
    return ImportedSourcePayload(
        source_type="notion",
        original_uri=f"{title}.txt",
        storage_kind="snapshot",
        file_bytes=None,
        snapshot_payload={
            "title": title,
            "content": content.strip(),
            "url": url,
            "source": "notion",
            "external_id": page_id,
        },
        source_metadata={
            "provider": "notion",
            "external_id": page_id,
            "external_url": url,
            "imported_at": _utc_iso_now(),
        },
    )


def _import_slack_source(
    connection: IntegrationConnection,
    item_reference: str,
) -> ImportedSourcePayload:
    channel_id, ts, permalink = _extract_slack_thread_reference(item_reference)
    headers = {"Authorization": f"Bearer {connection.access_token}"}
    response = requests.get(
        f"{SLACK_API_BASE}/conversations.replies",
        params={"channel": channel_id, "ts": ts},
        headers=headers,
        timeout=20,
    )
    _raise_for_status(response, "Slack thread request failed.")
    payload = response.json()
    if not payload.get("ok"):
        raise IntegrationError(
            str(payload.get("error") or "Slack API returned an error."),
            code="INTEGRATION_UPSTREAM_ERROR",
            status_code=502,
        )

    messages = payload.get("messages") or []
    if not messages:
        raise IntegrationError("Slack thread returned no messages.")

    lines: list[str] = []
    for message in messages:
        text = str(message.get("text") or "").strip()
        if not text:
            continue
        user = str(message.get("user") or message.get("username") or "unknown")
        lines.append(f"{user}: {text}")

    title = _truncate_title(lines[0] if lines else f"Slack thread {channel_id}")
    content = "\n".join(lines).strip()
    if not content:
        raise IntegrationError("Slack thread returned no readable text.")

    return ImportedSourcePayload(
        source_type="slack",
        original_uri=f"{title}.txt",
        storage_kind="snapshot",
        file_bytes=None,
        snapshot_payload={
            "title": title,
            "content": content,
            "url": permalink,
            "source": "slack",
            "external_id": f"{channel_id}:{ts}",
        },
        source_metadata={
            "provider": "slack",
            "external_id": f"{channel_id}:{ts}",
            "external_url": permalink,
            "channel_id": channel_id,
            "thread_ts": ts,
            "imported_at": _utc_iso_now(),
        },
    )


def _import_confluence_source(
    connection: IntegrationConnection,
    item_reference: str,
) -> ImportedSourcePayload:
    page_id = _extract_confluence_page_id(item_reference)
    base_url = _normalize_base_url(connection.base_url)
    if not base_url:
        raise IntegrationError("Confluence base URL is required.")

    headers = {
        "Authorization": f"Bearer {connection.access_token}",
        "Accept": "application/json",
    }
    response = requests.get(
        f"{base_url}/wiki/rest/api/content/{page_id}",
        params={"expand": "body.storage,version,space"},
        headers=headers,
        timeout=20,
    )
    _raise_for_status(response, "Confluence page request failed.")
    payload = response.json()

    title = str(payload.get("title") or "Confluence Page")
    html = (
        payload.get("body", {})
        .get("storage", {})
        .get("value", "")
    )
    text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    if not text:
        raise IntegrationError("Confluence page returned no readable text.")

    web_url = f"{base_url}/wiki{payload.get('_links', {}).get('webui', '')}"
    return ImportedSourcePayload(
        source_type="confluence",
        original_uri=f"{title}.txt",
        storage_kind="snapshot",
        file_bytes=None,
        snapshot_payload={
            "title": title,
            "content": text,
            "url": web_url or item_reference,
            "source": "confluence",
            "external_id": page_id,
        },
        source_metadata={
            "provider": "confluence",
            "external_id": page_id,
            "external_url": web_url or item_reference,
            "base_url": base_url,
            "imported_at": _utc_iso_now(),
        },
    )


def _collect_notion_block_text(block_id: str, headers: dict[str, str], depth: int = 0) -> str:
    response = requests.get(
        f"{NOTION_API_BASE}/blocks/{block_id}/children",
        headers=headers,
        params={"page_size": 100},
        timeout=20,
    )
    _raise_for_status(response, "Notion blocks request failed.")
    payload = response.json()
    lines: list[str] = []

    for block in payload.get("results", []):
        block_type = str(block.get("type") or "")
        block_value = block.get(block_type, {})
        rich_text = block_value.get("rich_text") or block_value.get("text") or []
        text = _flatten_notion_rich_text(rich_text)
        prefix = ""
        if block_type in {"bulleted_list_item", "to_do"}:
            prefix = "- "
        elif block_type == "numbered_list_item":
            prefix = "1. "
        elif block_type.startswith("heading_"):
            prefix = "# "
        if text:
            lines.append(("  " * depth) + prefix + text)
        if block.get("has_children"):
            child_text = _collect_notion_block_text(str(block["id"]), headers, depth + 1)
            if child_text:
                lines.append(child_text)

    return "\n".join(line for line in lines if line.strip())


def _flatten_notion_rich_text(rich_text: list[dict[str, Any]]) -> str:
    return "".join(str(item.get("plain_text") or "") for item in rich_text).strip()


def _extract_notion_page_title(page: dict[str, Any]) -> str:
    properties = page.get("properties") or {}
    for value in properties.values():
        if value.get("type") == "title":
            return _flatten_notion_rich_text(value.get("title") or [])
    return ""


def _extract_google_drive_file_id(reference: str) -> str:
    parsed = urlparse(reference)
    if not parsed.scheme:
        return reference.strip()
    query_id = parse_qs(parsed.query).get("id")
    if query_id:
        return query_id[0]
    match = re.search(r"/d/([A-Za-z0-9_-]+)", parsed.path)
    if match:
        return match.group(1)
    raise IntegrationError("Could not determine Google Drive file ID from this reference.")


def _extract_notion_page_id(reference: str) -> str:
    if "/" not in reference:
        return _normalize_uuid_fragment(reference)
    match = re.search(r"([a-fA-F0-9]{32})", reference)
    if match:
        return _normalize_uuid_fragment(match.group(1))
    match = re.search(r"([a-fA-F0-9-]{36})", reference)
    if match:
        return _normalize_uuid_fragment(match.group(1))
    raise IntegrationError("Could not determine Notion page ID from this reference.")


def _extract_slack_thread_reference(reference: str) -> tuple[str, str, str]:
    parsed = urlparse(reference)
    if not parsed.scheme:
        raise IntegrationError("Slack import currently expects a thread permalink.")
    match = re.search(r"/archives/(?P<channel>[A-Z0-9]+)/p(?P<ts>\d{16})", parsed.path)
    if not match:
        raise IntegrationError("Could not parse Slack thread permalink.")
    raw_ts = match.group("ts")
    return (
        match.group("channel"),
        f"{raw_ts[:10]}.{raw_ts[10:]}",
        reference,
    )


def _extract_confluence_page_id(reference: str) -> str:
    parsed = urlparse(reference)
    if not parsed.scheme:
        return reference.strip()
    query_values = parse_qs(parsed.query)
    if query_values.get("pageId"):
        return query_values["pageId"][0]
    match = re.search(r"/pages/(\d+)", parsed.path)
    if match:
        return match.group(1)
    raise IntegrationError("Could not determine Confluence page ID from this reference.")


def _serialize_connection_status(
    provider: str,
    provider_metadata: dict[str, Any],
    connection: IntegrationConnection | None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "display_name": provider_metadata["display_name"],
        "supports_base_url": provider_metadata["supports_base_url"],
        "reference_label": provider_metadata["reference_label"],
        "description": provider_metadata["description"],
        "configured": connection is not None,
        "status": connection.status if connection else "disconnected",
        "account_label": connection.account_label if connection else None,
        "base_url": connection.base_url if connection else None,
        "masked_access_token": _mask_secret(connection.access_token) if connection else None,
        "updated_at": connection.updated_at.isoformat() if connection and connection.updated_at else None,
    }


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in INTEGRATION_PROVIDERS:
        raise IntegrationError(
            "Unsupported integration provider.",
            code="INTEGRATION_PROVIDER_UNSUPPORTED",
        )
    return normalized


def _normalize_base_url(base_url: str | None) -> str | None:
    cleaned = (base_url or "").strip()
    return cleaned.rstrip("/") if cleaned else None


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * max(4, len(value) - 8)}{value[-4:]}"


def _normalize_uuid_fragment(value: str) -> str:
    cleaned = value.replace("-", "").strip()
    if len(cleaned) != 32:
        raise IntegrationError("Invalid identifier format.")
    return str(uuid.UUID(cleaned))


def _truncate_title(text: str, max_length: int = 72) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return compact[: max_length - 1].rstrip() + "…"


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _raise_for_status(response: requests.Response, default_message: str) -> None:
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise IntegrationError(
            default_message,
            code="INTEGRATION_UPSTREAM_ERROR",
            status_code=502,
            details={
                "provider_status": response.status_code,
                "body": response.text[:240],
            },
        ) from exc
