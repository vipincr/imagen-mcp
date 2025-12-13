#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
REQ_FILE="$ROOT_DIR/requirements.txt"

if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$PYTHON" -m pip install --upgrade pip >/dev/null
"$PYTHON" -m pip install -r "$REQ_FILE" >/dev/null

# Ensure project root is on PYTHONPATH so tests import local package
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

exec "$PYTHON" -m unittest discover -s "$ROOT_DIR/tests" -v
