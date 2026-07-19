#!/usr/bin/env bash
#
# Publish imagen-mcp to PyPI and the MCP Registry, giving it a rich VS Code MCP
# gallery page. See PUBLISHING.md for details.
#
# Requires:
#   - PYPI_TOKEN env var (a PyPI API token: https://pypi.org/manage/account/token/)
#   - The GitHub account that owns github.com/vipincr/imagen-mcp (for mcp-publisher login)
#
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

: "${PYPI_TOKEN:?Set PYPI_TOKEN to a PyPI API token (see PUBLISHING.md)}"

# ---- Version sanity check: pyproject, __init__, and server.json must match ----
PY_VER=$(sed -n 's/^version = "\([^"]*\)".*/\1/p' pyproject.toml | head -1)
SJ_TOP=$(python3 -c "import json;print(json.load(open('server.json'))['version'])")
SJ_PKG=$(python3 -c "import json;print(json.load(open('server.json'))['packages'][0]['version'])")
if [[ "$PY_VER" != "$SJ_TOP" || "$PY_VER" != "$SJ_PKG" ]]; then
  echo "error: version mismatch — pyproject=$PY_VER server.json(top)=$SJ_TOP server.json(pkg)=$SJ_PKG" >&2
  echo "Make all three identical before publishing." >&2
  exit 1
fi
echo "Publishing version $PY_VER"

# ---- 1. Build and upload to PyPI ----
echo "==> Building distribution"
python3 -m pip install --quiet --upgrade build twine
rm -rf dist
python3 -m build

echo "==> Uploading to PyPI"
python3 -m twine upload dist/* -u __token__ -p "$PYPI_TOKEN"

# ---- 2. Ensure mcp-publisher is available ----
if ! command -v mcp-publisher >/dev/null 2>&1; then
  echo "==> Installing mcp-publisher"
  os=$(uname -s | tr '[:upper:]' '[:lower:]')
  arch=$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/')
  url="https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_${os}_${arch}.tar.gz"
  tmp=$(mktemp -d)
  curl -L "$url" | tar xz -C "$tmp" mcp-publisher
  sudo mv "$tmp/mcp-publisher" /usr/local/bin/
fi

# ---- 3. Authenticate and publish to the MCP Registry ----
echo "==> Logging in to the MCP Registry (GitHub device flow)"
mcp-publisher login github

echo "==> Publishing server.json"
mcp-publisher publish

echo
echo "Done. Search '@mcp imagen' in the VS Code Extensions view to see the gallery page."
