# Imagen MCP Server (VS Code Extension)

Manage and configure the Imagen MCP server from VS Code:
- Securely store your Google AI API key (Secret Storage)
- Pick the image model (default `gemini-3-pro-image-preview`)
- Auto-generate `.vscode/mcp.json` so MCP works out of the box
- Use MCP image tools including generation, editing, and generation with up to 3 reference images (references can be used as actual visual inputs per prompt)
- **Standalone installation** — no additional files required in your workspace

## Requirements
- **Python 3** must be installed on your system
- The extension automatically creates a virtual environment and installs dependencies

## Commands (Command Palette)
- **Imagen MCP: Set API Key** — stores key in Secret Storage
- **Imagen MCP: Select Model** — sets `imagenMcp.modelId`
- **Imagen MCP: Generate MCP Config** — writes `.vscode/mcp.json` with command/args (does not write API keys)
- **Imagen MCP: Reinstall Python Environment** — recreates the virtual environment (useful for troubleshooting)

## Settings
- `imagenMcp.apiKey` (string) — deprecated. If set in workspace settings, it will be migrated into Secret Storage and removed to prevent leaks.
- `imagenMcp.modelId` (default `gemini-3-pro-image-preview`)

## Installation
- Marketplace: search **Imagen MCP Server** (auto-updates)
- VSIX: run `npm run package` then "Install from VSIX…"

## Behavior
- On activation, the extension automatically:
  1. Sets up a Python virtual environment (stored in VS Code's global storage)
  2. Installs required dependencies (fastmcp, Pillow, pillow-heif)
  3. Creates `.vscode/mcp.json` using the bundled server (API key is never written to workspace files)

The MCP server reads `GOOGLE_AI_API_KEY` from your environment, or from the OS keychain (via Python `keyring`) when you use **Imagen MCP: Set API Key**.

The virtual environment is shared across all workspaces, so setup only happens once.

## License
MIT
