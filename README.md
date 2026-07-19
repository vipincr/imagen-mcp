# 🎨 Imagen MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green.svg)](https://modelcontextprotocol.io)

A high-quality [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that enables AI assistants to generate images using Google's Gemini and Imagen models.

## 📖 Overview

**Imagen MCP** provides AI-powered image generation capabilities to any MCP-compatible client (such as Claude Desktop, VS Code with GitHub Copilot, or custom applications). It connects to Google's AI platform to provide access to cutting-edge image generation models.

### Why Use This MCP Server?

- 🔄 **Dynamic Model Selection**: Query available models and choose the best one for your needs
- 🖼️ **High-Quality Output**: Access to Gemini and Imagen models for 2K/4K resolution images
- 📐 **Flexible Aspect Ratios**: Support for multiple aspect ratios (1:1, 16:9, 9:16, etc.)
- 🔤 **Text Rendering**: Strong text-in-image rendering with Gemini models
- �� **Secure Configuration**: API keys stored securely via environment variables
- 🚀 **Easy Integration**: Works with any MCP-compatible AI assistant
- 📦 **Minimal Dependencies**: Only requires `fastmcp` - all other functionality uses Python standard library

## ✨ Features

| Tool | Description |
|------|-------------|
| `check_api_status` | Verify API key configuration and connectivity |
| `list_image_models` | Discover available image generation models |
| `set_image_model` | Select which model to use for generation |
| `get_current_image_model` | Check which model is currently selected |
| `generate_image_from_prompt` | Generate images from text descriptions |
| `generate_image_with_references_from_files` | Generate using 1–3 reference images (can be included as actual content, as-is or modified per prompt) |
| `generate_image_resized_from_prompt` | Generate an image then resize/compress to target bounds |
| `generate_image_with_references_resized_from_files` | Generate with references then resize/compress |
| `save_image_to_file` | Save generated images to the filesystem |
| `generate_and_save_image` | Generate and save in a single operation |
| `generate_and_save_image_resized` | Generate, resize/compress, and save an optimized output |
| `generate_and_save_image_with_references` | Generate with references and save in one step |
| `generate_and_save_image_with_references_resized` | Generate with references, resize/compress, and save |
| `convert_image` | Convert formats (png, jpeg, webp, heic/heif, ico) with favicon sizing |

## 🔧 Prerequisites

- **Python 3.9+** (uses standard library features available in 3.9+)
- **Google AI API Key** ([Get one here](https://aistudio.google.com/apikey))
- **Pillow** (installed automatically via `requirements.txt` for resizing/optimization)
- **pillow-heif** (installed via `requirements.txt` for HEIC/HEIF support)
- An MCP-compatible client (Claude Desktop, VS Code with Copilot, etc.)

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/vipincr/imagen-mcp.git
cd imagen-mcp
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or using a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure API Key

Create a `.env` file in the project root:

```env
GOOGLE_AI_API_KEY=your_google_ai_api_key_here
```

Or set it as an environment variable directly in your MCP client configuration.

> 💡 **Tip**: Get your API key from [Google AI Studio](https://aistudio.google.com/apikey)

### 4. Test the Server

```bash
python run_server.py
```

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_AI_API_KEY` | Google AI API key | ✅ Yes |
| `IMAGEN_MODEL_ID` | Default model to use (defaults to `gemini-3-pro-image-preview`) | ❌ No |

**Model selection fallback (highest priority first):** explicit tool parameter ➜ runtime `set_image_model` ➜ `IMAGEN_MODEL_ID` env var ➜ built-in default `gemini-3-pro-image-preview`.

### Supported Aspect Ratios

| Aspect Ratio | Use Case |
|--------------|----------|
| `1:1` | Social media posts, profile pictures |
| `3:2`, `2:3` | Photography, prints |
| `4:3`, `3:4` | Traditional displays |
| `4:5`, `5:4` | Instagram posts |
| `16:9`, `9:16` | Widescreen, mobile stories |
| `21:9` | Ultra-wide, cinematic |

> **Note**: Not all models support all aspect ratios. The server will automatically retry without aspect ratio if not supported.

## 🔌 MCP Client Integration

The server speaks MCP over stdio, so any MCP client can **spawn it on demand** —
you never run a server process yourself. The recommended launch command is the
self-bootstrapping launcher [`run_mcp.py`](run_mcp.py): the first time a client
starts it, it creates a private virtualenv at `~/.imagen-mcp/venv`, installs this
package, and starts the server (~0.4s on every subsequent launch). All you need
on the machine is **Python 3** and network access for that first run.

Example configs live in [`examples/`](examples/).

### Claude Code

**One command** (user scope — available in every project):

```bash
export GOOGLE_AI_API_KEY=your_key_here
./scripts/add-to-claude-code.sh
```

This runs `claude mcp add imagen --scope user … -- python3 <repo>/run_mcp.py`.
Claude Code then starts the server automatically the first time it needs an
image tool. Verify with `claude mcp list`.

**Per-project** instead: copy [`examples/claude_code.mcp.json`](examples/claude_code.mcp.json)
to your project root as `.mcp.json` (it reads `${GOOGLE_AI_API_KEY}` from your
environment, so no key is stored in the file).

### Claude Desktop

Merge [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json)
into your config file, using the absolute path to your checkout and your real key:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "imagen": {
      "command": "python3",
      "args": ["/absolute/path/to/imagen-mcp/run_mcp.py"],
      "env": {
        "GOOGLE_AI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

Restart Claude Desktop; the **imagen** tools appear under the MCP tools menu.

### VS Code with GitHub Copilot

Install the bundled extension (see [VS Code Extension](#-vs-code-extension-optional)) —
it registers the server globally and manages the API key for you, so no manual
config is required. To wire it up by hand instead, add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "imagen": {
      "command": "python3",
      "args": ["/absolute/path/to/imagen-mcp/run_mcp.py"],
      "env": {
        "GOOGLE_AI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### Using with uv

If you have [uv](https://github.com/astral-sh/uv) installed, you can skip the
bootstrap launcher and let uv manage the environment:

```json
{
  "mcpServers": {
    "imagen": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/imagen-mcp", "imagen-mcp"],
      "env": {
        "GOOGLE_AI_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

### API key resolution

The server looks for the key in this order: the `GOOGLE_AI_API_KEY` environment
variable (what the configs above set) ➜ the OS keychain (via `keyring`) ➜ a
`.env` file in the repo root. Provide it whichever way suits your client; the
env var in the MCP config is the simplest and most portable.

## 📚 Tools Reference

### `check_api_status`

Verify that your API key is configured and working.

**Parameters:** None

**Returns:**
```json
{
  "success": true,
  "api_key_configured": true,
  "api_key_valid": true,
  "total_models": 25,
  "image_models": 3,
  "current_model": "gemini-3-pro-image-preview"
}
```

---

### `list_image_models`

Discover available image generation models for your API key.

**Parameters:** None

**Returns:**
```json
{
  "success": true,
  "models": [
    {
      "name": "gemini-3-pro-image-preview",
      "display_name": "Gemini 3 Pro (Image Preview)",
      "description": "Fast image generation model..."
    }
  ],
  "current_model": null,
  "count": 3
}
```

---

### `set_image_model`

Select which model to use for image generation.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `model_name` | string | ✅ | Model ID from `list_image_models` |

**Returns:**
```json
{
  "success": true,
  "model": "gemini-3-pro-image-preview",
  "message": "Model set to 'gemini-3-pro-image-preview'. Ready for image generation."
}
```

---

### `generate_image_from_prompt`

Generate an image from a text description.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | ✅ | Detailed text description of the image |
| `aspect_ratio` | string | ❌ | One of the supported aspect ratios |
| `model` | string | ❌ | Override the current model |

**Returns:**
```json
{
  "success": true,
  "image_base64": "iVBORw0KGgo...",
  "mime_type": "image/png",
  "extension": ".png",
  "size_bytes": 1234567,
  "model_used": "gemini-3-pro-image-preview"
}
```

---

### `generate_image_with_references_from_files`

Generate an image using **1–3 reference images** (files on disk) plus a text prompt.

**Important:** reference images are *visual inputs* — you can instruct the model to include the referenced object/subject inside the generated image (as-is or modified), not only copy its style.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `reference_paths` | string[] | ✅ | 1–3 paths to reference images (order matters) |
| `prompt` | string | ✅ | Describe the output and how to use each reference (e.g., keep object identical vs modify) |
| `aspect_ratio` | string | ❌ | Optional aspect ratio |
| `model` | string | ❌ | Override the current model |

---

### `generate_image_with_references_resized_from_files`

Same as `generate_image_with_references_from_files`, but additionally resizes/compresses to target bounds.

---

### `generate_and_save_image_with_references`

Convenience tool that generates from references and saves to `output_path` (adds an extension if missing).

---

### `generate_and_save_image_with_references_resized`

Convenience tool that generates from references, resizes/compresses, and saves to `output_path`.

---

### `save_image_to_file`

Save a base64-encoded image to a file.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `image_base64` | string | ✅ | Base64-encoded image data |
| `output_path` | string | ✅ | File path to save the image |

**Returns:**
```json
{
  "success": true,
  "saved_path": "/absolute/path/to/image.png",
  "size_bytes": 1234567
}
```

---

### `generate_and_save_image`

Generate an image and save it to a file in one operation.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | ✅ | Detailed text description of the image |
| `output_path` | string | ✅ | File path to save the image |
| `aspect_ratio` | string | ❌ | One of the supported aspect ratios |
| `model` | string | ❌ | Override the current model |

**Returns:**
```json
{
  "success": true,
  "saved_path": "/absolute/path/to/image.png",
  "mime_type": "image/png",
  "size_bytes": 1234567,
  "model_used": "gemini-3-pro-image-preview"
}
```

---

### `generate_image_resized_from_prompt`

Generate an image, then resize/compress it to fit within given dimensions.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | ✅ | Detailed text description of the image |
| `max_width` | integer | ✅ | Target max width in pixels |
| `max_height` | integer | ✅ | Target max height in pixels |
| `aspect_ratio` | string | ❌ | One of the supported aspect ratios |
| `model` | string | ❌ | Override the current model |
| `format` | string | ❌ | Output format (`png`, `jpeg`, `webp`; defaults to source/PNG) |
| `quality` | integer | ❌ | Quality 1-100 (applies to JPEG/WEBP) |

**Returns:**
```json
{
  "success": true,
  "image_base64": "iVBORw0KGgo...",
  "mime_type": "image/jpeg",
  "extension": ".jpg",
  "size_bytes": 123456,
  "model_used": "gemini-3-pro-image-preview",
  "resized": true,
  "max_width": 1024,
  "max_height": 1024
}
```

---

### `generate_and_save_image_resized`

Generate an image, resize/compress it, and save to disk (kept separate from the high-res save path).

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `prompt` | string | ✅ | Detailed text description of the image |
| `output_path` | string | ✅ | File path to save; extension inferred if missing |
| `max_width` | integer | ✅ | Target max width in pixels |
| `max_height` | integer | ✅ | Target max height in pixels |
| `aspect_ratio` | string | ❌ | One of the supported aspect ratios |
| `model` | string | ❌ | Override the current model |
| `format` | string | ❌ | Output format (`png`, `jpeg`, `webp`; defaults to source/PNG) |
| `quality` | integer | ❌ | Quality 1-100 (applies to JPEG/WEBP) |

**Returns:**
```json
{
  "success": true,
  "saved_path": "/absolute/path/to/image.jpg",
  "mime_type": "image/jpeg",
  "size_bytes": 123456,
  "model_used": "gemini-3-pro-image-preview",
  "resized": true,
  "max_width": 1024,
  "max_height": 1024
}
```

---

### `convert_image`

Convert an image to another format, optionally emitting multi-size ICOs for favicons.

**Parameters:**
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `input_path` | string | ✅ | Source image path |
| `output_path` | string | ✅ | Destination path (extension may be inferred from `format`) |
| `format` | string | ✅ | One of `png`, `jpeg`/`jpg`, `webp`, `heic`/`heif`, `ico` |
| `sizes` | array<int> | ❌ | For ICO: list of sizes (e.g., `[16,32,48,64,128]`); ignored for other formats |

**Returns:**
```json
{
  "success": true,
  "saved_path": "/absolute/path/to/favicon.ico",
  "mime_type": "image/x-icon",
  "sizes": [16,32,48,64,128],
  "format": "ico"
}
```

## 💡 Usage Examples

Once the server is connected to your AI assistant, you can use natural language:

### First-Time Setup
> "Check if my API key is configured correctly"
> "List available image generation models"
> "Set the model to gemini-2.0-flash-exp-image-generation"

### Basic Image Generation
> "Generate a sunset over mountains with vibrant orange and purple colors"

### Product Photography
> "Create a product shot of a smartwatch on a minimalist white surface with dramatic lighting"

### Specific Dimensions
> "Generate a 16:9 banner image for a tech blog featuring abstract circuit patterns"

### Save to Project
> "Generate a hero image for my website and save it to assets/images/hero.png"

## 🏗️ Project Structure

```
imagen-mcp/
├── imagen_mcp/              # Main package (renamed from image_generator)
│   ├── __init__.py          # Package initialization & public API
│   ├── core.py              # Core image generation & model listing logic
│   └── server.py            # MCP server implementation with tools
├── run_server.py            # Standalone server entry point
├── pyproject.toml           # Python package configuration
├── requirements.txt         # Python dependencies
├── LICENSE                  # MIT License
├── README.md                # This file
├── CONTRIBUTING.md          # Contribution guidelines
└── vscode-extension/        # VS Code extension to manage MCP config
    ├── package.json
    ├── tsconfig.json
    ├── src/extension.ts     # Extension implementation
    ├── scripts/
    │   ├── copy-server.js   # Copies imagen_mcp to server/ during build
    │   └── bump-version.js  # Version management
    └── server/               # Bundled server code (generated during build)
        ├── imagen_mcp/       # Copied from root during build
        └── run_server.py    # Extension entry point
```

## 🧩 VS Code Extension (Optional)

You can manage the MCP server from inside VS Code via the bundled extension.

### Build & Install

#### For End Users (Marketplace install — auto updates)

- Install from the VS Code Marketplace (search “Imagen MCP Server”). Marketplace installs auto-update with new releases.
- After install: run the commands below to set your API key and model.

#### For Manual / VSIX Install

1. `cd vscode-extension`
2. `npm install`
3. `npm run package` (creates `imagen-mcp-vscode-<version>.vsix`)
4. In VS Code, run “Extensions: Install from VSIX...” and pick the `.vsix` (updates require installing the new VSIX).

#### For Contributors (publish a release)

1. Set `publisher` in `vscode-extension/package.json` (already `gramini-consulting`).
2. Set `VSCE_PAT` (Personal Access Token with Marketplace publish rights).
3. `cd vscode-extension && npm install && npm run package && npx vsce publish` (bumps version before publish as needed).
4. Tag the release in GitHub and attach the `.vsix` for non-marketplace installs.

### Commands (Command Palette → "Imagen MCP")

- **Set API Key** – validated and stored once in VS Code Secret Storage (OS keychain), shared across all workspaces.
- **Clear API Key** – removes the stored key.
- **Select Model** – updates the application-scoped setting `imagenMcp.modelId` (default `gemini-3-pro-image-preview`).
- **Reinstall Python Environment** – rebuilds the shared virtual environment.

The extension registers the MCP server **globally** via VS Code's MCP provider API
(`vscode.lm.registerMcpServerDefinitionProvider`, VS Code 1.101+). It does **not**
write `.vscode/mcp.json` into your workspaces; the API key is injected into the
server process from Secret Storage at launch.

### Extension Settings

- `imagenMcp.modelId` (application scope, default `gemini-3-pro-image-preview`) — the default image model, applied across all workspaces.

The API key is intentionally **not** a setting — it lives only in Secret Storage.

## 🛡️ Security Considerations

- **API Key Protection**: Never commit your API key. Use environment variables or `.env` files
- **Secure Storage**: The `.env` file is included in `.gitignore` by default
- **MCP Configuration**: API keys can be passed securely via MCP client env configuration
- **File System Access**: Be mindful of where images are saved

## 🔍 Troubleshooting

### Common Issues

**"Missing API key" error**
- Ensure `GOOGLE_AI_API_KEY` is set in your environment or `.env` file
- Check that the `.env` file is in the project root directory
- Verify the key is passed in your MCP client configuration

**"No model selected" error**
- Use `list_image_models` to see available models
- Use `set_image_model` to select one before generating

**"Aspect ratio is not enabled" error**
- The server automatically retries without aspect ratio
- Some models don't support custom aspect ratios

**No image models found**
- Your API key may not have access to image generation models
- Check your Google AI Studio account for API access

**Connection issues with MCP client**
- Verify the path in your MCP configuration is absolute
- Check that Python is in your system PATH
- Ensure all dependencies are installed

### Debugging

Check your MCP client's logs:
- **Claude Desktop**: Check the application logs
- **VS Code**: View Output panel → MCP

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Ways to Contribute

- 🐛 Report bugs and issues
- 💡 Suggest new features
- 📖 Improve documentation
- 🔧 Submit pull requests

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2025 Vipin Ravindran

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

## 🙏 Acknowledgments

- [Model Context Protocol](https://modelcontextprotocol.io) - The protocol specification
- [FastMCP](https://github.com/jlowin/fastmcp) - Python MCP framework
- [Google Gemini](https://ai.google.dev/) - Image generation models

## 📬 Support

- **Issues**: [GitHub Issues](https://github.com/vipincr/imagen-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/vipincr/imagen-mcp/discussions)

---

<p align="center">
  Made with ❤️ for the MCP community
</p>
