from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import tiktoken
from openai import OpenAI

from app.core.config import get_settings


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text))


def chunk_text(text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    tokens = _encoding().encode(text)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(_encoding().decode(chunk_tokens).strip())
        if end >= len(tokens):
            break
        start = end - chunk_overlap
    return [chunk for chunk in chunks if chunk]


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    return embed_texts_with_config(texts=texts)


def embed_texts_with_config(
    texts: Sequence[str],
    api_key: str | None = None,
    model: str | None = None,
) -> list[list[float]]:
    if not texts:
        return []

    settings = get_settings()
    resolved_api_key = api_key or settings.openai_api_key
    resolved_model = model or settings.embedding_model
    if not resolved_api_key:
        raise ValueError("OPENAI_API_KEY is required to create embeddings.")

    client = OpenAI(api_key=resolved_api_key)
    vectors: list[list[float]] = []
    batch_size = 32

    for start in range(0, len(texts), batch_size):
        batch = list(texts[start : start + batch_size])
        response = client.embeddings.create(model=resolved_model, input=batch)
        vectors.extend(item.embedding for item in response.data)

    return vectors


@lru_cache(maxsize=1)
def _encoding():
    try:
        return tiktoken.encoding_for_model(get_settings().embedding_model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")
