#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

ensure_uv() {
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  echo "[setup] uv not found; attempting installation"
  if [[ "$(uname -s)" == "Darwin" ]] && command -v brew >/dev/null 2>&1; then
    brew install uv || true
  fi
  if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh || true
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    if [[ -f "$HOME/.cargo/env" ]]; then
      # shellcheck disable=SC1091
      . "$HOME/.cargo/env"
    fi
  fi
  command -v uv >/dev/null 2>&1
}

use_uv=0
if ensure_uv; then
  use_uv=1
else
  use_uv=0
fi

# Try uv path first (preferred for consistent, python>=3.10 env)
if [[ "$use_uv" -eq 1 ]]; then
  echo "[setup] Using uv to sync dependencies"
  uv sync
  echo "[setup] Initializing SQLite database (uv)"
  uv run python scripts/init_db.py
  echo "[setup] Done."
  exit 0
fi

# Fallback: venv + pip
echo "[setup] uv is not installed; falling back to venv + pip"

# choose python executable
PYTHON="python3"
# Prefer newer python if available
if command -v python3.12 >/dev/null 2>&1; then PYTHON="python3.12"; 
elif command -v python3.11 >/dev/null 2>&1; then PYTHON="python3.11";
elif command -v python3.10 >/dev/null 2>&1; then PYTHON="python3.10"; fi

echo "[setup] Using $PYTHON to create virtualenv"
$PYTHON -m venv .venv
. .venv/bin/activate

pip install --upgrade pip

# ensure tomli available for py<=3.10 parsing
pip install tomli || true

# Try editable install first; if it fails, install dependencies directly
if ! pip install -e ".[all]"; then
  echo "[setup] Editable install failed; installing dependencies from pyproject"
  pip install -r <(python - <<'PY'
import sys
try:
    import tomllib  # Python >=3.11
except ModuleNotFoundError:
    import tomli as tomllib  # Python <=3.10

with open("pyproject.toml","rb") as f:
    data = tomllib.load(f)
deps = data.get("project",{}).get("dependencies",[])
print("\n".join(deps))
PY
  )
fi

echo "[setup] Initializing SQLite database (venv)"
python scripts/init_db.py

echo "[setup] Done."
