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
two servers (chat on :8080, embeddings on :8081) — see `scripts/`.

**Model files are not stored inside this project.** This app only speaks HTTP
to whatever server you run — it's engine-agnostic — so `.gguf` weights belong
in a shared folder alongside your local-LLM tooling, not bundled into this
package. A sibling folder works well:

```
Ollama CPP LLM\
├── llama.cpp\           (the inference engine)
├── models\              (shared .gguf weights — put them here)
└── Website-AI-helper\   (this project, model-agnostic)
```

```powershell
$env:LLAMA_SERVER="C:\path\to\llama-server.exe"; $env:CHAT_MODEL="..\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf"
.\scripts\start-llm.ps1
$env:EMBED_MODEL_PATH="..\models\nomic-embed-text-v1.5.Q8_0.gguf"
.\scripts\start-embeddings.ps1
```

Chat model should be instruct + tool-capable (e.g. Qwen2.5-Instruct) and started
with `--jinja`. Embedding `EMBED_DIM` in `.env` must match the model (nomic /
bge-base = 768).

### GPU acceleration with Vulkan (optional)

**Vulkan is not part of this package.** Website-AI-helper only talks HTTP to an
OpenAI-compatible server and is agnostic to how that server computes. GPU
acceleration is a property of the **llama.cpp backend** you run behind it — so
"pairing" is nothing more than: run a Vulkan-enabled `llama-server` with `-ngl`,
then point `.env` at it (exactly as above). No app code or dependency changes.

Vulkan is a good cross-vendor choice (NVIDIA / AMD / Intel) and needs no
CUDA or ROCm toolkit.

**1. Runtime prerequisite** — a GPU driver that ships the Vulkan runtime (the
loader `vulkan-1.dll` on Windows, `libvulkan.so.1` on Linux). This is included
with modern GPU drivers; you do **not** need the Vulkan SDK just to run.
Verify:

```bash
vulkaninfo --summary     # lists your GPU as a Vulkan device (if installed)
nvidia-smi               # NVIDIA: confirms the driver is present
```

**2. Get a Vulkan-enabled llama.cpp** — either:

- **Prebuilt (easiest):** download the `*-vulkan-*` asset from a
  [llama.cpp release](https://github.com/ggml-org/llama.cpp/releases). Needs only
  the driver's Vulkan runtime — no SDK.
- **Build from source:** install the
  [Vulkan SDK](https://vulkan.lunarg.com/sdk/home) (provides headers + the
  `glslc` shader compiler), then:
  ```bash
  cmake -B build -DGGML_VULKAN=ON
  cmake --build build --config Release
  ```
  (On a Windows **MinGW** toolchain also add `-DGGML_OPENMP=OFF` and define
  `_WIN32_WINNT=0x0A00`; not needed with MSVC or on Linux.)

**3. Start the servers with GPU offload** — add `-ngl 99` (offload all layers);
`scripts/start-llm.ps1` / `scripts/start-embeddings.ps1` already do this.

**4. Confirm it's actually on the GPU** — the server log prints e.g.
`ggml_vulkan: Found 1 Vulkan devices: ... NVIDIA GeForce GTX 1080 Ti` and
`load_tensors: offloaded 29/29 layers to GPU`, and `nvidia-smi` shows
`llama-server` using VRAM. That's it — `.env` already points the app at these
servers, so it uses the accelerated backend with no further change.

### Crawling JavaScript / single-page-app sites

By default the crawler does a plain HTTP GET — fast, but it only sees
server-rendered HTML. For sites whose content (or navigation) is built by
JavaScript in the browser, use `--render`, which drives a headless Chromium
that executes the page's JS before extracting text:

```bash
pip install "website-ai-helper[render]"   # one-time
playwright install chromium               # one-time (downloads the browser)

website-ai-helper ingest https://my-spa.com --collection myspa --render
```

Rendering is slower per page, but crawling only happens at ingest time, so it
doesn't affect answer latency. Tune the per-page settle time with
`CRAWL_RENDER_WAIT_MS` (default 5000). If a page still comes back empty, its
content likely loads on scroll/interaction, which this mode doesn't trigger.

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
| `CRAWL_RENDER`, `CRAWL_RENDER_WAIT_MS` | Render JS with a headless browser (`--render`) and settle time |

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
