"""ChromaDB vector store — store and query entity embeddings."""

from __future__ import annotations

import chromadb

from app.config import settings

_client: chromadb.HttpClient | None = None


def _get_client() -> chromadb.HttpClient:
    global _client
    if _client is None:
        _client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return _client


def get_collection() -> chromadb.Collection:
    return _get_client().get_or_create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
    )


def upsert_chunks(chunks: list[dict], embeddings: list[list[float]]) -> None:
    """Store entity chunks in ChromaDB. Idempotent — safe to re-run."""
    collection = get_collection()
    collection.upsert(
        ids=[c["entity_name"] for c in chunks],
        embeddings=embeddings,
        documents=[c["chunk"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )


def similarity_search(query_embedding: list[float], n_results: int = 3) -> list[dict]:
    """
    Return top-n results sorted by cosine similarity (highest first).

    ChromaDB cosine space returns distance = 1 - cosine_similarity,
    so similarity = 1 - distance (range 0–1 for normalised vectors).
    """
    collection = get_collection()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        hits.append({
            "entity_name": meta.get("entity_name", ""),
            "document":    doc,
            "score":       round(1.0 - dist, 4),   # cosine similarity
            "metadata":    meta,
        })
    return hits
