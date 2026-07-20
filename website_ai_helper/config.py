"""Configuration, loaded from environment / a local .env file.

Everything that varies per deployment lives here. Two ideas make this reusable
across many websites:

  * DATA_DIR is resolved relative to your current working directory, so each
    project folder gets its own vector store / demo DB.
  * QDRANT_COLLECTION names the knowledge base. Give each website its own
    collection (via the --collection CLI flag or the env var) and one install
    can serve many sites.

The LLM and embedding endpoints are just OpenAI-compatible URLs, so this works
with llama.cpp, Ollama, or any compatible server — local or remote.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # read .env from the current working directory, if present


def _get(key: str, default: str) -> str:
    return os.getenv(key, default)


# Where this install writes its data (vector store, demo DB). CWD-relative so
# different project folders stay isolated.
DATA_DIR = Path(_get("DATA_DIR", "data")).resolve()

# --- LLM (chat) endpoint — any OpenAI-compatible server ---
LLM_BASE_URL = _get("LLM_BASE_URL", "http://127.0.0.1:8080/v1")
LLM_API_KEY = _get("LLM_API_KEY", "sk-local")   # llama.cpp ignores the value
LLM_MODEL = _get("LLM_MODEL", "local-chat")
# Extra JSON fields merged into every chat completion request body. Defaults
# to disabling Qwen3's hybrid "thinking" mode (see agent.py), which is only
# understood by llama.cpp/vLLM-style servers. Hosted APIs like OpenAI's real
# api.openai.com reject unrecognized body fields, so set this to "{}" there.
LLM_EXTRA_BODY = json.loads(_get(
    "LLM_EXTRA_BODY", '{"chat_template_kwargs": {"enable_thinking": false}}'
))

# --- Embedding endpoint ---
EMBED_BASE_URL = _get("EMBED_BASE_URL", "http://127.0.0.1:8081/v1")
EMBED_API_KEY = _get("EMBED_API_KEY", "sk-local")
EMBED_MODEL = _get("EMBED_MODEL", "local-embed")
EMBED_DIM = int(_get("EMBED_DIM", "768"))       # must match your embedding model
# nomic-embed needs these prefixes; for a bge model set both to "".
EMBED_DOC_PREFIX = _get("EMBED_DOC_PREFIX", "search_document: ")
EMBED_QUERY_PREFIX = _get("EMBED_QUERY_PREFIX", "search_query: ")

# --- Vector store (Qdrant) ---
# Empty QDRANT_URL -> embedded local folder (no server). Set it to use a server.
QDRANT_URL = _get("QDRANT_URL", "")
QDRANT_PATH = _get("QDRANT_PATH", str(DATA_DIR / "qdrant"))
QDRANT_COLLECTION = _get("QDRANT_COLLECTION", "default")  # one per website

# --- Structured DB (demo SQLite; point at your real DB in structured.py) ---
SQLITE_PATH = _get("SQLITE_PATH", str(DATA_DIR / "demo.db"))

# --- Retrieval / generation ---
TOP_K = int(_get("TOP_K", "3"))
CHUNK_SIZE = int(_get("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(_get("CHUNK_OVERLAP", "160"))
MAX_TOOL_ITERS = int(_get("MAX_TOOL_ITERS", "1"))
# Minimum retrieval score to keep a chunk. Only meaningful for LEGACY
# (dense-only) collections, where scores are cosine similarities; hybrid
# collections return rank-fusion scores on a different scale (~0.01-0.03),
# so leave this at 0 for them.
SCORE_THRESHOLD = float(_get("SCORE_THRESHOLD", "0.0"))
TEMPERATURE = float(_get("TEMPERATURE", "0.2"))
# Penalize repeated tokens — the main lever against degenerate loops (e.g. a
# model repeating the same sentence, sometimes drifting into another language
# mid-repeat). 0 = off; llama.cpp/OpenAI-compatible servers accept 0-2.
FREQUENCY_PENALTY = float(_get("FREQUENCY_PENALTY", "0.4"))
PRESENCE_PENALTY = float(_get("PRESENCE_PENALTY", "0.4"))
# Hard cap on answer length — bounds how far a runaway/looping generation can
# go before it's cut off, regardless of what caused it.
MAX_TOKENS = int(_get("MAX_TOKENS", "500"))
# Max characters of the visitor's current page injected into the prompt.
# Bigger = better "this page" answers but slower time-to-first-token (every
# ~4 chars is a prompt token the GPU must process before answering).
PAGE_MAX_CHARS = int(_get("PAGE_MAX_CHARS", "1500"))
# Rewrite follow-up messages into standalone search queries before retrieval
# (resolves 'how much does IT cost?' using the conversation). Costs one small
# extra LLM call per follow-up turn; first messages are never rewritten.
QUERY_REWRITE = _get("QUERY_REWRITE", "1") == "1"
SITE_NAME = _get("SITE_NAME", "this website")
# Per-collection site names for multi-tenant serving, e.g.
#   SITE_NAMES=acme=Acme Shop,adr=Adrlandia
# The agent introduces itself as "assistant for <name>". Collections without
# an entry fall back to SITE_NAME.
_SITE_NAMES: dict[str, str] = {}
for _pair in _get("SITE_NAMES", "").split(","):
    if "=" in _pair:
        _k, _v = _pair.split("=", 1)
        if _k.strip() and _v.strip():
            _SITE_NAMES[_k.strip()] = _v.strip()


def site_name_for(collection: str | None) -> str:
    """Site name for a request's collection (None = the default collection)."""
    return _SITE_NAMES.get(collection or QDRANT_COLLECTION, SITE_NAME)

