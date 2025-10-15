#!/usr/bin/env bash
set -euo pipefail
if [ ! -f ".venv/bin/activate" ]; then
  python3 -m venv .venv
  . .venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
else
  . .venv/bin/activate
fi
# Load root .env if present
if [ -f "../.env" ]; then
  set -a
  . ../.env
  set +a
fi
streamlit run app.py --server.port 8501
