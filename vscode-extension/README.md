# Imagen MCP Server (VS Code Extension)

Manage and configure the Imagen MCP server from VS Code:
- Securely store your Google AI API key (Secret Storage)
- Pick the image model (default `gemini-3-pro-image-preview`)
- Auto-generate `.vscode/mcp.json` so MCP works out of the box
- **Standalone installation** — no additional files required in your workspace

## Requirements
- **Python 3** must be installed on your system
- The extension automatically creates a virtual environment and installs dependencies

## Commands (Command Palette)
- **Imagen MCP: Set API Key** — stores key in Secret Storage
- **Imagen MCP: Select Model** — sets `imagenMcp.modelId`
- **Imagen MCP: Generate MCP Config** — writes `.vscode/mcp.json` with command/args/env
- **Imagen MCP: Reinstall Python Environment** — recreates the virtual environment (useful for troubleshooting)

## Settings
- `imagenMcp.apiKey` (string) — optionally set your Google AI key in settings; it syncs to secret storage and `.vscode/mcp.json`. Stored in settings as plain text. You'll get a warning toast with a shortcut to set it when missing.
- `imagenMcp.modelId` (default `gemini-3-pro-image-preview`)

## Installation
- Marketplace: search **Imagen MCP Server** (auto-updates)
- VSIX: run `npm run package` then "Install from VSIX…"

## Behavior
- On activation, the extension automatically:
  1. Sets up a Python virtual environment (stored in VS Code's global storage)
  2. Installs required dependencies (fastmcp, Pillow, pillow-heif)
  3. Creates `.vscode/mcp.json` using the bundled server and your stored API key

The virtual environment is shared across all workspaces, so setup only happens once.

## License
MIT
