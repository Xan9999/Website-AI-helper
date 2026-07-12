#!/usr/bin/env bash
# One-command setup (macOS / Linux): creates a venv and installs the tool.
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -e .
echo
echo "Installed. Next:"
echo "  source .venv/bin/activate"
echo "  website-ai-helper init"
echo "  website-ai-helper ingest https://your-site.com --collection mysite"
echo "  website-ai-helper serve --collection mysite"
