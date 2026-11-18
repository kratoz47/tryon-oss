#!/usr/bin/env bash
# 跨平台启动（macOS / Linux）。Windows 用「启动本地.ps1」。
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/python -m pip install -r deploy/requirements.txt
fi

exec .venv/bin/python local/server.py --port "${PORT:-8765}"
