# Website-AI-helper

A portable, **fully local** RAG chatbot you can drop onto **any website**. It
answers using **hybrid retrieval**:

- **Vector RAG** over the site's crawled content + your documents
- **Live database** lookups via safe, read-only tools (price, stock, orders…)
- **Current-page context** passed live from the chat widget

It talks to any **OpenAI-compatible** LLM + embedding server, so it runs on
[llama.cpp](https://github.com/ggml-org/llama.cpp), Ollama, or a remote API —
your data and models never have to leave your machine.

## Why it's reusable

One install can serve **many sites**: give each website its own **collection**.

```bash
website-ai-helper ingest https://acme.com   --collection acme
website-ai-helper ingest https://globex.com --collection globex

website-ai-helper serve --collection acme   --port 8000
website-ai-helper serve --collection globex --port 8001
```

## Install

Requires Python 3.11+ and an OpenAI-compatible chat + embedding endpoint.

```bash
# clone, then:
./setup.sh          # macOS/Linux
# or on Windows:
.\setup.ps1
```

That creates a virtualenv and installs the `website-ai-helper` command. (Under
the hood it's just `pip install -e .` — you can also `pipx install .` for a
global command.)

## Quickstart

```bash
website-ai-helper init                                   # writes a starter .env
website-ai-helper ingest https://example.com --collection demo
website-ai-helper serve --collection demo
# open http://127.0.0.1:8000  and click the chat button
```

### Bring your own models (llama.cpp example)

Any OpenAI-compatible server works; point `.env` at it. For llama.cpp, start
two servers (chat on :8080, embeddings on :8081) — see `scripts/`:

```powershell
$env:LLAMA_SERVER="C:\path\to\llama-server.exe"; $env:CHAT_MODEL="models\qwen2.5-7b-instruct-q4_k_m.gguf"
.\scripts\start-llm.ps1
$env:EMBED_MODEL_PATH="models\nomic-embed-text-v1.5.q8_0.gguf"
.\scripts\start-embeddings.ps1
```

Chat model should be instruct + tool-capable (e.g. Qwen2.5-Instruct) and started
with `--jinja`. Embedding `EMBED_DIM` in `.env` must match the model (nomic /
bge-base = 768).

## Configuration

All via `.env` or CLI flags (see `.env.example`). Common knobs:

| Var | Meaning |
|---|---|
| `LLM_BASE_URL` / `EMBED_BASE_URL` | Your chat / embedding endpoints |
| `EMBED_DIM` | Embedding dimensionality (must match the model) |
| `QDRANT_URL` | Empty = embedded local folder; else a Qdrant server |
| `QDRANT_COLLECTION` | Knowledge base name — **one per site** |
| `TOP_K`, `CHUNK_SIZE` | Retrieval tuning |
| `CRAWL_MAX_PAGES`, `CRAWL_SAME_DOMAIN` | Crawl scope |

## Embedding the widget on your site

Serve the backend somewhere your site can reach, copy the markup + `<script>`
from `website_ai_helper/web/widget.html` onto your pages, and set
`const BACKEND = "https://your-backend"`. The widget sends the visitor's current
URL, title, and page text as context. **Restrict CORS** (in `main.py`) to your
domain before production.

## Connecting your real database

Everything DB-specific lives in `website_ai_helper/structured.py`:

1. Replace `_conn()` / `init_demo_db()` with your database (use a **read-only**
   user — Postgres, MySQL, SQLite, …).
2. Rewrite the tool functions (`search_products`, `get_order_status`) as
   parameterized queries for your tables, and update the `TOOLS` schemas.

The model calls these tools rather than writing SQL, which keeps it safe and
reliable. For the *unstructured* half of another database (free text), embed it
alongside the website with `ingest_pages([...])`.

## How it works

```
ingest  ─crawl→ chunk → embed →  Qdrant (per-site collection)
                                      ▲ retrieve
browser widget ─POST /chat→ FastAPI ──┤
 (msg + page)                         ▼ tool calls (price/stock/orders)
                    chat LLM  ◄──►  your database (read-only tools)
```

The model answers from retrieved content, calls DB tools for live facts, and
streams the grounded answer back — following a strict source-precedence rule
(tool results > current page > website content).

## Notes / limitations

- **Embedded Qdrant is single-writer**: ingest with the server stopped, or run a
  Qdrant server (`docker run -p 6333:6333 qdrant/qdrant`, set `QDRANT_URL`) to do
  both at once.
- Grounding quality depends on the chat model; a 7B-class instruct model is a
  good baseline. Small models may under-call tools.
- Re-ingest after changing `EMBED_DIM`/`CHUNK_SIZE` (vector dimensions must match).

## License

MIT — see [LICENSE](LICENSE).
