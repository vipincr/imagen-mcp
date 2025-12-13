#!/usr/bin/env python3
"""Startup script for the Imagen MCP Server."""

from mcp_server.server import mcp

if __name__ == "__main__":
    # Run with stdio transport (default for MCP) without banner noise
    mcp.run(show_banner=False, log_level="WARNING")
