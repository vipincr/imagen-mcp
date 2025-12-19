# Architecture Documentation

## Overview

The Imagen MCP Server is a Model Context Protocol (MCP) server that provides image generation capabilities using Google's Gemini and Imagen models. The project consists of two main components:

1. **Standalone MCP Server** (`imagen_mcp/` package) - Can be used by any MCP-compatible client
2. **VS Code Extension** (`vscode-extension/`) - Provides UI for managing the MCP server configuration

## Package Structure

### `imagen_mcp/` - Core Package

The main Python package containing all server logic:

- **`core.py`**: Business logic for image generation, model management, API communication
  - Image generation functions (`generate_image`, `generate_image_with_references`, etc.)
  - Model listing and validation
  - Image processing (resizing, conversion, file I/O)
  - API key management with keyring fallback
  
- **`server.py`**: MCP server implementation using FastMCP
  - Tool definitions (all `@mcp.tool()` decorated functions)
  - Error handling wrapper (`_wrap_tool()`)
  - Response formatting helpers
  - Server initialization

- **`__init__.py`**: Public API exports
  - Exports core functions and the `mcp` server instance

### Entry Points

- **`run_server.py`**: Standalone entry point for running the server directly
  - Imports `mcp` from `imagen_mcp.server`
  - Configures logging and runs the server

## Data Flow

### Image Generation Flow

```
User/Agent Request
    ↓
MCP Tool Call (e.g., generate_image_from_prompt)
    ↓
server.py: Tool Handler
    ↓
core.py: generate_image()
    ↓
core.py: HTTP Request to Google AI API
    ↓
core.py: Parse Response → ImageResult
    ↓
server.py: Format Response (base64 or save to file)
    ↓
MCP Response to Client
```

### Model Selection Flow

```
1. Tool Parameter (explicit model)
   OR
2. Runtime State (set_image_model)
   OR
3. Environment Variable (IMAGEN_MODEL_ID)
   OR
4. Default (gemini-3-pro-image-preview)
```

## VS Code Extension Architecture

### Build Process

1. **TypeScript Compilation**: `npm run compile` compiles `src/extension.ts` → `out/extension.js`
2. **Server Copy**: `npm run copy-server` copies `imagen_mcp/` to `vscode-extension/server/`
3. **Package**: `npm run package` creates `.vsix` file with bundled code

### Runtime Behavior

1. **Activation**: Extension activates on startup or command
2. **Python Environment Setup**: Creates venv in global storage, installs dependencies
3. **MCP Config Generation**: Writes `.vscode/mcp.json` with server configuration
4. **API Key Management**: Uses VS Code Secret Storage via MCP inputs

### Key Functions

- **`ensurePythonEnvironment()`**: Sets up Python venv with dependencies
- **`ensureMcpConfig()`**: Generates/updates MCP configuration file
- **`getServerConfig()`**: Returns command and args for bundled server
- **`cleanupLeakedKeysSync()`**: Removes API keys from workspace files (security)

## Design Decisions

### Why Single Package (`imagen_mcp`)?

- **Eliminates redundancy**: Previously had `image_generator` + `mcp_server` wrapper
- **Clearer naming**: `imagen_mcp` reflects it's an MCP server, not just an image generator
- **Single source of truth**: All code in one place, no sync needed

### Why Copy Instead of Install?

- **Extension bundling**: VS Code extensions need all code bundled
- **No external dependencies**: Extension works offline after installation
- **Simpler deployment**: No need to publish to PyPI for extension use

### Error Handling Strategy

- **Consistent wrapper**: All tools use `_wrap_tool()` for uniform error responses
- **Error types**: Catches `ValueError`, `RuntimeError`, `OSError`, `FileNotFoundError`
- **Response format**: Always returns `{"success": bool, ...}` with optional `"error"` field

### API Key Management

- **Priority order**:
  1. Tool parameter (if applicable)
  2. Environment variable (`GOOGLE_AI_API_KEY`)
  3. OS keyring (via Python `keyring` library)
- **VS Code integration**: Uses MCP inputs for secure storage (never written to files)

## Dependencies

### Runtime Dependencies
- `fastmcp>=2.0.0`: MCP protocol implementation
- `Pillow>=10.4.0`: Image processing (resizing, conversion)
- `pillow-heif>=0.18.0`: HEIC/HEIF format support

### Development Dependencies
- `pytest>=7.0.0`: Testing framework
- `pylint>=2.0.0`: Code quality checks

## Extension Points

### Adding New Tools

1. Add function to `core.py` (business logic)
2. Add `@mcp.tool()` decorated function to `server.py`
3. Use `_wrap_tool()` for error handling
4. Export from `__init__.py` if needed for external use

### Adding New Image Formats

1. Update `_normalize_target_format()` in `core.py`
2. Add format handling in `convert_image_format()`
3. Update MIME type mapping if needed

## Testing Strategy

- **Unit tests**: `tests/test_core.py` - Tests core functionality with mocks
- **Integration tests**: Requires `GOOGLE_AI_API_KEY` - Tests against real API
- **Test structure**: Uses `unittest` framework with mock patches

## Security Considerations

- **API keys**: Never committed, stored in environment or keyring
- **File access**: Tools validate paths and create directories safely
- **Input validation**: All user inputs validated before API calls
- **Error messages**: Don't expose sensitive information in errors

## Future Improvements

- Consider publishing `imagen_mcp` to PyPI for easier installation
- Add more image processing options (filters, transformations)
- Support for batch operations
- Caching layer for model listings
- Async/await support for better performance

