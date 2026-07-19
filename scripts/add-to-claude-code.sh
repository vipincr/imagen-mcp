#!/usr/bin/env bash
#
# Register the Imagen MCP server with Claude Code (user scope, available in
# every project). Requires the `claude` CLI and a GOOGLE_AI_API_KEY in your env.
#
# Usage:
#   export GOOGLE_AI_API_KEY=your_key_here
#   ./scripts/add-to-claude-code.sh
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v claude >/dev/null 2>&1; then
  echo "error: the 'claude' CLI was not found on PATH." >&2
  echo "Install Claude Code first: https://docs.claude.com/en/docs/claude-code" >&2
  exit 1
fi

: "${GOOGLE_AI_API_KEY:?Set GOOGLE_AI_API_KEY in your environment first}"

# Remove any prior registration so re-running is idempotent.
claude mcp remove imagen --scope user >/dev/null 2>&1 || true

claude mcp add imagen \
  --scope user \
  --env "GOOGLE_AI_API_KEY=${GOOGLE_AI_API_KEY}" \
  -- python3 "${REPO}/run_mcp.py"

echo
echo "Added 'imagen' to Claude Code (user scope)."
echo "Claude Code will start it automatically the first time it needs an image tool."
echo "Verify with: claude mcp list"
