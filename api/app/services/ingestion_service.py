from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from fastapi import UploadFile

from app.core.config import get_settings

ARXIV_ID_PATTERN = re.compile(r"(?P<id>\d{4}\.\d{4,5}(?:v\d+)?)")
ARXIV_ATOM_NAMESPACE = {"atom": "http://www.w3.org/2005/Atom"}


class IngestionError(Exception):
    pass


def _upload_root() -> Path:
    root = Path(get_settings().upload_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _source_directory(source_id: uuid.UUID) -> Path:
    directory = _upload_root() / str(source_id)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _sanitize_filename(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "upload.bin"


def save_uploaded_file(source_id: uuid.UUID, upload: UploadFile) -> tuple[str, str]:
    filename = _sanitize_filename(upload.filename or "upload.bin")
    destination = _source_directory(source_id) / filename
    content = upload.file.read()
    destination.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    return str(destination), checksum


def ingest_remote_source(source_id: uuid.UUID, url: str) -> tuple[str, str, str]:
    arxiv_id = extract_arxiv_id(url)
    payload = fetch_arxiv_record(arxiv_id) if arxiv_id else fetch_web_article(url)
    payload["ingested_from"] = url

    destination = _source_directory(source_id) / "source.json"
    raw = json.dumps(payload, ensure_ascii=True, indent=2)
    destination.write_text(raw, encoding="utf-8")
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    source_type = "arxiv" if arxiv_id else "url"
    return str(destination), checksum, source_type


def extract_arxiv_id(reference: str) -> str | None:
    parsed = urlparse(reference)
    candidates = [reference]
    if parsed.path:
        candidates.extend(part for part in parsed.path.split("/") if part)

    for candidate in candidates:
        cleaned = candidate.removesuffix(".pdf")
        match = ARXIV_ID_PATTERN.search(cleaned)
        if match:
            return match.group("id")
    return None


def fetch_arxiv_record(arxiv_id: str) -> dict[str, Any]:
    response = requests.get(
        "https://export.arxiv.org/api/query",
        params={"id_list": arxiv_id},
        timeout=20,
    )
    response.raise_for_status()

    root = ElementTree.fromstring(response.text)
    entry = root.find("atom:entry", ARXIV_ATOM_NAMESPACE)
    if entry is None:
        raise IngestionError(f"arXiv item '{arxiv_id}' was not found.")

    title = _xml_text(entry, "atom:title")
    summary = _xml_text(entry, "atom:summary")
    link = _xml_text(entry, "atom:id")

    if not title or not summary:
        raise IngestionError(f"arXiv item '{arxiv_id}' returned incomplete metadata.")

    return {
        "title": " ".join(title.split()),
        "content": " ".join(summary.split()),
        "source": "arxiv",
        "url": link or f"https://arxiv.org/abs/{arxiv_id}",
    }


def fetch_web_article(url: str) -> dict[str, Any]:
    response = requests.get(url, timeout=20, headers={"User-Agent": "Cogniflow/0.1"})
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        heading = soup.find(["h1", "h2"])
        if heading:
            title = heading.get_text(" ", strip=True)

    paragraphs = [node.get_text(" ", strip=True) for node in soup.find_all("p")]
    content = "\n".join(paragraph for paragraph in paragraphs if paragraph)

    if not content:
        body = soup.body.get_text(" ", strip=True) if soup.body else soup.get_text(" ", strip=True)
        content = " ".join(body.split())

    if not content:
        raise IngestionError(f"No readable content extracted from '{url}'.")

    return {
        "title": title or url,
        "content": content,
        "source": urlparse(url).netloc or "web",
        "url": url,
    }


def _xml_text(entry: ElementTree.Element, path: str) -> str:
    node = entry.find(path, ARXIV_ATOM_NAMESPACE)
    return node.text.strip() if node is not None and node.text else ""
