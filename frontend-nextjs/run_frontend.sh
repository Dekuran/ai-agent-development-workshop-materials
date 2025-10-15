#!/usr/bin/env bash
set -euo pipefail
if command -v pnpm >/dev/null 2>&1; then
  pnpm install
  pnpm dev -p 3000
else
  npm install
  npm run dev -- --port 3000
fi
