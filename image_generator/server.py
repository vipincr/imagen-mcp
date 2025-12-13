"""MCP Server for Google AI image generation.

This server exposes image generation capabilities to AI agents via MCP.
It provides tools for generating, editing, and saving images using Google's Gemini API.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import List, Optional

from fastmcp import FastMCP

from .core import (
    API_KEY_ENV,
    ImageResult,
    edit_image,
    generate_image,
    generate_image_resized,
    generate_image_with_references,
    generate_image_with_references_resized,
    convert_image_format,
    get_api_key,
    get_current_model,
    infer_extension,
    list_available_models,
    read_image_file,
    set_current_model,
    validate_api_key,
    write_image_to_file,
)

# Create the MCP server instance (logging configured at run-time to avoid deprecation)
mcp = FastMCP("Imagen - Google AI Image Generator")


def _model_used(model: Optional[str]) -> str:
    return model or get_current_model()


def _encode_image_result(result: ImageResult, *, model: Optional[str], extra: Optional[dict] = None) -> dict:
    image_base64 = base64.b64encode(result.buffer).decode("utf-8")
    payload = {
        "success": True,
        "image_base64": image_base64,
        "mime_type": result.mime_type,
        "extension": infer_extension(result.mime_type),
        "size_bytes": len(result.buffer),
        "model_used": _model_used(model),
    }
    if extra:
        payload.update(extra)
    return payload


def _save_image_result(
    result: ImageResult,
    *,
    output_path: str,
    model: Optional[str],
    extra: Optional[dict] = None,
) -> dict:
    path = Path(output_path)
    if not path.suffix:
        path = path.with_suffix(infer_extension(result.mime_type))

    saved_path = write_image_to_file(result.buffer, path)
    payload = {
        "success": True,
        "saved_path": str(saved_path.absolute()),
        "mime_type": result.mime_type,
        "size_bytes": len(result.buffer),
        "model_used": _model_used(model),
    }
    if extra:
        payload.update(extra)
    return payload


def _handle_image_result(
    result: ImageResult,
    *,
    model: Optional[str],
    output_path: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Return an encoded response or save the image, based on output_path."""
    if output_path:
        return _save_image_result(result, output_path=output_path, model=model, extra=extra)
    return _encode_image_result(result, model=model, extra=extra)


def _wrap_tool(fn):
    """Execute a tool handler and normalize common error handling."""
    try:
        return fn()
    except (ValueError, RuntimeError, OSError, FileNotFoundError) as exc:  # noqa: PERF203 safe surface errors
        return {"success": False, "error": str(exc)}



def _call_with_aspect_ratio_fallback(fn, *, aspect_ratio: Optional[str], **kwargs):
    if not aspect_ratio:
        return fn(**kwargs)

    try:
        return fn(aspect_ratio=aspect_ratio, **kwargs)
    except RuntimeError as exc:
        if "Aspect ratio is not enabled" in str(exc):
            return fn(**kwargs)
        raise


def _read_reference_images(reference_paths: List[str]):
    if not reference_paths or not isinstance(reference_paths, list):
        raise ValueError("reference_paths must be a non-empty list of 1-3 paths.")
    if len(reference_paths) > 3:
        raise ValueError("A maximum of 3 reference images are supported.")

    return [read_image_file(p) for p in reference_paths]


