"""Core image generation logic for the Imagen MCP server.

This module provides:
- Image generation using Google's Gemini/Imagen models
- Dynamic model discovery and selection
- API key validation
- File I/O utilities for saving generated images

All functionality uses only Python standard library (no external HTTP libraries).
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

# Environment variable name for the Google AI API key
API_KEY_ENV = "GOOGLE_AI_API_KEY"

# Look for .env in the project root (parent directory of this file's parent)
DOTENV_CANDIDATES = [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[1] / ".env.local",
]

# Default settings
DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MIME_TYPE = "image/png"
# Default image model to use when none is provided or configured
DEFAULT_MODEL_ID = "gemini-3-pro-image-preview"

# Known image generation models (used for filtering)
# These models support image generation via responseModalities: ["IMAGE"]
IMAGE_GENERATION_MODEL_PATTERNS = [
    "gemini-2.0-flash-exp-image",
    "gemini-2.0-flash-preview-image",
    "gemini-2.5-flash-preview-image",
    "gemini-2.5-flash-image",
    "gemini-2.5-pro-exp-image",
    "gemini-3-pro-image",
    "imagen-3",
    "imagen-4",
    "image-generation",
]


@dataclass
class ImageResult:
    """Result of an image generation request."""
    buffer: bytes
    mime_type: str
    response: Dict[str, Any]
    source_url: Optional[str] = None


@dataclass
class ModelInfo:
    """Information about an available model."""
    name: str
    display_name: str
    description: str
    supported_generation_methods: List[str] = field(default_factory=list)
    input_token_limit: Optional[int] = None
    output_token_limit: Optional[int] = None


class _ModelState:
    """Internal state holder for the currently selected model."""
    
    __slots__ = ("_model_id",)
    
    def __init__(self) -> None:
        self._model_id: Optional[str] = None
    
    @property
    def current_model(self) -> Optional[str]:
        """Get the currently selected model, or default from environment."""
        return self._model_id or os.getenv("IMAGEN_MODEL_ID") or DEFAULT_MODEL_ID
    
    @current_model.setter
    def current_model(self, value: str) -> None:
        """Set the current model ID."""
        self._model_id = value


# Singleton state instance
_state = _ModelState()


def _prime_dotenv_env() -> None:
    """Load environment variables from .env files for local development."""
    for env_file in DOTENV_CANDIDATES:
        try:
            if not env_file.exists():
                continue
            for raw_line in env_file.read_text().splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, val = line.split("=", 1)
                name = name.strip()
                if not name or name in os.environ:
                    continue
                cleaned = val.strip().strip('"').strip("'")
                if cleaned:
                    os.environ[name] = cleaned
        except OSError:
            continue


# Auto-load .env/.env.local for developer convenience.
_prime_dotenv_env()


def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Get the API key from parameter or environment. Returns None if not set."""
    return api_key or os.getenv(API_KEY_ENV)


def require_api_key(api_key: Optional[str] = None) -> str:
    """Get the API key from parameter, environment, or raise an error."""
    key = get_api_key(api_key)
    if not key:
        raise ValueError(
            f"Missing API key. Set the {API_KEY_ENV} environment variable or provide it in the MCP configuration."
        )
    return key


def get_current_model() -> Optional[str]:
    """Get the currently selected model ID."""
    return _state.current_model


def set_current_model(model_id: str) -> None:
    """Set the current model ID to use for image generation."""
    _state.current_model = model_id


def build_url(*, base_url: str = DEFAULT_BASE_URL, model_id: str, stream: bool = False) -> str:
    """Build the API endpoint URL."""
    action = "streamGenerateContent" if stream else "generateContent"
    base = base_url.rstrip("/")
    return f"{base}/{model_id}:{action}"


def build_request_body(
    prompt: str,
    *,
    aspect_ratio: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build the request body for the Gemini API."""
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt is required and must be a string.")

    body: Dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            **(generation_config or {}),
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    if aspect_ratio:
        image_cfg = body["generationConfig"].setdefault("imageConfig", {})
        image_cfg["aspectRatio"] = aspect_ratio

    return body


def build_edit_request_body(
    prompt: str,
    image_data: str,
    image_mime_type: str = "image/png",
    *,
    aspect_ratio: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Build the request body for editing an existing image.
    
    Args:
        prompt: Text description of the edit to make.
        image_data: Base64-encoded image data.
        image_mime_type: MIME type of the image (e.g., "image/png", "image/jpeg").
        aspect_ratio: Optional aspect ratio for the output image.
        generation_config: Optional additional generation configuration.
    
    Returns:
        Dictionary containing the request body for the API.
    """
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt is required and must be a string.")
    if not image_data or not isinstance(image_data, str):
        raise ValueError("Image data is required and must be a base64-encoded string.")

    # For image editing, we send both the text prompt and the image
    # The order matters: prompt first, then image (as per Google's documentation)
    body: Dict[str, Any] = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": image_mime_type,
                        "data": image_data
                    }
                }
            ]
        }],
        "generationConfig": {
            **(generation_config or {}),
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    if aspect_ratio:
        image_cfg = body["generationConfig"].setdefault("imageConfig", {})
        image_cfg["aspectRatio"] = aspect_ratio

    return body


def _http_get_json(url: str, api_key: str) -> Dict[str, Any]:
    """Make an HTTP GET request and return JSON response."""
    req = request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="GET",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            return json.loads(content.decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"API error {exc.code}: {detail[:400]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def _http_post_json(url: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Make an HTTP POST request and return JSON response."""
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=120) as resp:
            content = resp.read()
            return json.loads(content.decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"API error {exc.code}: {detail[:400]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def _http_get_bytes(url: str) -> Tuple[bytes, str]:
    """Download bytes from a URL."""
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=60) as resp:
            content_type = resp.headers.get("content-type", DEFAULT_MIME_TYPE)
            return resp.read(), content_type
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"Download error {exc.code}: {detail[:200]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error downloading: {exc}") from exc


