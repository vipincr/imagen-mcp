# Changelog

All notable changes to the Imagen MCP Server extension are documented here.

## [0.2.1]

### Changed

- Default image model is now **`gemini-3-pro-image`** (Nano Banana Pro, GA) —
  the stable release of Google's highest-quality image model, replacing the
  preview default. The model picker was refreshed to the current lineup
  (added Nano Banana 2 / `gemini-3.1-flash-image`; removed the retired
  `gemini-2.0-flash-exp-image-generation`).

## [0.2.0]

### Changed (breaking)

- **Global MCP registration.** The server is now registered through VS Code's
  `mcpServerDefinitionProviders` API (`vscode.lm.registerMcpServerDefinitionProvider`)
  instead of writing a per-workspace `.vscode/mcp.json`. The server is available in
  **every** workspace and window, and appears as a managed entry (icon, label,
  description, settings) in the MCP panel.
- **Requires VS Code 1.101+** for the MCP provider API.

### Added

- API key is stored **once** in global Secret Storage (OS keychain) and reused
  everywhere; it is validated against Google AI before being saved and never
  requested again unless cleared.
- **Imagen MCP: Clear API Key** command.
- `imagenMcp.modelId` is now an application-scoped setting with a dropdown of
  known models.
- esbuild bundling, ESLint (flat config), and a GitHub Actions CI workflow.

### Removed

- No longer writes `.vscode/mcp.json`, workspace settings, or any file into your
  projects. A one-time migration strips the old Imagen entry from any existing
  `.vscode/mcp.json`.
- Removed the **Generate MCP Config** command (obsolete under the provider API).
- Removed the deprecated `vscode` (`^1.1.37`) dev dependency.
- Removed stale empty `server/` subdirectories that were being bundled.

## [0.1.x]

- Earlier releases configured the server by writing `.vscode/mcp.json` into each
  workspace and prompting for the API key via a VS Code input on server start.
