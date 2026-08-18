#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "[Celeste] Creando entorno virtual..."
  python3 -m venv .venv
fi

./.venv/bin/python -m pip install -e '.[dev]'
export CELESTE_API_TOKEN="${CELESTE_API_TOKEN:-celeste-local-dev}"

echo "[Celeste] Iniciando Core en http://0.0.0.0:8000"
./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
