"""Ingestion: crawl a website, chunk the text, embed it, store it in Qdrant.

Programmatic entry point is `crawl_and_ingest(url)`. The CLI (`website-ai-helper
ingest <url>`) calls it. To also ingest free text from another database, shape
rows as {"text","url","title"} and pass them to `ingest_pages(...)`.
"""
from __future__ import annotations

import time
from collections import deque
from contextlib import contextmanager
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from website_ai_helper import config, vectorstore
from website_ai_helper.llm import embed_texts

_HEADERS = {"User-Agent": "website-ai-helper-ingest/1.0"}


def _extract_text_title(soup: BeautifulSoup) -> tuple[str, str]:
    """Strip noise tags and pull (visible_text, title) out of an already-parsed
    soup. Mutates `soup` in place (decomposes tags) — call this AFTER anything
    else that needs the original tree, e.g. link discovery."""
    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg", "form"]):
        tag.decompose()
    lines = [ln.strip() for ln in soup.get_text(separator="\n").splitlines()]
    return "\n".join(ln for ln in lines if ln), title


def clean_html(html: str) -> tuple[str, str]:
    """Parse raw HTML and return (visible_text, title)."""
    return _extract_text_title(BeautifulSoup(html, "html.parser"))


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    chunks, i, n = [], 0, len(text)
    step = max(1, size - overlap)
    while i < n:
        piece = text[i:i + size].strip()
        if piece:
            chunks.append(piece)
        i += step
    return chunks


@contextmanager
def _static_fetcher():
    """Yield a fetch(url)->html function backed by ONE reused HTTP connection
    (requests.Session), rather than opening a fresh TCP+TLS connection for
    every page — roughly 2x faster per page after the first on real sites."""
    with requests.Session() as session:
        session.headers.update(_HEADERS)

        def fetch(url: str) -> str | None:
            try:
                resp = session.get(url, timeout=15)
            except requests.RequestException as exc:
                print(f"  skip {url}: {exc}")
                return None
            if "text/html" not in resp.headers.get("content-type", ""):
                return None
            return resp.text

        yield fetch


@contextmanager
def _rendered_fetcher():
    """Yield a fetch(url)->html function backed by a headless Chromium browser.

    Runs each page's JavaScript and waits for it to settle, so client-rendered
    (single-page-app) content and JS-built links are captured. Requires the
    optional Playwright dependency:
        pip install "website-ai-helper[render]"
        playwright install chromium
    """
    try:
        # Optional dependency (the [render] extra); guarded so a plain install works.
        from playwright.sync_api import (  # pyright: ignore[reportMissingImports]
            Error as PlaywrightError,
            TimeoutError as PlaywrightTimeout,
            sync_playwright,
        )
    except ImportError as exc:
        raise SystemExit(
            "Rendered crawling needs Playwright. Install it with:\n"
            '  pip install "website-ai-helper[render]"\n'
            "  playwright install chromium"
        ) from exc

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except PlaywrightError as exc:
            raise SystemExit(
                f"Could not launch Chromium: {exc}\n"
                "Did you run `playwright install chromium`?"
            ) from exc
        page = browser.new_page(user_agent=_HEADERS["User-Agent"])

        def fetch(url: str) -> str | None:
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if resp is not None:
                    ctype = (resp.headers or {}).get("content-type", "")
                    if ctype and "text/html" not in ctype:
                        return None
                # Let client-side rendering / XHR settle (best-effort).
                try:
                    page.wait_for_load_state("networkidle", timeout=config.CRAWL_RENDER_WAIT_MS)
                except PlaywrightTimeout:
                    pass
                return page.content()
            except PlaywrightTimeout:
                print(f"  skip {url}: render timeout")
                return None
            except PlaywrightError as exc:
                print(f"  skip {url}: {exc}")
                return None

        try:
            yield fetch
        finally:
            browser.close()


def _bfs_crawl(start_url: str, max_pages: int, same_domain: bool, fetch) -> list[dict]:
    """Breadth-first crawl using the given `fetch(url)->html|None` function."""
    seen: set[str] = set()
    queue: deque[str] = deque([start_url])
    domain = urlparse(start_url).netloc
    pages: list[dict] = []

    while queue and len(pages) < max_pages:
        url = urldefrag(queue.popleft())[0]
        if url in seen:
            continue
        seen.add(url)

        html = fetch(url)
        if not html:
            continue

        # Parse once. Discover links from the ORIGINAL tree first — nav/header/
        # footer often hold site navigation and _extract_text_title() strips
        # those tags out (it mutates `soup` in place).
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            nxt = urldefrag(urljoin(url, a["href"]))[0]
            if not nxt.startswith("http"):
                continue
            if same_domain and urlparse(nxt).netloc != domain:
                continue
            if nxt not in seen:
                queue.append(nxt)

        text, title = _extract_text_title(soup)
        if text:
            pages.append({"url": url, "title": title, "text": text})
            print(f"[{len(pages)}/{max_pages}] {url} ({len(text)} chars)")
        # time.sleep(0.1)  # be polite

    return pages


def crawl(start_url: str, max_pages: int, same_domain: bool, render: bool = False) -> list[dict]:
    """Breadth-first crawl within `max_pages`.

    render=False -> fast static HTTP GET (default).
    render=True  -> headless browser that executes JavaScript, capturing
                    dynamically generated pages and JS-built navigation links.
    """
    if render:
        with _rendered_fetcher() as fetch:
            return _bfs_crawl(start_url, max_pages, same_domain, fetch)
    with _static_fetcher() as fetch:
        return _bfs_crawl(start_url, max_pages, same_domain, fetch)


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


def crawl_and_ingest(url: str, render: bool | None = None) -> int:
    render = config.CRAWL_RENDER if render is None else render
    config.ensure_data_dir()

    # Fail fast on a locked/unavailable vector store BEFORE crawling — a long
    # crawl finishing only to fail at the last step (storing) wastes real time.
    vectorstore.get_client()

    mode = "rendered/JS" if render else "static"
    print(f"Crawling {url} (max {config.CRAWL_MAX_PAGES} pages, {mode}) "
          f"into collection '{config.QDRANT_COLLECTION}'...")
    pages = crawl(url, config.CRAWL_MAX_PAGES, config.CRAWL_SAME_DOMAIN, render=render)
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