@mcp.tool()
def list_image_models() -> dict:
    """List available image generation models from Google AI.

    This tool queries the Google AI API to retrieve a list of models that support
    image generation. Use this to discover which models are available for your API key.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the operation succeeded
        - models: List of available image generation models (if successful)
        - current_model: The currently selected model (if any)
        - error: Error message (if failed)
    """
    try:
        models = list_available_models(image_only=True)
        current = get_current_model()

        model_list = [
            {
                "name": m.name,
                "display_name": m.display_name,
                "description": m.description[:200] + "..." if len(m.description) > 200 else m.description,
            }
            for m in models
        ]

        return {
            "success": True,
            "models": model_list,
            "current_model": current,
            "count": len(model_list),
        }
    except (ValueError, RuntimeError, OSError) as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def set_image_model(model_name: str) -> dict:
    """Set the model to use for image generation.

    This tool sets the active model for subsequent image generation requests.
    Use 'list_image_models' first to see available models.

    Args:
        model_name: The name/ID of the model to use (e.g., "gemini-2.0-flash-exp-image-generation").

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the operation succeeded
        - model: The model that was set (if successful)
        - error: Error message (if failed)
    """
    try:
        if not model_name or not isinstance(model_name, str):
            return {
                "success": False,
                "error": "Model name is required and must be a string.",
            }

        # Set the model
        set_current_model(model_name.strip())

        return {
            "success": True,
            "model": model_name.strip(),
            "message": f"Model set to '{model_name.strip()}'. Ready for image generation.",
        }
    except (ValueError, TypeError) as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def get_current_image_model() -> dict:
    """Get the currently selected image generation model.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the operation succeeded
        - model: The currently selected model (may be None)
        - api_key_configured: Whether an API key is configured
    """
    try:
        current = get_current_model()
        has_key = get_api_key() is not None

        return {
            "success": True,
            "model": current,
            "api_key_configured": has_key,
            "message": f"Current model: {current or 'None (use set_image_model to select one)'}",
        }
    except (ValueError, RuntimeError) as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def generate_image_from_prompt(
    prompt: str,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Generate an image using Google AI (Gemini/Imagen).

    This tool generates images based on text prompts using Google's AI models.
    Make sure to set a model first using 'set_image_model' or provide one here.

    Args:
        prompt: A detailed text description of the image to generate.
                Be specific about style, lighting, composition, and subject matter.
                Example: "A serene mountain landscape at sunset with vibrant orange and purple sky"
        aspect_ratio: Optional aspect ratio for the generated image.
                     Supported values: "1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
                     Note: Not all models support all aspect ratios.
        model: Optional model to use. If not provided, uses the currently selected model.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if generation succeeded
        - image_base64: Base64-encoded image data (if successful)
        - mime_type: MIME type of the image (e.g., "image/png")
        - extension: Suggested file extension (e.g., ".png")
        - size_bytes: Size of the image in bytes
        - model_used: The model that was used for generation
        - error: Error message (if failed)
    """
    return _wrap_tool(
        lambda: _handle_image_result(
            _call_with_aspect_ratio_fallback(
                generate_image,
                aspect_ratio=aspect_ratio,
                prompt=prompt,
                model_id=model,
            ),
            model=model,
        )
    )


@mcp.tool()
def generate_image_resized_from_prompt(
    prompt: str,
    max_width: int,
    max_height: int,
    *,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
    format: Optional[str] = None,  # pylint: disable=redefined-builtin
    quality: Optional[int] = 85,
) -> dict:
    """Generate an image, then resize/compress it to the target bounds.
    Keeps high-res generation separate from optimized output flows.
    """
    return _wrap_tool(
        lambda: _handle_image_result(
            generate_image_resized(
                prompt=prompt,
                max_width=max_width,
                max_height=max_height,
                aspect_ratio=aspect_ratio,
                model_id=model,
                output_format=format,
                quality=quality if quality is not None else 85,
            ),
            model=model,
            extra={
                "resized": True,
                "max_width": max_width,
                "max_height": max_height,
            },
        )
    )


@mcp.tool()
def generate_and_save_image_resized(
    prompt: str,
    output_path: str,
    max_width: int,
    max_height: int,
    *,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
    format: Optional[str] = None,  # pylint: disable=redefined-builtin
    quality: Optional[int] = 85,
) -> dict:
    """Generate an image, resize/compress it, and save to disk.

    This avoids overwriting the high-res save path and keeps optimized output separate.
    """
    return _wrap_tool(
        lambda: _handle_image_result(
            generate_image_resized(
                prompt=prompt,
                max_width=max_width,
                max_height=max_height,
                aspect_ratio=aspect_ratio,
                model_id=model,
                output_format=format,
                quality=quality if quality is not None else 85,
            ),
            model=model,
            output_path=output_path,
            extra={
                "resized": True,
                "max_width": max_width,
                "max_height": max_height,
            },
        )
    )


@mcp.tool()
def convert_image(
    input_path: str,
    output_path: str,
    format: str,  # pylint: disable=redefined-builtin
    sizes: Optional[List[int]] = None,
) -> dict:
    """Convert image to another format; supports multi-size ICO for favicons.

    Formats: png, jpeg/jpg, webp, heic/heif, ico. For ICO you can pass sizes like [16,32,48,64,128].
    """
    try:
        out_path, mime = convert_image_format(
            input_path=input_path,
            output_path=output_path,
            target_format=format,
            sizes=sizes,
        )
        return {
            "success": True,
            "saved_path": str(out_path.absolute()),
            "mime_type": mime,
            "sizes": sizes,
            "format": format,
        }
    except (ValueError, RuntimeError, OSError, FileNotFoundError) as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def save_image_to_file(
    image_base64: str,
    output_path: str,
) -> dict:
    """Save a base64-encoded image to a file.

    This tool saves image data (typically from generate_image_from_prompt) to the filesystem.
    It will create any necessary parent directories.

    Args:
        image_base64: Base64-encoded image data from generate_image_from_prompt.
        output_path: Absolute or relative path where the image should be saved.
                    Include the file extension (e.g., "/path/to/image.png").
                    Parent directories will be created if they don't exist.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if save succeeded
        - saved_path: Absolute path where the image was saved (if successful)
        - size_bytes: Size of the saved file in bytes
        - error: Error message (if failed)
    """
    try:
        # Decode base64 to bytes
        image_buffer = base64.b64decode(image_base64)

        # Write to file
        saved_path = write_image_to_file(image_buffer, output_path)

        return {
            "success": True,
            "saved_path": str(saved_path.absolute()),
            "size_bytes": len(image_buffer),
        }
    except (ValueError, TypeError, OSError) as e:
        return {
            "success": False,
            "error": str(e),
        }


@mcp.tool()
def generate_and_save_image(
    prompt: str,
    output_path: str,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Generate an image and save it to a file in one operation.

    This is a convenience tool that combines generate_image_from_prompt and
    save_image_to_file into a single call. Use this when you know the
    destination path upfront.

    Args:
        prompt: A detailed text description of the image to generate.
                Be specific about style, lighting, composition, and subject matter.
        output_path: Absolute or relative path where the image should be saved.
                    Include the file extension (e.g., "/path/to/image.png").
                    Parent directories will be created if they don't exist.
        aspect_ratio: Optional aspect ratio for the generated image.
                     Supported values: "1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
        model: Optional model to use. If not provided, uses the currently selected model.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the operation succeeded
        - saved_path: Absolute path where the image was saved (if successful)
        - mime_type: MIME type of the generated image
        - size_bytes: Size of the image in bytes
        - model_used: The model that was used for generation
        - error: Error message (if failed)
    """
    return _wrap_tool(
        lambda: _handle_image_result(
            _call_with_aspect_ratio_fallback(
                generate_image,
                aspect_ratio=aspect_ratio,
                prompt=prompt,
                model_id=model,
            ),
            model=model,
            output_path=output_path,
        )
    )


@mcp.tool()
def edit_image_from_file(
    input_path: str,
    prompt: str,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Edit an existing image using a text prompt.

    This tool reads an image from the filesystem and applies edits based on
    the text prompt. The model will attempt to modify only the specified
    aspects while preserving the rest of the image.

    Args:
        input_path: Path to the existing image file to edit.
                   Supported formats: PNG, JPEG, WebP, GIF.
        prompt: A detailed description of the edit to make.
                Be specific about what should change and what should stay the same.
                Example: "Change the color of the apple from red to green, keeping
                everything else exactly the same including the shape and lighting."
        aspect_ratio: Optional aspect ratio for the output image.
                     Supported values: "1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
        model: Optional model to use. If not provided, uses the currently selected model.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the edit succeeded
        - image_base64: Base64-encoded edited image data (if successful)
        - mime_type: MIME type of the image (e.g., "image/png")
        - extension: Suggested file extension (e.g., ".png")
        - size_bytes: Size of the image in bytes
        - model_used: The model that was used for editing
        - error: Error message (if failed)
    """
    def _run():
        image_base64, image_mime_type = read_image_file(input_path)
        result: ImageResult = _call_with_aspect_ratio_fallback(
            edit_image,
            aspect_ratio=aspect_ratio,
            prompt=prompt,
            image_data=image_base64,
            image_mime_type=image_mime_type,
            model_id=model,
        )
        return _handle_image_result(result, model=model)

    return _wrap_tool(_run)


@mcp.tool()
def edit_and_save_image(
    input_path: str,
    prompt: str,
    output_path: str,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Edit an existing image and save the result to a file.

    This is a convenience tool that combines edit_image_from_file and
    save_image_to_file into a single call. Use this when you know the
    destination path upfront.

    Args:
        input_path: Path to the existing image file to edit.
                   Supported formats: PNG, JPEG, WebP, GIF.
        prompt: A detailed description of the edit to make.
                Be specific about what should change and what should stay the same.
                Example: "Change the color of the apple from red to green, keeping
                everything else exactly the same including the shape and lighting."
        output_path: File path to save the edited image.
                    Include the file extension (e.g., "/path/to/edited.png").
                    Parent directories will be created if they don't exist.
        aspect_ratio: Optional aspect ratio for the output image.
                     Supported values: "1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"
        model: Optional model to use. If not provided, uses the currently selected model.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the operation succeeded
        - saved_path: Absolute path where the edited image was saved (if successful)
        - mime_type: MIME type of the edited image
        - size_bytes: Size of the image in bytes
        - model_used: The model that was used for editing
        - error: Error message (if failed)
    """
    def _run():
        image_base64, image_mime_type = read_image_file(input_path)
        result: ImageResult = _call_with_aspect_ratio_fallback(
            edit_image,
            aspect_ratio=aspect_ratio,
            prompt=prompt,
            image_data=image_base64,
            image_mime_type=image_mime_type,
            model_id=model,
        )
        return _handle_image_result(result, model=model, output_path=output_path)

    return _wrap_tool(_run)


@mcp.tool()
def generate_image_with_references_from_files(
    reference_paths: List[str],
    prompt: str,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Generate an image using a prompt plus up to 3 reference images from disk.

    IMPORTANT: reference images are *visual inputs* to the model.
    Use this tool when the prompt needs to:
    - Preserve a referenced object/subject and include it in the output scene (as-is), OR
    - Include it but with specified modifications, OR
    - Use references for style/composition inspiration.

    Prompts should clearly specify whether referenced content must be identical
    ("do not change any details") or may be modified.
    """
    def _run():
        refs = _read_reference_images(reference_paths)
        result: ImageResult = _call_with_aspect_ratio_fallback(
            generate_image_with_references,
            aspect_ratio=aspect_ratio,
            prompt=prompt,
            reference_images=refs,
            model_id=model,
        )
        return _handle_image_result(
            result,
            model=model,
            extra={"reference_count": len(reference_paths)},
        )

    return _wrap_tool(_run)


@mcp.tool()
def generate_image_with_references_resized_from_files(
    reference_paths: List[str],
    prompt: str,
    max_width: int,
    max_height: int,
    *,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
    format: Optional[str] = None,  # pylint: disable=redefined-builtin
    quality: Optional[int] = 85,
) -> dict:
    """Generate an image with references, then resize/compress to target bounds.

    Use this when you need the referenced content to be used as actual visual
    input (potentially included as-is) and also need optimized output size.
    """
    def _run():
        refs = _read_reference_images(reference_paths)
        result: ImageResult = generate_image_with_references_resized(
            prompt=prompt,
            reference_images=refs,
            max_width=max_width,
            max_height=max_height,
            aspect_ratio=aspect_ratio,
            model_id=model,
            output_format=format,
            quality=quality if quality is not None else 85,
        )
        return _handle_image_result(
            result,
            model=model,
            extra={
                "resized": True,
                "max_width": max_width,
                "max_height": max_height,
                "reference_count": len(reference_paths),
            },
        )

    return _wrap_tool(_run)


@mcp.tool()
def generate_and_save_image_with_references(
    reference_paths: List[str],
    prompt: str,
    output_path: str,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """Generate an image with references and save it to a file.

    This is the convenience variant for workflows where references must be used
    as visual inputs and the output needs to be written to disk.
    """
    def _run():
        refs = _read_reference_images(reference_paths)
        result: ImageResult = _call_with_aspect_ratio_fallback(
            generate_image_with_references,
            aspect_ratio=aspect_ratio,
            prompt=prompt,
            reference_images=refs,
            model_id=model,
        )
        return _handle_image_result(
            result,
            model=model,
            output_path=output_path,
            extra={"reference_count": len(reference_paths)},
        )

    return _wrap_tool(_run)


@mcp.tool()
def generate_and_save_image_with_references_resized(
    reference_paths: List[str],
    prompt: str,
    output_path: str,
    max_width: int,
    max_height: int,
    *,
    aspect_ratio: Optional[str] = None,
    model: Optional[str] = None,
    format: Optional[str] = None,  # pylint: disable=redefined-builtin
    quality: Optional[int] = 85,
) -> dict:
    """Generate an image with references, resize/compress it, and save to disk."""
    def _run():
        refs = _read_reference_images(reference_paths)
        result: ImageResult = generate_image_with_references_resized(
            prompt=prompt,
            reference_images=refs,
            max_width=max_width,
            max_height=max_height,
            aspect_ratio=aspect_ratio,
            model_id=model,
            output_format=format,
            quality=quality if quality is not None else 85,
        )
        return _handle_image_result(
            result,
            model=model,
            output_path=output_path,
            extra={
                "resized": True,
                "max_width": max_width,
                "max_height": max_height,
                "reference_count": len(reference_paths),
            },
        )

    return _wrap_tool(_run)


@mcp.tool()
def check_api_status() -> dict:
    """Check if the Google AI API key is configured and valid.

    This tool validates the API configuration by attempting to list available models.
    Use this to verify your setup before generating images.

    Returns:
        A dictionary containing:
        - success: Boolean indicating if the check succeeded
        - api_key_configured: Whether an API key is set
        - api_key_valid: Whether the API key is valid (if configured)
        - total_models: Total number of models available
        - image_models: Number of image generation models available
        - current_model: The currently selected model
        - error: Error message (if check failed)
    """
    try:
        has_key = get_api_key() is not None
        current = get_current_model()

        if not has_key:
            return {
                "success": True,
                "api_key_configured": False,
                "api_key_valid": False,
                "current_model": current,
                "message": f"No API key configured. Set the {API_KEY_ENV} environment variable.",
            }

        # Validate the key
        validation = validate_api_key()

        if validation.get("valid"):
            return {
                "success": True,
                "api_key_configured": True,
                "api_key_valid": True,
                "total_models": validation.get("total_models", 0),
                "image_models": validation.get("image_models", 0),
                "current_model": current,
                "message": "API key is valid and working.",
            }

        return {
            "success": True,
            "api_key_configured": True,
            "api_key_valid": False,
            "current_model": current,
            "error": validation.get("error", "Unknown validation error"),
        }
    except (ValueError, RuntimeError, OSError) as e:
        return {
            "success": False,
            "error": str(e),
        }


# Entry point for running the server
if __name__ == "__main__":
    mcp.run()


__all__ = [name for name in globals() if not name.startswith("_")]