# --- CORS ---
# Comma-separated list of origins allowed to call /chat from a browser, e.g.
# "https://acme.com,https://www.acme.com". Empty (default) = allow any origin,
# fine for local testing but should be locked down before going live.
ALLOWED_ORIGINS = [o.strip() for o in _get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# --- Conversation logging + QA review site ---
# Every chat turn (client message, agent reply, latency) is logged to this
# SQLite file for quality assurance. Transcripts are served at /qa, protected
# by QA_TOKEN — if the token is empty, the /qa site is DISABLED (logging still
# happens). Open /qa?token=<QA_TOKEN> to review conversations.
CONVERSATIONS_DB = _get("CONVERSATIONS_DB", str(DATA_DIR / "conversations.db"))
QA_TOKEN = _get("QA_TOKEN", "")

# --- Crawler ---
CRAWL_MAX_PAGES = int(_get("CRAWL_MAX_PAGES", "50"))
CRAWL_SAME_DOMAIN = _get("CRAWL_SAME_DOMAIN", "1") == "1"
# Also download linked PDF files (same-domain rule applies) and ingest their
# text. Detected by the .pdf URL extension. Set to 0 to skip PDFs entirely.
CRAWL_PDFS = _get("CRAWL_PDFS", "1") == "1"
CRAWL_PDF_MAX_MB = int(_get("CRAWL_PDF_MAX_MB", "20"))  # skip PDFs larger than this
# Render pages with a headless browser (runs JavaScript) so dynamically
# generated / single-page-app content is captured. Needs the optional
# Playwright dependency. Slower per page, but crawling only happens at ingest.
CRAWL_RENDER = _get("CRAWL_RENDER", "0") == "1"
# Strip lines repeated across many crawled pages (cookie banners, nav menus,
# footers) before chunking/embedding — see ingest.strip_boilerplate(). A line
# is boilerplate when it appears on >= BOILERPLATE_MIN_PAGES pages AND on
# >= BOILERPLATE_PAGE_FRACTION of all pages.
BOILERPLATE_STRIP = _get("BOILERPLATE_STRIP", "1") == "1"
BOILERPLATE_MIN_PAGES = int(_get("BOILERPLATE_MIN_PAGES", "4"))
BOILERPLATE_PAGE_FRACTION = float(_get("BOILERPLATE_PAGE_FRACTION", "0.3"))
CRAWL_RENDER_WAIT_MS = int(_get("CRAWL_RENDER_WAIT_MS", "5000"))  # network-idle wait per page


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