def _is_image_generation_model(model: Dict[str, Any]) -> bool:
    """Check if a model supports image generation based on its properties."""
    name = model.get("name", "").lower()
    
    # Check if the model name contains known image generation patterns
    for pattern in IMAGE_GENERATION_MODEL_PATTERNS:
        if pattern.lower() in name:
            return True
    
    # Check supported generation methods
    methods = model.get("supportedGenerationMethods", [])
    if "generateContent" in methods:
        # Models with generateContent that have "image" in the name
        if "image" in name or "imagen" in name:
            return True
    
    return False


def list_available_models(
    api_key: Optional[str] = None,
    image_only: bool = True,
) -> List[ModelInfo]:
    """List available models from the Google AI API.
    
    Args:
        api_key: Optional API key (uses environment variable if not provided).
        image_only: If True, only return models that support image generation.
    
    Returns:
        List of ModelInfo objects describing available models.
    """
    key = require_api_key(api_key)
    
    # The URL format for listing is the base models endpoint
    list_url = "https://generativelanguage.googleapis.com/v1beta/models"
    
    all_models: List[ModelInfo] = []
    page_token: Optional[str] = None
    
    while True:
        full_url = f"{list_url}?pageSize=100"
        if page_token:
            full_url += f"&pageToken={page_token}"
        
        try:
            response = _http_get_json(full_url, key)
        except RuntimeError as e:
            raise RuntimeError(f"Failed to list models: {e}") from e
        
        models = response.get("models", [])
        
        for model in models:
            # Filter for image generation models if requested
            if image_only and not _is_image_generation_model(model):
                continue
            
            # Extract model ID from the full name (e.g., "models/gemini-2.0-flash" -> "gemini-2.0-flash")
            full_name = model.get("name", "")
            model_id = full_name.replace("models/", "") if full_name.startswith("models/") else full_name
            
            model_info = ModelInfo(
                name=model_id,
                display_name=model.get("displayName", model_id),
                description=model.get("description", ""),
                supported_generation_methods=model.get("supportedGenerationMethods", []),
                input_token_limit=model.get("inputTokenLimit"),
                output_token_limit=model.get("outputTokenLimit"),
            )
            all_models.append(model_info)
        
        # Check for more pages
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    
    return all_models


