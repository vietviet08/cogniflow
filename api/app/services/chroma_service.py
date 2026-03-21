from __future__ import annotations

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
