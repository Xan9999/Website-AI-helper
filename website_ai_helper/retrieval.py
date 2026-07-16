"""Vector retrieval: embed the query, search Qdrant, return the best chunks."""
from __future__ import annotations

from website_ai_helper import config, vectorstore
from website_ai_helper.llm import embed_text


def retrieve(query: str, top_k: int | None = None, collection: str | None = None) -> list[dict]:
    top_k = top_k or config.TOP_K
    client = vectorstore.get_client()
    vectorstore.ensure_collection(client, collection)
    query_vector = embed_text(query, kind="query")
    hits = vectorstore.search(client, query_vector, top_k, collection)
    return [h for h in hits if h.get("score", 0.0) >= config.SCORE_THRESHOLD]
