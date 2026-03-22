from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

import tiktoken
from openai import OpenAI

DEFAULT_TOKENIZER_MODEL = "text-embedding-3-small"


def count_tokens(text: str, model_name: str | None = None) -> int:
    return len(_encoding(model_name).encode(text))


def chunk_text(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    model_name: str | None = None,
) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    encoding = _encoding(model_name)
    tokens = encoding.encode(text)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunks.append(encoding.decode(chunk_tokens).strip())
        if end >= len(tokens):
            break
        start = end - chunk_overlap
    return [chunk for chunk in chunks if chunk]


def embed_texts_with_config(
    texts: Sequence[str],
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> list[list[float]]:
    if not texts:
        return []

    client_kwargs = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)
    vectors: list[list[float]] = []
    batch_size = 32

    for start in range(0, len(texts), batch_size):
        batch = list(texts[start : start + batch_size])
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)

    return vectors


@lru_cache(maxsize=8)
def _encoding(model_name: str | None):
    resolved_model = model_name or DEFAULT_TOKENIZER_MODEL
    try:
        return tiktoken.encoding_for_model(resolved_model)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")
