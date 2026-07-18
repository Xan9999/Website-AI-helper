#!/usr/bin/env bash
# Linux/macOS launcher for the llama.cpp CHAT server on :8080.
# Configure via the project-root .env (KEY=value) or shell env vars:
#   LLAMA_SERVER = path to llama-server (default: found on PATH)
#   CHAT_MODEL   = path to the chat .gguf
#   LLM_CTX      = total context size (default 16384; split across slots by
#                  -np — lower it if the model + KV cache overflows your VRAM)
#   CPU_MOE=1    = keep MoE expert weights in RAM (only for MoE models)
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

SERVER="${LLAMA_SERVER:-llama-server}"
if ! command -v "$SERVER" >/dev/null 2>&1 && [ ! -x "$SERVER" ]; then
    echo "Could not find '$SERVER'. Set LLAMA_SERVER in .env to the llama-server binary." >&2
    echo "Build it from https://github.com/ggml-org/llama.cpp (e.g. cmake -DGGML_CUDA=ON) or use Docker Compose instead (see README)." >&2
    exit 1
fi

MODEL="${CHAT_MODEL:-../models/chat.gguf}"
if [ ! -f "$MODEL" ]; then
    echo "Chat model not found at '$MODEL'. Set CHAT_MODEL in .env." >&2
    exit 1
fi

MOE_ARGS=()
[ "${CPU_MOE:-0}" = "1" ] && MOE_ARGS=(--cpu-moe)

# -np 2 = two chats in parallel; -c is TOTAL context split across slots.
# --cache-reuse keeps KV-cache for prompt parts matching a previous request
# (big prefill savings on follow-ups retrieving the same website chunks).
exec "$SERVER" -m "$MODEL" -np "${LLM_SLOTS:-2}" -ngl 99 -c "${LLM_CTX:-16384}" --cache-reuse 256 \
    --jinja --host 127.0.0.1 --port 8080 --alias local-chat "${MOE_ARGS[@]}"
