"""Qdrant vector store wrapper (embedded local folder or remote server).

Embedded mode allows only one process to open the folder at a time, so run
ingestion while the server is stopped, or use a Qdrant server (set QDRANT_URL)
to do both at once.
"""
from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from website_ai_helper import config

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if config.QDRANT_URL:
            _client = QdrantClient(url=config.QDRANT_URL)
        else:
            config.ensure_data_dir()
            try:
                _client = QdrantClient(path=config.QDRANT_PATH)
            except RuntimeError as exc:
                if "already accessed by another instance" not in str(exc):
                    raise
                raise SystemExit(
                    f"Cannot open the vector store at '{config.QDRANT_PATH}' — it's "
                    "already open in another process (e.g. `website-ai-helper serve` "
                    "is running). Embedded Qdrant only allows ONE process at a time.\n"
                    "Fix: stop that process first, then retry — or avoid this "
                    "entirely by running a real Qdrant server and setting QDRANT_URL "
                    "in .env (e.g. `docker run -p 6333:6333 qdrant/qdrant`), which "
                    "lets ingest and serve run at the same time."
                ) from exc
    return _client


def ensure_collection(client: QdrantClient, name: str | None = None) -> None:
    name = name or config.QDRANT_COLLECTION
    existing = {c.name for c in client.get_collections().collections}
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=config.EMBED_DIM, distance=Distance.COSINE),
        )


def upsert(client: QdrantClient, vectors: list[list[float]], payloads: list[dict],
           name: str | None = None) -> None:
    name = name or config.QDRANT_COLLECTION
    points = [
        PointStruct(id=str(uuid.uuid4()), vector=v, payload=p)
        for v, p in zip(vectors, payloads)
    ]
    client.upsert(collection_name=name, points=points)


def search(client: QdrantClient, query_vector: list[float], top_k: int,
           name: str | None = None) -> list[dict]:
    name = name or config.QDRANT_COLLECTION
    hits = client.query_points(
        collection_name=name, query=query_vector, limit=top_k, with_payload=True,
    ).points
    return [{"score": h.score, **(h.payload or {})} for h in hits]
