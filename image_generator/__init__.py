"""Imagen MCP Server - Google AI Image Generation.

This package provides an MCP server for generating images using Google's
Gemini and Imagen models.
"""

from .core import (
    ImageResult,
    ModelInfo,
    edit_image,
    generate_image,
    get_current_model,
    infer_extension,
    list_available_models,
    read_image_file,
    set_current_model,
    validate_api_key,
    write_image_to_file,
)
from .server import mcp

__all__ = [
    "mcp",
    "edit_image",
    "generate_image",
    "get_current_model",
    "infer_extension",
    "list_available_models",
    "read_image_file",
    "set_current_model",
    "validate_api_key",
    "write_image_to_file",
    "ImageResult",
    "ModelInfo",
]

__version__ = "1.0.0"
