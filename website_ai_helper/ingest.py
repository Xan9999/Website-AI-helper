"""Ingestion: crawl a website, chunk the text, embed it, store it in Qdrant.

Programmatic entry point is `crawl_and_ingest(url)`. The CLI (`website-ai-helper
ingest <url>`) calls it. To also ingest free text from another database, shape
rows as {"text","url","title"} and pass them to `ingest_pages(...)`.
"""
from __future__ import annotations

import time
from collections import deque
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from website_ai_helper import config, vectorstore
from website_ai_helper.llm import embed_texts

_HEADERS = {"User-Agent": "website-ai-helper-ingest/1.0"}


def clean_html(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines()]
    return "\n".join(ln for ln in lines if ln), title


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    chunks, i, n = [], 0, len(text)
    step = max(1, size - overlap)
    while i < n:
        piece = text[i:i + size].strip()
        if piece:
            chunks.append(piece)
        i += step
    return chunks


def crawl(start_url: str, max_pages: int, same_domain: bool) -> list[dict]:
    seen: set[str] = set()
    queue: deque[str] = deque([start_url])
    domain = urlparse(start_url).netloc
    pages: list[dict] = []

    while queue and len(pages) < max_pages:
        url = urldefrag(queue.popleft())[0]
        if url in seen:
            continue
        seen.add(url)
        try:
            resp = requests.get(url, timeout=15, headers=_HEADERS)
            if "text/html" not in resp.headers.get("content-type", ""):
                continue
        except requests.RequestException as exc:
            print(f"  skip {url}: {exc}")
            continue

        text, title = clean_html(resp.text)
        if text:
            pages.append({"url": url, "title": title, "text": text})
            print(f"[{len(pages)}/{max_pages}] {url} ({len(text)} chars)")

        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.find_all("a", href=True):
            nxt = urldefrag(urljoin(url, a["href"]))[0]
            if not nxt.startswith("http"):
                continue
            if same_domain and urlparse(nxt).netloc != domain:
                continue
            if nxt not in seen:
                queue.append(nxt)
        time.sleep(0.2)  # be polite

    return pages


def ingest_pages(pages: list[dict], batch_size: int = 32) -> int:
    client = vectorstore.get_client()
    vectorstore.ensure_collection(client)

    texts: list[str] = []
    payloads: list[dict] = []
    total = 0

    def flush() -> None:
        nonlocal total, texts, payloads
        if not texts:
            return
        vectors = embed_texts(texts, kind="document")
        vectorstore.upsert(client, vectors, payloads)
        total += len(texts)
        print(f"  ...stored {total} chunks")
        texts, payloads = [], []

    for pg in pages:
        for chunk in chunk_text(pg["text"], config.CHUNK_SIZE, config.CHUNK_OVERLAP):
            texts.append(chunk)
            payloads.append({"text": chunk, "url": pg.get("url", ""), "title": pg.get("title", "")})
            if len(texts) >= batch_size:
                flush()
    flush()
    return total


def crawl_and_ingest(url: str) -> int:
    config.ensure_data_dir()
    print(f"Crawling {url} (max {config.CRAWL_MAX_PAGES} pages) "
          f"into collection '{config.QDRANT_COLLECTION}'...")
    pages = crawl(url, config.CRAWL_MAX_PAGES, config.CRAWL_SAME_DOMAIN)
    print(f"Crawled {len(pages)} pages. Embedding + storing...")
    total = ingest_pages(pages)
    print(f"Done. Ingested {total} chunks into '{config.QDRANT_COLLECTION}'.")
    return total


def main() -> None:
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m website_ai_helper.ingest <start_url>")
        raise SystemExit(1)
    crawl_and_ingest(sys.argv[1])


if __name__ == "__main__":
    main()
