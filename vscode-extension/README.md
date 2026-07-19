# Imagen MCP Server (VS Code Extension)

Adds a **Google AI (Gemini / Imagen) image-generation MCP server** to VS Code and
registers it **globally** — for GitHub Copilot Chat and any other MCP client — so it
works in **every workspace and window** without dropping any config files into your
projects.

- 🔑 **Set your API key once.** It is stored in VS Code Secret Storage (your OS
  keychain) and reused everywhere. You are never asked again unless you clear it.
- 🌍 **Global, not per-project.** The server is registered through VS Code's MCP
  provider API — no `.vscode/mcp.json` is written into your workspaces.
- 🖼️ **Image tools:** generate, edit, generate-with-references (up to 3 reference
  images as real visual inputs), format conversion, and more.
- 🐍 **Zero manual setup.** A private Python virtual environment is created once in
  the extension's global storage and shared across all workspaces.

## Requirements

- **VS Code 1.101 or newer** (the MCP server provider API).
- **Python 3** available on your `PATH`. The extension creates and manages its own
  virtual environment; it never touches your system or project interpreters.

## Getting started

1. Install the extension.
2. Open the **MCP Servers** view (or run any Copilot Chat request that needs images).
   The first time the **Imagen (Google AI)** server starts, you'll be prompted for
   your Google AI API key. It's validated and saved to Secret Storage.
3. That's it — the key and model apply to every workspace from now on.

Get an API key from [Google AI Studio](https://aistudio.google.com/apikey).

## Commands (Command Palette → "Imagen MCP")

- **Set API Key** — enter/replace your Google AI API key (validated, stored securely).
- **Clear API Key** — remove the stored key.
- **Select Model** — choose the default image model (stored in global settings).
- **Reinstall Python Environment** — rebuild the virtual environment for troubleshooting.

## Settings

- `imagenMcp.modelId` (application scope, default `gemini-3-pro-image`) —
  the default image model, applied across all workspaces.

The API key is **not** a setting — it lives only in Secret Storage so it can never
leak into a settings file or a committed workspace file.

## How it works

On activation the extension registers an MCP server definition provider. When the
server is started, the extension:

1. Ensures the shared Python virtual environment exists (fastmcp, Pillow, pillow-heif).
2. Reads your API key from Secret Storage (prompting once if missing).
3. Launches the bundled server, passing `GOOGLE_AI_API_KEY` and `IMAGEN_MODEL_ID`
   as environment variables — nothing is written to disk in your workspace.

## Installation from VSIX

```bash
npm install
npm run package   # builds ../build/imagen-mcp-vscode-<version>.vsix
```

Then run **Extensions: Install from VSIX…** and pick the file.

## Migrating from earlier versions

Older versions wrote a `.vscode/mcp.json` file into each workspace. On first run,
this version removes the old Imagen entry (and any stored key input) from that file
automatically. You can safely delete a now-empty `.vscode/mcp.json`.

## License

MIT
