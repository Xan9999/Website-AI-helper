# Starts a real Qdrant server (not the embedded/local mode) so `ingest` and
# `serve` can run at the same time — the embedded local folder only allows
# ONE process to open it at all, which fails (or worse, silently corrupts
# data if something races) whenever ingest and serve overlap.
#
# Configure via .env / shell env vars:
#   QDRANT_BIN     = full path to qdrant.exe (default: ..\..\qdrant\qdrant.exe,
#                    a sibling of this project — see README)
#   QDRANT_STORAGE = where Qdrant persists its data (default: ..\..\qdrant\storage)
#
# After this is running, set QDRANT_URL=http://127.0.0.1:6333 in .env.
$ErrorActionPreference = "Stop"

# Pull QDRANT_BIN / QDRANT_STORAGE from .env if not already set in shell.
. "$PSScriptRoot\_env.ps1"

$bin = if ($env:QDRANT_BIN) { $env:QDRANT_BIN } else { "..\..\qdrant\qdrant.exe" }
if (-not (Test-Path $bin)) {
    Write-Error (
        "Could not find Qdrant at '$bin'.`n" +
        "Download the Windows release from https://github.com/qdrant/qdrant/releases " +
        "(qdrant-x86_64-pc-windows-msvc.zip), extract it, then set:`n" +
        '  $env:QDRANT_BIN = "C:\path\to\qdrant.exe"'
    )
    exit 1
}

$storage = if ($env:QDRANT_STORAGE) { $env:QDRANT_STORAGE } else { "..\..\qdrant\storage" }
New-Item -ItemType Directory -Force -Path $storage | Out-Null

$env:QDRANT__STORAGE__STORAGE_PATH = (Resolve-Path $storage).Path
$env:QDRANT__TELEMETRY_DISABLED = "true"

& $bin
