# Convenience launcher for a llama.cpp EMBEDDING server (OpenAI-compatible) on :8081.
# Configure via the project-root .env file (KEY=value):
#   LLAMA_SERVER     = full path to llama-server(.exe)
#   EMBED_MODEL_PATH = path to a .gguf embedding model (e.g. nomic-embed-text)
# ...or set the same names as shell env vars, which take precedence over .env.
#
# Models are NOT stored inside this project — keep .gguf files in a shared
# folder alongside your local-LLM tooling, e.g. "..\models\" (a sibling of
# this project).
$ErrorActionPreference = "Stop"

# Pull LLAMA_SERVER / EMBED_MODEL_PATH (etc.) from .env if not already set.
. "$PSScriptRoot\_env.ps1"

# Resolve the server binary: explicit $env:LLAMA_SERVER first, else whatever
# "llama-server" finds on PATH (works only if you've added it there yourself).
$server = if ($env:LLAMA_SERVER) { $env:LLAMA_SERVER } else { "llama-server" }
if (-not (Get-Command $server -ErrorAction SilentlyContinue)) {
    Write-Error (
        "Could not find '$server'. This project does not bundle llama-server " +
        "and nothing puts it on PATH automatically.`n" +
        "Set it explicitly, e.g.:`n" +
        '  $env:LLAMA_SERVER = "C:\path\to\llama-server.exe"'
    )
    exit 1
}

$model = if ($env:EMBED_MODEL_PATH) { $env:EMBED_MODEL_PATH } else { "..\models\embed.gguf" }
if (-not (Test-Path $model)) {
    Write-Error (
        "Embedding model not found at '$model'.`n" +
        "Set it explicitly, e.g.:`n" +
        '  $env:EMBED_MODEL_PATH = "..\models\nomic-embed-text-v1.5.Q8_0.gguf"'
    )
    exit 1
}

& $server -m "$model" --embedding --pooling mean -ngl 99 `
  -c 2048 -b 2048 -ub 2048 --host 127.0.0.1 --port 8081 --alias local-embed
