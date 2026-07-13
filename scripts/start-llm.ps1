# Convenience launcher for a llama.cpp CHAT server (OpenAI-compatible) on :8080.
# Not required — you can use any OpenAI-compatible endpoint (Ollama, a remote
# server, etc.). Set these env vars or edit the defaults.
#   $env:LLAMA_SERVER  = full path to llama-server(.exe)
#   $env:CHAT_MODEL    = path to a .gguf chat model (instruct, tool-capable)
#
# Models are NOT stored inside this project — this app is engine-agnostic and
# only talks HTTP to whatever server you point it at. Keep .gguf files in a
# shared folder alongside your local-LLM tooling, e.g. "..\models\" (a sibling
# of this project), and pass the path via $env:CHAT_MODEL below.
$ErrorActionPreference = "Stop"

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

$model = if ($env:CHAT_MODEL) { $env:CHAT_MODEL } else { "..\models\chat.gguf" }
if (-not (Test-Path $model)) {
    Write-Error (
        "Chat model not found at '$model'.`n" +
        "Set it explicitly, e.g.:`n" +
        '  $env:CHAT_MODEL = "..\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf"'
    )
    exit 1
}

& $server -m "$model" -ngl 99 -c 8192 --jinja --host 127.0.0.1 --port 8080 --alias local-chat
