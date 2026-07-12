# Convenience launcher for a llama.cpp EMBEDDING server (OpenAI-compatible) on :8081.
#   $env:LLAMA_SERVER  = full path to llama-server(.exe)
#   $env:EMBED_MODEL_PATH = path to a .gguf embedding model (e.g. nomic-embed-text)
$ErrorActionPreference = "Stop"
$server = if ($env:LLAMA_SERVER)     { $env:LLAMA_SERVER }     else { "llama-server" }
$model  = if ($env:EMBED_MODEL_PATH) { $env:EMBED_MODEL_PATH } else { "models\embed.gguf" }

& $server -m "$model" --embedding --pooling mean -ngl 99 `
  -c 2048 -b 2048 -ub 2048 --host 127.0.0.1 --port 8081 --alias local-embed
