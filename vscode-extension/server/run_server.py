#!/usr/bin/env python3
"""Startup script for the Imagen MCP Server."""
from pathlib import Path
import sys

SERVER_DIR = Path(__file__).resolve().parent
REPO_ROOT = SERVER_DIR.parents[2]

for search_path in (SERVER_DIR, REPO_ROOT):
    if str(search_path) not in sys.path:
        sys.path.insert(0, str(search_path))

from mcp_server.server import mcp  # pylint: disable=wrong-import-position


def main():
    """Run the MCP server via stdio."""
    mcp.run(show_banner=False, log_level="WARNING")


if __name__ == "__main__":
    # Run with stdio transport (default for MCP) without banner noise
    main()
