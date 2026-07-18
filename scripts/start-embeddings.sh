#!/usr/bin/env bash
# Linux/macOS launcher for the llama.cpp EMBEDDING server on :8081.
# Configure via the project-root .env (KEY=value) or shell env vars:
#   LLAMA_SERVER     = path to llama-server (default: found on PATH)
#   EMBED_MODEL_PATH = path to the embedding .gguf (e.g. bge-m3)
#   EMBED_NGL        = GPU layers (default 99; set 0 to keep the GPU free for
#                      the chat model on VRAM-constrained machines)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

SERVER="${LLAMA_SERVER:-llama-server}"
if ! command -v "$SERVER" >/dev/null 2>&1 && [ ! -x "$SERVER" ]; then
    echo "Could not find '$SERVER'. Set LLAMA_SERVER in .env to the llama-server binary." >&2
    exit 1
fi

MODEL="${EMBED_MODEL_PATH:-../models/embed.gguf}"
if [ ! -f "$MODEL" ]; then
    echo "Embedding model not found at '$MODEL'. Set EMBED_MODEL_PATH in .env." >&2
    exit 1
fi

exec "$SERVER" -m "$MODEL" --embedding --pooling mean -ngl "${EMBED_NGL:-99}" \
    -c 2048 -b 2048 -ub 2048 --host 127.0.0.1 --port 8081 --alias local-embed
