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

Any OpenAI-compatible server works; point `.env` at it. `llama.cpp` is a
separate project (not bundled with this package) that provides `llama-server`
— a binary that loads a `.gguf` model and exposes it over an OpenAI-compatible
API + web UI.

**Getting `llama-server`:**
- **Prebuilt (easiest):** download the asset matching your OS/GPU from a
  [llama.cpp release](https://github.com/ggml-org/llama.cpp/releases) — plain
  CPU build, or `*-vulkan-*` / `*-cuda-*` for GPU (see the Vulkan section below
  for GPU setup specifics). Extract and run — no install step.
- **Build from source:** clone
  [ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) and follow its
  build docs (`cmake -B build && cmake --build build --config Release`).

Either way you get `llama-server(.exe)` — point `$env:LLAMA_SERVER` at wherever
you put it, start two instances (chat on :8080, embeddings on :8081) — see
`scripts/`.

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
$env:EMBED_MODEL_PATH="..\models\bge-m3-Q8_0.gguf"
.\scripts\start-embeddings.ps1
```

Chat model should be instruct + tool-capable and started with `--jinja`.
Embedding `EMBED_DIM` in `.env` must match the model (`bge-m3` = 1024,
`nomic-embed-text` = 768).

**Current default chat model: `Qwen3-14B-Instruct` (Q4_K_M, ~9GB).**
Dense, tool-capable, and gives noticeably more thorough/structured answers
than the 7B — but it only just fits an 11GB card (~10.8GB used with the
embedding server also running, so no headroom for a second chat model
alongside it). Measured on a GTX 1080 Ti: ~27 tok/s generation, ~2.9s
time-to-first-token (streaming, so close to the 7B's perceived latency
despite the lower raw token rate).

Qwen3 ships with **hybrid thinking mode on by default** — without
`chat_template_kwargs: {"enable_thinking": false}` (already wired into
`agent.py`'s completion calls) it burns the whole token budget on hidden
`<think>...</think>` reasoning instead of answering, the same failure mode
GPT-OSS hit below.

Previous default `Qwen2.5-7B-Instruct` (Q4_K_M, ~4.4GB) is still a good
choice if you want more headroom / faster responses over max answer quality
— ~60 tok/s / 0.3s-to-first-token, comfortably fits alongside the embedding
model with room to spare. Swap `CHAT_MODEL` in `.env` to switch back.

**Why not a bigger MoE model?** We benchmarked 20B+ Mixture-of-Experts
alternatives on the same card and none were viable for a live chatbot:
ERNIE-4.5-21B-A3B has no tool-calling in its chat template; GPT-OSS-20B
spends 90%+ of its tokens on hidden "reasoning" (~25s for a 5-word answer);
Qwen3-30B-A3B-Instruct managed only 1.8-3 tok/s with `--cpu-moe`/`-ncmoe`
expert offloading. The MoE "only 3B active" pitch doesn't help when the
inactive experts still live in slow CPU RAM — if the model doesn't fit
VRAM, a dense model that does fit is ~20x faster. `start-llm.ps1` still
supports MoE offload via `CPU_MOE=1` in `.env` for cards/models where the
math works out.

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

### Linked PDF files

The crawler also downloads PDF files linked from crawled pages (detected by
the `.pdf` URL extension; the same-domain rule applies) and ingests their
text alongside regular pages — price lists, brochures, and forms become
answerable. Each PDF counts toward `CRAWL_MAX_PAGES`. Limitations: scanned /
image-only PDFs are skipped (no OCR), as are PDFs served from URLs without a
`.pdf` extension. Set `CRAWL_PDFS=0` to disable, and `CRAWL_PDF_MAX_MB`
(default 20) to cap the download size per file.

### Vector store: run a real Qdrant server (recommended)

By default the vector store is an **embedded local folder** (`./data/qdrant`)
— zero setup, but it only allows **one process** to open it at a time. That
means `ingest` and `serve` can't run simultaneously, and starting one while
the other has it open fails outright (or, if a process dies mid-write,
worse). This gets painful fast once you're doing real ingests.

**Fix: run a real Qdrant server** — no Docker required, a small (~29 MB)
native binary:

```powershell
# One-time: download from https://github.com/qdrant/qdrant/releases
#   (qdrant-x86_64-pc-windows-msvc.zip) and extract to ..\qdrant\ (a sibling
#   of this project), or set QDRANT_BIN to wherever you put it.
.\scripts\start-qdrant.ps1
```

Then in `.env`:
```
QDRANT_URL=http://127.0.0.1:6333
```
Now `ingest` and `serve` can run at the same time, and one Qdrant instance
holds every site's collection.

### Re-ingesting a site (avoid duplicates)

Point IDs are random, so **ingesting the same site twice duplicates every
chunk** — the copies then crowd out other results in the retrieval top-K.
To refresh a site's content, delete its collection first, then ingest:

```powershell
# NOTE: in PowerShell `curl` aliases Invoke-WebRequest — use curl.exe,
# or natively: Invoke-RestMethod -Method Delete http://127.0.0.1:6333/collections/adr
curl.exe -X DELETE http://127.0.0.1:6333/collections/adr

website-ai-helper ingest https://adrlandia.com --collection adr
```

The collection is recreated automatically at ingest. Heads-up: the collection
is empty while the re-crawl runs, so a live chatbot on it answers without
website context for those few minutes.

**Migrating existing data** from the embedded folder to a server: open both
with `qdrant_client` (`QdrantClient(path="data/qdrant")` and
`QdrantClient(url="http://127.0.0.1:6333")`), then for each collection,
recreate it on the server with the same `VectorParams` and copy points across
with `scroll(..., with_vectors=True)` → `upsert(...)` (convert each `Record`
to a `PointStruct` first). Stop anything using the embedded folder first.

## Configuration

All via `.env` or CLI flags (see `.env.example`). Common knobs:

| Var | Meaning |
|---|---|
| `LLM_BASE_URL` / `EMBED_BASE_URL` | Your chat / embedding endpoints |
| `EMBED_DIM` | Embedding dimensionality (must match the model) |
| `QDRANT_URL` | Empty = embedded local folder (single-writer); set to a Qdrant server URL to allow concurrent ingest+serve |
| `QDRANT_COLLECTION` | Knowledge base name — **one per site** |
| `TOP_K`, `CHUNK_SIZE` | Retrieval tuning |
| `FREQUENCY_PENALTY`, `PRESENCE_PENALTY`, `MAX_TOKENS` | Anti-repetition / runaway-generation guards |
| `CRAWL_MAX_PAGES`, `CRAWL_SAME_DOMAIN` | Crawl scope |
| `CRAWL_PDFS`, `CRAWL_PDF_MAX_MB` | Ingest linked PDF files (default on, 20 MB cap) |
| `CRAWL_RENDER`, `CRAWL_RENDER_WAIT_MS` | Render JS with a headless browser (`--render`) and settle time |
| `ALLOWED_ORIGINS` | Comma-separated origins allowed to call `/chat`; empty = allow any (dev only) |

## Embedding the widget on your site

Serve the backend somewhere your site can reach — over **HTTPS** with a real
certificate (e.g. Caddy/nginx reverse-proxying Uvicorn, or
`serve --ssl-certfile cert.pem --ssl-keyfile key.pem` / `SSL_CERTFILE`+
`SSL_KEYFILE` env vars to let Uvicorn terminate TLS itself), since a browser
will block `fetch()` from an `https://` page to a plain `http://` backend.
Then set `ALLOWED_ORIGINS=https://clientsite.com,https://www.clientsite.com`
in `.env` before going live (default is wide-open, fine for local testing
only).

> **Symptom decoder:** if the backend logs `WARNING: Invalid HTTP request
> received.` on every page load, the snippet says `https://` but the backend
> is speaking plain HTTP — the TLS handshake bytes are hitting Uvicorn as
> garbage. Terminate TLS (see above); note browsers reject self-signed certs
> and Let's Encrypt won't issue for a bare IP, so you need a (sub)domain
> pointed at the server, e.g. `chat.yourdomain.com`.

### HTTPS from a home/office PC: Cloudflare Tunnel

If the backend runs on your own machine (no public server, router/NAT in the
way), a **Cloudflare Tunnel** is the easiest way to get a real HTTPS URL: the
`cloudflared` agent opens an *outbound* connection to Cloudflare's edge,
Cloudflare terminates TLS with its own valid certificate, and relays requests
down the tunnel to `localhost:8000`. No domain DNS on the client's side, no
certificate to obtain, no router port-forwarding — and the widget-hosting
site does **not** need to be yours; the snippet can point at any HTTPS URL
(that's how all third-party widgets work).

**Quick tunnel — testing, zero setup, no account:**

```powershell
# one-time download (single ~50MB exe, no installer):
curl -L -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe

# run it (keep the window open — closing it kills the URL):
.\cloudflared.exe tunnel --url http://localhost:8000
```

It prints a random `https://<random-words>.trycloudflare.com` URL — use that
as the backend in the embed snippet. **Caveats:** the URL only lives while
the process runs, and a *new random URL* is issued on every restart (so the
snippet on the client site must be updated each time) — fine for demos,
wrong for production.

**Named tunnel — production, stable URL (`chat.yourdomain.com`):**

Needs a free Cloudflare account and a domain you own (~10€/yr — any
registrar). One-time setup:

1. **Put the domain on Cloudflare:** Cloudflare dashboard → "Add a site" →
   follow the prompt to switch your domain's nameservers at the registrar to
   the two Cloudflare gives you (takes minutes to a few hours to propagate).
2. **Authenticate the agent:** `.\cloudflared.exe tunnel login`
   (opens a browser, pick the domain).
3. **Create the tunnel:** `.\cloudflared.exe tunnel create wah-chat`
   — prints a tunnel UUID and writes a credentials JSON.
4. **Point a hostname at it:**
   `.\cloudflared.exe tunnel route dns wah-chat chat.yourdomain.com`
   (creates the DNS record on Cloudflare automatically).
5. **Config file** `%USERPROFILE%\.cloudflared\config.yml`:
   ```yaml
   tunnel: wah-chat
   credentials-file: C:\Users\<you>\.cloudflared\<tunnel-uuid>.json
   ingress:
     - hostname: chat.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   ```
6. **Run it — as a Windows service** so it survives reboots:
   `.\cloudflared.exe service install`, then start "Cloudflared" in
   services.msc (or `.\cloudflared.exe tunnel run wah-chat` to run manually).

The snippet then uses `https://chat.yourdomain.com/widget.js?...` forever —
one stable hostname serves every client site (each with its own
`client_id`), certificates renew themselves, and nothing on your machine is
directly exposed to inbound internet traffic. Remember to set
`ALLOWED_ORIGINS` once it's live.

### One-line async embed (recommended)

`GET /widget.js` serves a self-contained loader script — no markup to copy,
one snippet handles every client site:

```html
<script>
!function(d,u,i,l){
    var s=d.createElement("script");s.async=1;s.src=u+"?client_id="+i+"&language="+l;
    var h=d.getElementsByTagName("script")[0];h.parentNode.insertBefore(s,h);
}(document,"https://your-backend/widget.js","acme","en");
</script>
```

- `client_id` **is** the Qdrant collection name — the same one you passed to
  `--collection` at ingest time (`website-ai-helper ingest https://acme.com
  --collection acme`). One backend + one snippet template serves every client;
  swap the `client_id` per site. Leave it blank to fall back to this install's
  default `QDRANT_COLLECTION`.
- `language` only picks the widget's UI strings (button labels, placeholder —
  currently `en`/`it`/`sl`, defaulting to `en`); the assistant itself already
  answers in whatever language the visitor actually types.
- The script reads both params from its own `<script src>` at load time via
  `document.currentScript`, builds the whole widget via DOM APIs, and POSTs
  `client_id` on every `/chat` call — nothing else to configure per site.

The widget sends the visitor's current URL, title, and page text as context —
this works unmodified on any page it's embedded in, including a WordPress site.

**On WordPress:** there's no code to write on the WP side beyond pasting the
snippet once. Add it sitewide via:
- A "header/footer" plugin (e.g. WPCode, "Insert Headers and Footers") — paste
  the snippet into the footer, applies to every page.
- Your (child) theme's `footer.php`, right before `</body>`, if you're
  comfortable editing theme files — survives non-child-theme updates only if
  it's a child theme.

Avoid page builders' "custom HTML" blocks for a *sitewide* widget — those only
apply per-page, so you'd have to repeat it everywhere.

### Manual embed (alternative)

Copy the markup + `<script>` from `website_ai_helper/web/widget.html` directly
onto your pages instead, and set `const BACKEND = "https://your-backend"`.
Useful if you want to customize the markup/CSS per site rather than share one
script across clients. This path doesn't support `client_id` — it always talks
to the install's default collection.

**Known limitation:** `client_id` only routes vector retrieval to the matching
collection; the structured-DB tools (`structured.py`) still hit one shared
demo SQLite regardless of `client_id`. Multi-tenant structured data needs
per-client DB wiring, not yet implemented.

## Conversation logging & QA review

Every chat turn is logged automatically to a SQLite database
(`data/conversations.db`): the client's message, the agent's full reply,
per-reply latency, and conversation metadata (site/collection, the page the
visitor was on, timestamps). Conversation duration = first to last message;
the widget groups turns with a per-session conversation id.

To review transcripts, set a secret in `.env`:

```
QA_TOKEN=some-long-random-string
```

then open the **private QA site**:

- `/qa?token=<QA_TOKEN>` — all conversations: start time, site, message
  count, duration, first message, error flags
- click **view** for the human-readable transcript (`Client:` / `Agent:`
  with per-reply latency), or **txt** to download it as plain text

With `QA_TOKEN` empty the `/qa` routes are disabled (logging still happens).
The transcripts contain whatever visitors type — treat the token like a
password and use HTTPS if the backend is reachable from outside.

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

- **Embedded Qdrant (the default) is single-writer**: `ingest` and `serve` can't
  run at the same time, and a long ingest that hits this fails only at the very
  last step (after crawling everything) — see "Vector store" above for the fix
  (a real Qdrant server, no Docker needed).
- Grounding quality depends on the chat model; a 7B-class instruct model is a
  good baseline. Small models may under-call tools.
- Re-ingest after changing `EMBED_DIM`/`CHUNK_SIZE` (vector dimensions must match).
- Use a genuinely multilingual embedding model (e.g. `bge-m3`) for non-English
  sites — English-centric models like `nomic-embed-text` retrieve poorly outside
  English, independent of how well the chat model itself handles the language.
- **Small local chat models can occasionally degenerate** — repeating a
  sentence, sometimes drifting into another language mid-repeat — especially
  on vague queries with weak/ambiguous retrieval matches. `FREQUENCY_PENALTY`
  / `PRESENCE_PENALTY` (default 0.4) and `MAX_TOKENS` (default 500) reduce and
  bound this; a larger/stronger chat model is the more thorough fix.

## License

MIT — see [LICENSE](LICENSE).
