#!/usr/bin/env python3
"""Startup script for the Imagen MCP Server.

This script starts the MCP server using stdio transport, which is the
standard way to connect MCP servers to AI assistants like Claude Desktop,
VS Code with GitHub Copilot, or other MCP-compatible clients.

Usage:
    python run_server.py
    
Or make executable and run directly:
    chmod +x run_server.py
    ./run_server.py
"""
import sys
from pathlib import Path

# Add the mcp directory to path so imports work correctly
mcp_dir = Path(__file__).resolve().parent
if str(mcp_dir) not in sys.path:
    sys.path.insert(0, str(mcp_dir))

from image_generator.server import mcp

if __name__ == "__main__":
    # Run with stdio transport (default for MCP)
    mcp.run()
