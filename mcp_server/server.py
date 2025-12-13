"""Thin wrapper to shared server implementation."""
from __future__ import annotations

from image_generator import server as _server

__all__ = getattr(_server, "__all__", [])

mcp = _server.mcp


def __getattr__(name: str):
    return getattr(_server, name)
