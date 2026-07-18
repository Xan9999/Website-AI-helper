#!/usr/bin/env bash
# Linux/macOS launcher for a real Qdrant server (lets `ingest` and `serve`
# run at the same time — the embedded local folder is single-process only).
# Configure via the project-root .env (KEY=value) or shell env vars:
#   QDRANT_BIN     = path to the qdrant binary (default: found on PATH)
#   QDRANT_STORAGE = data directory (default: ../../qdrant/storage)
# After this is running, set QDRANT_URL=http://127.0.0.1:6333 in .env.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_env.sh"

BIN="${QDRANT_BIN:-qdrant}"
if ! command -v "$BIN" >/dev/null 2>&1 && [ ! -x "$BIN" ]; then
    echo "Could not find Qdrant at '$BIN'. Download a release from" >&2
    echo "https://github.com/qdrant/qdrant/releases and set QDRANT_BIN in .env," >&2
    echo "or use Docker Compose instead (see README)." >&2
    exit 1
fi

STORAGE="${QDRANT_STORAGE:-../../qdrant/storage}"
mkdir -p "$STORAGE"

export QDRANT__STORAGE__STORAGE_PATH="$(cd "$STORAGE" && pwd)"
export QDRANT__TELEMETRY_DISABLED=true

exec "$BIN"
