from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import chromadb

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_chroma_client():
    settings = get_settings()
    return chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def get_collection() -> Any:
    settings = get_settings()
    client = get_chroma_client()
    return client.get_or_create_collection(name=settings.chroma_collection)


def get_named_collection(name: str) -> Any:
    client = get_chroma_client()
    return client.get_or_create_collection(name=name)


def get_retrieval_collection(embedding_model: str) -> Any:
    settings = get_settings()
    suffix = re.sub(r"[^a-z0-9]+", "-", embedding_model.lower()).strip("-")
    collection_name = f"{settings.chroma_collection}-{suffix}"
    return get_named_collection(collection_name)