def validate_api_key(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Validate an API key by attempting to list models.
    
    Args:
        api_key: The API key to validate.
    
    Returns:
        Dictionary with validation result and available models count.
    """
    try:
        key = require_api_key(api_key)
        models = list_available_models(api_key=key, image_only=False)
        image_models = [m for m in models if _is_image_generation_model({"name": f"models/{m.name}"})]
        
        return {
            "valid": True,
            "total_models": len(models),
            "image_models": len(image_models),
        }
    except ValueError as e:
        return {
            "valid": False,
            "error": str(e),
        }
    except RuntimeError as e:
        return {
            "valid": False,
            "error": f"API validation failed: {e}",
        }


def _extract_image_part(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract the image data from the API response."""
    candidates = payload.get("candidates") or []
    for candidate in candidates:
        parts = candidate.get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData") or {}
            if inline.get("data"):
                return {
                    "data": inline.get("data"),
                    "mimeType": inline.get("mimeType", DEFAULT_MIME_TYPE),
                    "source": "inlineData"
                }
            file_data = part.get("fileData") or {}
            if file_data.get("fileUri"):
                return {
                    "fileUri": file_data.get("fileUri"),
                    "mimeType": file_data.get("mimeType", DEFAULT_MIME_TYPE),
                    "source": "fileData"
                }
            if part.get("url"):
                return {
                    "url": part.get("url"),
                    "mimeType": part.get("mimeType", DEFAULT_MIME_TYPE),
                    "source": "url"
                }
    return None


def _buffer_from_inline(data: str) -> bytes:
    """Decode base64 image data."""
    try:
        return base64.b64decode(data)
    except Exception as exc:
        raise ValueError(f"Unable to decode image data: {exc}") from exc


def infer_extension(mime_type: str = DEFAULT_MIME_TYPE) -> str:
    """Get file extension from MIME type."""
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(mime_type.lower(), ".png")


def generate_image(
    *,
    prompt: str,
    aspect_ratio: Optional[str] = None,
    model_id: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
) -> ImageResult:
    """Generate an image using the Gemini API.
    
    Args:
        prompt: Text description of the image to generate.
        aspect_ratio: Optional aspect ratio (e.g., "1:1", "16:9", "9:16").
        model_id: Model identifier to use. If not provided, uses the current model.
        base_url: Base URL for the API.
        api_key: Optional API key (uses environment variable if not provided).
        generation_config: Optional additional generation configuration.
    
    Returns:
        ImageResult containing the image buffer, MIME type, and response data.
    
    Raises:
        ValueError: If no model is selected and none is provided.
        RuntimeError: If the API request fails.
    """
    # Get the model to use
    effective_model = model_id or get_current_model()
    if not effective_model:
        raise ValueError(
            "No model selected. Use the 'set_image_model' tool to select a model first, "
            "or provide a model_id parameter."
        )
    
    key = require_api_key(api_key)
    url = build_url(base_url=base_url, model_id=effective_model)
    body = build_request_body(prompt, aspect_ratio=aspect_ratio, generation_config=generation_config)

    response_json = _http_post_json(url, body, key)
    part = _extract_image_part(response_json)
    if not part:
        raise RuntimeError("No image part found in API response.")

    if part.get("data"):
        buffer = _buffer_from_inline(part["data"])
        return ImageResult(
            buffer=buffer,
            mime_type=part.get("mimeType", DEFAULT_MIME_TYPE),
            response=response_json
        )

    if part.get("fileUri") or part.get("url"):
        target_url = part.get("fileUri") or part.get("url")
        buffer, downloaded_mime = _http_get_bytes(target_url)
        return ImageResult(
            buffer=buffer,
            mime_type=downloaded_mime,
            response=response_json,
            source_url=target_url
        )

    raise RuntimeError("Unsupported image format in API response.")


def read_image_file(image_path: "Path | str") -> Tuple[str, str]:
    """Read an image file and return base64 data and MIME type.
    
    Args:
        image_path: Path to the image file.
    
    Returns:
        Tuple of (base64_data, mime_type).
    
    Raises:
        FileNotFoundError: If the image file doesn't exist.
        ValueError: If the file type is not supported.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")
    
    # Determine MIME type from extension
    ext_to_mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    
    ext = path.suffix.lower()
    if ext not in ext_to_mime:
        raise ValueError(f"Unsupported image format: {ext}. Supported: {', '.join(ext_to_mime.keys())}")
    
    mime_type = ext_to_mime[ext]
    image_bytes = path.read_bytes()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    
    return image_base64, mime_type


def edit_image(
    *,
    prompt: str,
    image_data: str,
    image_mime_type: str = "image/png",
    aspect_ratio: Optional[str] = None,
    model_id: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
) -> ImageResult:
    """Edit an existing image using the Gemini API.
    
    This function sends an image along with a text prompt describing the desired
    edit. The model will modify the image according to the prompt while trying
    to preserve other aspects of the original image.
    
    Args:
        prompt: Text description of the edit to make (e.g., "Change the apple to green").
        image_data: Base64-encoded image data.
        image_mime_type: MIME type of the image (e.g., "image/png", "image/jpeg").
        aspect_ratio: Optional aspect ratio for the output image.
        model_id: Model identifier to use. If not provided, uses the current model.
        base_url: Base URL for the API.
        api_key: Optional API key (uses environment variable if not provided).
        generation_config: Optional additional generation configuration.
    
    Returns:
        ImageResult containing the edited image buffer, MIME type, and response data.
    
    Raises:
        ValueError: If no model is selected and none is provided, or invalid input.
        RuntimeError: If the API request fails.
    """
    # Get the model to use
    effective_model = model_id or get_current_model()
    if not effective_model:
        raise ValueError(
            "No model selected. Use the 'set_image_model' tool to select a model first, "
            "or provide a model_id parameter."
        )
    
    key = require_api_key(api_key)
    url = build_url(base_url=base_url, model_id=effective_model)
    body = build_edit_request_body(
        prompt, 
        image_data, 
        image_mime_type,
        aspect_ratio=aspect_ratio, 
        generation_config=generation_config
    )

    response_json = _http_post_json(url, body, key)
    part = _extract_image_part(response_json)
    if not part:
        raise RuntimeError("No image part found in API response. The model may not have edited the image.")

    if part.get("data"):
        buffer = _buffer_from_inline(part["data"])
        return ImageResult(
            buffer=buffer,
            mime_type=part.get("mimeType", DEFAULT_MIME_TYPE),
            response=response_json
        )

    if part.get("fileUri") or part.get("url"):
        target_url = part.get("fileUri") or part.get("url")
        buffer, downloaded_mime = _http_get_bytes(target_url)
        return ImageResult(
            buffer=buffer,
            mime_type=downloaded_mime,
            response=response_json,
            source_url=target_url
        )

    raise RuntimeError("Unsupported image format in API response.")


def write_image_to_file(buffer: bytes, target_path: "Path | str") -> Path:
    """Write image bytes to a file, creating directories as needed."""
    if not isinstance(buffer, (bytes, bytearray)):
        raise TypeError("Expected bytes for image buffer.")
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer)
    return path
