"""Voyage AI embedding helpers 
"""

from __future__ import annotations

import voyageai

from app.config import settings

_client: voyageai.Client | None = None

_VOYAGE_MODEL = "voyage-4-lite"
_BATCH_SIZE = 128


def _get_client() -> voyageai.Client:
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=settings.voyage_api_key)
    return _client


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed a list of document strings in batches."""
    client = _get_client()
    embeddings: list[list[float]] = []
    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        result = client.embed(batch, model=_VOYAGE_MODEL, input_type="document")
        embeddings.extend(result.embeddings)
    return embeddings


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    client = _get_client()
    result = client.embed([text], model=_VOYAGE_MODEL, input_type="query")
    return result.embeddings[0]
