#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
# Load .env from repo root if present
if [ -f "../.env" ]; then
  set -a
  . ../.env
  set +a
fi
# Run via uv if available for consistent env
if command -v uv >/dev/null 2>&1; then
  uv run python -m uvicorn app.main:app --reload --host "${BACKEND_HOST:-127.0.0.1}" --port "${BACKEND_PORT:-8050}"
else
  python -m uvicorn app.main:app --reload --host "${BACKEND_HOST:-127.0.0.1}" --port "${BACKEND_PORT:-8050}"
fi
