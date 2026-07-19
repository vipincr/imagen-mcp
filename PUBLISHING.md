# Publishing to the MCP Registry (rich VS Code gallery page)

This is what gives Imagen the same kind of gallery page as popular servers like
**Chrome DevTools MCP** — icon, description, tags, license, repository/resources
links, changelog, and an `io.github.…` identifier — inside VS Code's **MCP
Servers** view and other MCP clients.

## How the rich page works

That page is **not** produced by the VS Code extension. It comes from two things:

1. A **published package** — Imagen is published to **PyPI** (`imagen-mcp`). PyPI
   supplies the description, keywords (shown as **tags**), license, and rendered
   README.
2. A **registry entry** — a [`server.json`](server.json) published to the
   [official MCP Registry](https://registry.modelcontextprotocol.io). VS Code's
   MCP gallery reads this and renders the DETAILS / MANIFEST / CONFIGURATION tabs,
   icon, tags, and Resources.

Ownership is proven by the `<!-- mcp-name: io.github.vipincr/imagen-mcp -->`
marker at the top of [`README.md`](README.md) (which becomes the PyPI
description). The `name` in `server.json` must match that marker and the GitHub
account used to log in (`io.github.<owner>/…`).

## Prerequisites

- A **PyPI account** + API token — <https://pypi.org/manage/account/token/>
- The **GitHub account** that owns `github.com/vipincr/imagen-mcp`
- `uv` (recommended) or `python -m build` + `twine`
- The `mcp-publisher` CLI (installed by the script below, or via `brew install mcp-publisher`)

## Quick path

```bash
export PYPI_TOKEN=pypi-...              # your PyPI API token
./scripts/publish-registry.sh
```

The script builds the package, uploads it to PyPI, installs `mcp-publisher` if
needed, then logs you in via GitHub and publishes `server.json`.

## Manual steps

### 1. Keep versions in sync

`pyproject.toml`, `imagen_mcp/__init__.py` (`__version__`), and **both** version
fields in `server.json` (top-level `version` and `packages[0].version`) must be
identical. Bump all of them for each release.

### 2. Build and publish to PyPI

```bash
python -m pip install --upgrade build twine
python -m build                                    # -> dist/*.whl, dist/*.tar.gz
twine upload dist/* -u __token__ -p "$PYPI_TOKEN"
```

Verify at <https://pypi.org/project/imagen-mcp/>. The page must contain the
`mcp-name: io.github.vipincr/imagen-mcp` string (from the README) — that's the
ownership proof the registry checks.

### 3. Install `mcp-publisher`

```bash
curl -L "https://github.com/modelcontextprotocol/registry/releases/latest/download/mcp-publisher_$(uname -s | tr '[:upper:]' '[:lower:]')_$(uname -m | sed 's/x86_64/amd64/;s/aarch64/arm64/').tar.gz" \
  | tar xz mcp-publisher && sudo mv mcp-publisher /usr/local/bin/
# or: brew install mcp-publisher
```

### 4. Authenticate and publish

```bash
mcp-publisher login github        # opens a device-code flow in your browser
mcp-publisher publish             # reads ./server.json
```

Within a minute the server appears in the MCP Registry and, shortly after, in the
VS Code MCP gallery (search `@mcp imagen`) with the full rich page.

## Updating

Bump the versions (step 1), re-run steps 2 and 4. `mcp-publisher publish` is
idempotent per version; the registry rejects a re-publish of an existing version.
