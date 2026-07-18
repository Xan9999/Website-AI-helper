"""Qdrant vector store wrapper (embedded local folder or remote server).

Embedded mode allows only one process to open the folder at a time, so run
ingestion while the server is stopped, or use a Qdrant server (set QDRANT_URL)
to do both at once.

Hybrid retrieval: collections created by this version store TWO vectors per
chunk — "dense" (the embedding model's semantic vector) and "lexical" (a
sparse term-frequency vector, see lexical.py). Searches run both and merge
the rankings with Reciprocal Rank Fusion (RRF) on the server: a chunk ranked
high by EITHER meaning or exact keywords makes the final top-K. Collections
created by older versions (one unnamed dense vector) are detected at runtime
and searched dense-only exactly as before — re-ingest a collection (delete +
ingest, see README) to upgrade it to hybrid.
"""
from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    Fusion,
    FusionQuery,
    Modifier,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from website_ai_helper import config
from website_ai_helper.lexical import sparse_encode

_client: QdrantClient | None = None

# collection name -> "hybrid" | "legacy", resolved once per process.
_modes: dict[str, str] = {}


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
            vectors_config={"dense": VectorParams(size=config.EMBED_DIM,
                                                  distance=Distance.COSINE)},
            # IDF weighting is computed by Qdrant over the live collection, so
            # the client only stores raw term frequencies (see lexical.py).
            sparse_vectors_config={"lexical": SparseVectorParams(modifier=Modifier.IDF)},
        )
        _modes[name] = "hybrid"


def _mode(client: QdrantClient, name: str) -> str:
    """'hybrid' (named dense + sparse lexical vectors) or 'legacy' (single
    unnamed dense vector, created by older versions). Cached per process."""
    if name not in _modes:
        info = client.get_collection(name)
        _modes[name] = "hybrid" if info.config.params.sparse_vectors else "legacy"
    return _modes[name]


def upsert(client: QdrantClient, vectors: list[list[float]], payloads: list[dict],
           name: str | None = None) -> None:
    name = name or config.QDRANT_COLLECTION
    hybrid = _mode(client, name) == "hybrid"

    def point(v: list[float], p: dict) -> PointStruct:
        if hybrid:
            idx, vals = sparse_encode(p.get("text", ""))
            vector = {"dense": v, "lexical": SparseVector(indices=idx, values=vals)}
        else:
            vector = v  # legacy collection: keep writing its original schema
        return PointStruct(id=str(uuid.uuid4()), vector=vector, payload=p)

    client.upsert(collection_name=name,
                  points=[point(v, p) for v, p in zip(vectors, payloads)])


def search(client: QdrantClient, query_vector: list[float], top_k: int,
           name: str | None = None, query_text: str | None = None) -> list[dict]:
    """Top-K chunks for a query. On hybrid collections this runs BOTH a dense
    (semantic) and a lexical (exact-keyword) search and fuses the two rankings
    with Reciprocal Rank Fusion; on legacy collections it is a plain dense
    search. NOTE: RRF scores are rank-based (~0.01..0.03), not cosine — don't
    compare them against cosine thresholds."""
    name = name or config.QDRANT_COLLECTION

    if _mode(client, name) == "hybrid":
        idx, vals = sparse_encode(query_text or "")
        prefetch = [Prefetch(query=query_vector, using="dense", limit=top_k * 3)]
        if idx:  # a query with no word tokens has no lexical signal
            prefetch.append(Prefetch(query=SparseVector(indices=idx, values=vals),
                                     using="lexical", limit=top_k * 3))
        hits = client.query_points(
            collection_name=name, prefetch=prefetch,
            query=FusionQuery(fusion=Fusion.RRF), limit=top_k, with_payload=True,
        ).points
    else:
        hits = client.query_points(
            collection_name=name, query=query_vector, limit=top_k, with_payload=True,
        ).points
    return [{"score": h.score, **(h.payload or {})} for h in hits]
