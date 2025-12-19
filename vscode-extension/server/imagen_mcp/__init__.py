"""Imagen MCP Server - Google AI Image Generation.

This package provides an MCP server for generating images using Google's
Gemini and Imagen models.
"""

from .core import (
    API_KEY_ENV,
    DEFAULT_MODEL_ID,
    ImageResult,
    ModelInfo,
    convert_image_format,
    edit_image,
    generate_image,
    generate_image_resized,
    generate_image_with_references,
    generate_image_with_references_resized,
    get_api_key,
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
    "API_KEY_ENV",
    "DEFAULT_MODEL_ID",
    "ImageResult",
    "ModelInfo",
    "convert_image_format",
    "edit_image",
    "generate_image",
    "generate_image_resized",
    "generate_image_with_references",
    "generate_image_with_references_resized",
    "get_api_key",
    "get_current_model",
    "infer_extension",
    "list_available_models",
    "mcp",
    "read_image_file",
    "set_current_model",
    "validate_api_key",
    "write_image_to_file",
]

__version__ = "1.0.0"

