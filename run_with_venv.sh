#!/usr/bin/env bash
set -euo pipefail

# Resolve repo root (directory of this script)
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$ROOT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"
REQ_FILE="$ROOT_DIR/requirements.txt"
SERVER="$ROOT_DIR/run_server.py"

# Create venv if missing
if [[ ! -x "$PYTHON" ]]; then
  python3 -m venv "$VENV_DIR"
fi

# Ensure pip and deps
"$PYTHON" -m pip install --upgrade pip >/dev/null
"$PYTHON" -m pip install -r "$REQ_FILE" >/dev/null

# Run the MCP server unless skipped
if [[ "${MCP_SKIP_RUN:-}" != "" ]]; then
  exit 0
fi

exec "$PYTHON" "$SERVER"
