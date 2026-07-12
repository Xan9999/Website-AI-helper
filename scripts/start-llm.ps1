# Convenience launcher for a llama.cpp CHAT server (OpenAI-compatible) on :8080.
# Not required — you can use any OpenAI-compatible endpoint (Ollama, a remote
# server, etc.). Set these env vars or edit the defaults.
#   $env:LLAMA_SERVER  = full path to llama-server(.exe)
#   $env:CHAT_MODEL    = path to a .gguf chat model (instruct, tool-capable)
$ErrorActionPreference = "Stop"
$server = if ($env:LLAMA_SERVER) { $env:LLAMA_SERVER } else { "llama-server" }
$model  = if ($env:CHAT_MODEL)   { $env:CHAT_MODEL }   else { "models\chat.gguf" }

& $server -m "$model" -ngl 99 -c 8192 --jinja --host 127.0.0.1 --port 8080 --alias local-chat
