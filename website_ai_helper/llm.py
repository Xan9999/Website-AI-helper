"""Clients for the chat and embedding endpoints (OpenAI-compatible)."""
from __future__ import annotations

from openai import OpenAI

from website_ai_helper import config

_chat_client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)
_embed_client = OpenAI(base_url=config.EMBED_BASE_URL, api_key=config.EMBED_API_KEY)


def chat_client() -> OpenAI:
    return _chat_client


def embed_texts(texts: list[str], kind: str = "document") -> list[list[float]]:
    """Embed a batch. `kind` ('document'|'query') selects the task prefix."""
    prefix = config.EMBED_DOC_PREFIX if kind == "document" else config.EMBED_QUERY_PREFIX
    inputs = [f"{prefix}{t}" for t in texts]
    resp = _embed_client.embeddings.create(model=config.EMBED_MODEL, input=inputs)
    ordered = sorted(resp.data, key=lambda d: d.index)
    return [d.embedding for d in ordered]


def embed_text(text: str, kind: str = "query") -> list[float]:
    return embed_texts([text], kind=kind)[0]
