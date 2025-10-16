#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Prefer uvx if available (runs without needing a local venv)
if command -v uvx >/dev/null 2>&1; then
  # Load root .env if present
  if [ -f "../.env" ]; then
    set -a; . ../.env; set +a
  fi
  # Ensure required deps are available in the ephemeral runner
  exec uvx --with python-dotenv --with requests streamlit run app.py --server.port "${FRONTEND_PORT:-8501}"
fi

VENV_DIR=".venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
STREAMLIT="$VENV_DIR/bin/streamlit"

# Create venv if missing
if [ ! -x "$PY" ]; then
  python3 -m venv "$VENV_DIR"
fi

# Install/upgrade deps using venv pip (explicit path to avoid PATH issues)
"$PIP" install --upgrade pip
"$PIP" install -r requirements.txt

# Load root .env if present
if [ -f "../.env" ]; then
  set -a; . ../.env; set +a
fi

# Run streamlit from the venv explicitly
exec "$STREAMLIT" run app.py --server.port "${FRONTEND_PORT:-8501}"
