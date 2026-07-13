"""Command-line interface: `website-ai-helper <ingest|serve|init>`.

Designed so ONE install serves MANY websites — give each site its own
collection with --collection and point the widget at the right server.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

_ENV_TEMPLATE = """\
# Website-AI-helper configuration. All values are optional (sane defaults shown).

# Chat + embedding endpoints (any OpenAI-compatible server: llama.cpp, Ollama, ...)
LLM_BASE_URL=http://127.0.0.1:8080/v1
EMBED_BASE_URL=http://127.0.0.1:8081/v1
EMBED_DIM=768
# nomic-embed prefixes (set both to "" for a bge model)
EMBED_DOC_PREFIX="search_document: "
EMBED_QUERY_PREFIX="search_query: "

# Vector store: empty QDRANT_URL = embedded local folder; else a Qdrant server URL
QDRANT_URL=
QDRANT_COLLECTION=default

# Identity + retrieval tuning
SITE_NAME=this website
TOP_K=3
CHUNK_SIZE=800
CRAWL_MAX_PAGES=50
"""


def _cmd_init(_args: argparse.Namespace) -> None:
    path = Path(".env")
    if path.exists():
        print(".env already exists — not overwriting.")
        return
    path.write_text(_ENV_TEMPLATE, encoding="utf-8")
    print(f"Wrote {path.resolve()}. Edit it, then run `website-ai-helper ingest <url>`.")


def _cmd_ingest(args: argparse.Namespace) -> None:
    if args.collection:
        os.environ["QDRANT_COLLECTION"] = args.collection
    if args.max_pages is not None:
        os.environ["CRAWL_MAX_PAGES"] = str(args.max_pages)
    if args.all_domains:
        os.environ["CRAWL_SAME_DOMAIN"] = "0"
    if args.render:
        os.environ["CRAWL_RENDER"] = "1"
    if args.site_name:
        os.environ["SITE_NAME"] = args.site_name
    # Import AFTER setting env so config picks up the overrides.
    from website_ai_helper.ingest import crawl_and_ingest
    crawl_and_ingest(args.url)


def _cmd_serve(args: argparse.Namespace) -> None:
    if args.collection:
        os.environ["QDRANT_COLLECTION"] = args.collection
    if args.site_name:
        os.environ["SITE_NAME"] = args.site_name
    import uvicorn
    uvicorn.run("website_ai_helper.main:app", host=args.host, port=args.port)


def main() -> None:
    p = argparse.ArgumentParser(
        prog="website-ai-helper",
        description="Local RAG chatbot for any website + your database.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest", help="Crawl a website and embed it into a collection.")
    pi.add_argument("url", help="Start URL, e.g. https://example.com")
    pi.add_argument("--collection", help="Knowledge-base name (one per site).")
    pi.add_argument("--max-pages", type=int, help="Max pages to crawl.")
    pi.add_argument("--all-domains", action="store_true", help="Follow links off the start domain.")
    pi.add_argument("--render", action="store_true",
                    help="Render pages with a headless browser (runs JavaScript) to "
                         "capture dynamic/SPA content. Needs the [render] extra.")
    pi.add_argument("--site-name", help="Human name of the site (used in answers).")
    pi.set_defaults(func=_cmd_ingest)

    ps = sub.add_parser("serve", help="Run the chatbot backend + widget.")
    ps.add_argument("--collection", help="Which knowledge base to answer from.")
    ps.add_argument("--site-name", help="Human name of the site (used in answers).")
    ps.add_argument("--host", default="127.0.0.1")
    ps.add_argument("--port", type=int, default=8000)
    ps.set_defaults(func=_cmd_serve)

    pn = sub.add_parser("init", help="Write a starter .env in the current folder.")
    pn.set_defaults(func=_cmd_init)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
