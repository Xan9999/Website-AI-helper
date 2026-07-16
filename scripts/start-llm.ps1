# Convenience launcher for a llama.cpp CHAT server (OpenAI-compatible) on :8080.
# Not required — you can use any OpenAI-compatible endpoint (Ollama, a remote
# server, etc.). Configure via the project-root .env file (KEY=value):
#   LLAMA_SERVER   = full path to llama-server(.exe)
#   CHAT_MODEL     = path to a .gguf chat model (instruct, tool-capable)
#   CPU_MOE        = "1" to keep Mixture-of-Experts weights on CPU/RAM instead
#                    of VRAM — lets a big MoE model run on a GPU with less VRAM
#                    than the full model size. Default "0": measured on a GTX
#                    1080 Ti, CPU-offloaded 20B+ MoE models ran 8-20x slower
#                    than a dense 7B fully on GPU, so prefer a dense model
#                    that fits your VRAM.
# ...or set the same names as shell env vars, which take precedence over .env.
#
# Models are NOT stored inside this project — this app is engine-agnostic and
# only talks HTTP to whatever server you point it at. Keep .gguf files in a
# shared folder alongside your local-LLM tooling, e.g. "..\models\" (a sibling
# of this project).
$ErrorActionPreference = "Stop"

# Pull LLAMA_SERVER / CHAT_MODEL (etc.) from .env if not already set in shell.
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

$model = if ($env:CHAT_MODEL) { $env:CHAT_MODEL } else { "..\models\chat.gguf" }
if (-not (Test-Path $model)) {
    Write-Error (
        "Chat model not found at '$model'.`n" +
        "Set it explicitly, e.g.:`n" +
        '  $env:CHAT_MODEL = "..\models\Qwen2.5-7B-Instruct-Q4_K_M.gguf"'
    )
    exit 1
}

$cpuMoe = if ($env:CPU_MOE) { $env:CPU_MOE } else { "0" }
# @(...) around the whole if/else is required: without it, PowerShell unwraps
# the single-element array from the "1" branch into a bare string, and
# splatting a string with @moeArgs below splats it character-by-character
# (each becoming its own arg) instead of as one "--cpu-moe" token — which
# llama-server then rejects with a confusing "invalid argument: -".
$moeArgs = @(if ($cpuMoe -eq "1") { "--cpu-moe" })

& $server -m "$model" -ngl 99 -c 8192 --jinja --host 127.0.0.1 --port 8080 --alias local-chat @moeArgs
