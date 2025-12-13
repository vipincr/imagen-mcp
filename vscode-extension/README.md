# Imagen MCP Server (VS Code Extension)

Manage and configure the Imagen MCP server from VS Code:
- Securely store your Google AI API key (Secret Storage)
- Pick the image model (default `gemini-3-pro-image-preview`)
- Auto-generate `.vscode/mcp.json` so MCP works out of the box

## Commands (Command Palette)
- **Imagen MCP: Set API Key** — stores key in Secret Storage
- **Imagen MCP: Select Model** — sets `imagenMcp.modelId`
- **Imagen MCP: Generate MCP Config** — writes `.vscode/mcp.json` with command/args/env

## Settings
- `imagenMcp.apiKey` (string) — optionally set your Google AI key in settings; it syncs to secret storage and `.vscode/mcp.json`. Stored in settings as plain text. You’ll get a warning toast with a shortcut to set it when missing.
- `imagenMcp.modelId` (default `gemini-3-pro-image-preview`)
- `imagenMcp.serverCommand` (default `${workspaceFolder}/run_with_venv.sh` for auto-venv + deps)
- `imagenMcp.serverArgs` (default `[]`)

Tip: override `imagenMcp.serverCommand`/`serverArgs` if you have a custom launcher.
Note: when using the default `run_with_venv.sh`, the extension sets the executable bit automatically if needed.

## Installation
- Marketplace: search **Imagen MCP Server** (auto-updates)
- VSIX: run `npm run package` then “Install from VSIX…”

## Behavior
- On activation, if `.vscode/mcp.json` is missing, it’s created automatically using your settings and stored API key.

## License
MIT
