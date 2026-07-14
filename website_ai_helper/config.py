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
SITE_NAME = _get("SITE_NAME", "this website")

# --- Crawler ---
CRAWL_MAX_PAGES = int(_get("CRAWL_MAX_PAGES", "50"))
CRAWL_SAME_DOMAIN = _get("CRAWL_SAME_DOMAIN", "1") == "1"
# Render pages with a headless browser (runs JavaScript) so dynamically
# generated / single-page-app content is captured. Needs the optional
# Playwright dependency. Slower per page, but crawling only happens at ingest.
CRAWL_RENDER = _get("CRAWL_RENDER", "0") == "1"
CRAWL_RENDER_WAIT_MS = int(_get("CRAWL_RENDER_WAIT_MS", "5000"))  # network-idle wait per page


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
