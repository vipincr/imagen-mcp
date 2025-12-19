"""Core image generation logic for the Imagen MCP server (standard library only)."""
from __future__ import annotations

import base64
import binascii
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import error, request

# Environment variable name for the Google AI API key
API_KEY_ENV = "GOOGLE_AI_API_KEY"

# Optional keyring fallback: when used via the VS Code extension, the key may be
# written to the OS keychain using python-keyring.
_DEFAULT_KEYRING_SERVICE = "imagen-mcp-vscode"
_DEFAULT_KEYRING_ACCOUNT = "GOOGLE_AI_API_KEY"

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


class _ModelState:  # pylint: disable=too-few-public-methods
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
    key = api_key or os.getenv(API_KEY_ENV)
    if key:
        return key

    # Best-effort keyring lookup (optional dependency).
    service = os.getenv("IMAGEN_MCP_KEYRING_SERVICE") or _DEFAULT_KEYRING_SERVICE
    account = os.getenv("IMAGEN_MCP_KEYRING_ACCOUNT") or _DEFAULT_KEYRING_ACCOUNT
    try:
        import keyring  # type: ignore
        from keyring.errors import KeyringError  # type: ignore
    except (ImportError, ModuleNotFoundError):
        return None

    try:
        stored = keyring.get_password(service, account)
    except KeyringError:
        return None

    if stored and stored.strip():
        return stored.strip()
    return None


def require_api_key(api_key: Optional[str] = None) -> str:
    """Get the API key from parameter, environment, or raise an error."""
    key = get_api_key(api_key)
    if not key:
        raise ValueError(
            f"Missing API key. Set the {API_KEY_ENV} environment variable, provide it in the MCP configuration, "
            "or store it in the OS keychain (via the VS Code extension)."
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


def _build_generation_config(
    *,
    aspect_ratio: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {
        **(generation_config or {}),
        "responseModalities": ["TEXT", "IMAGE"],
    }

    if aspect_ratio:
        image_cfg = cfg.setdefault("imageConfig", {})
        image_cfg["aspectRatio"] = aspect_ratio

    return cfg


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
        "generationConfig": _build_generation_config(
            aspect_ratio=aspect_ratio,
            generation_config=generation_config,
        ),
    }
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
        "generationConfig": _build_generation_config(
            aspect_ratio=aspect_ratio,
            generation_config=generation_config,
        ),
    }
    return body


def build_reference_request_body(
    prompt: str,
    reference_images: List[Tuple[str, str]],
    *,
    aspect_ratio: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the request body for generating an image using reference images.

    IMPORTANT: Reference images are provided as *visual inputs* to the model.
    Depending on your prompt, the model can:
    - Treat them as inspiration (style/composition/palette), OR
    - Recreate specific elements faithfully, OR
    - Include the referenced subject/object inside the generated scene
      (as-is or modified), as explicitly instructed.

    To help agents select the right tool, prompts should be explicit about
    whether the referenced content must be copied exactly ("keep identical")
    or may be modified ("change color", "add text", etc.).

    Args:
        prompt: Text description of the desired output and how to use references.
        reference_images: List of tuples (base64_data, mime_type). Up to 3.
        aspect_ratio: Optional aspect ratio for the output image.
        generation_config: Optional additional generation configuration.
    """
    if not prompt or not isinstance(prompt, str):
        raise ValueError("Prompt is required and must be a string.")
    if not reference_images or not isinstance(reference_images, list):
        raise ValueError("At least one reference image is required.")
    if len(reference_images) > 3:
        raise ValueError("A maximum of 3 reference images are supported.")

    parts: List[Dict[str, Any]] = [{"text": prompt}]
    for image_data, image_mime_type in reference_images:
        if not image_data or not isinstance(image_data, str):
            raise ValueError("Reference image data must be a base64-encoded string.")
        if not image_mime_type or not isinstance(image_mime_type, str):
            raise ValueError("Reference image mime type must be a string.")
        parts.append(
            {
                "inlineData": {
                    "mimeType": image_mime_type,
                    "data": image_data,
                }
            }
        )

    body: Dict[str, Any] = {
        "contents": [{"parts": parts}],
        "generationConfig": _build_generation_config(
            aspect_ratio=aspect_ratio,
            generation_config=generation_config,
        ),
    }
    return body


def _http_request_json(*, url: str, api_key: str, method: str, payload: Optional[Dict[str, Any]] = None,
                       timeout: int = 30) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        },
        method=method,
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            return json.loads(content.decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        raise RuntimeError(f"API error {exc.code}: {detail[:400]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def _http_get_json(url: str, api_key: str) -> Dict[str, Any]:
    """Make an HTTP GET request and return JSON response."""
    return _http_request_json(url=url, api_key=api_key, method="GET", timeout=30)


def _http_post_json(url: str, payload: Dict[str, Any], api_key: str) -> Dict[str, Any]:
    """Make an HTTP POST request and return JSON response."""
    return _http_request_json(url=url, api_key=api_key, method="POST", payload=payload, timeout=120)


def _generate_with_body(
    *,
    body: Dict[str, Any],
    model_id: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
) -> ImageResult:
    return _generate_image_from_body(body=body, model_id=model_id, base_url=base_url, api_key=api_key)


def _generate_image_from_body(
    *,
    body: Dict[str, Any],
    model_id: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
) -> ImageResult:
    """Shared implementation for image generation/editing requests."""
    effective_model = model_id or get_current_model()
    if not effective_model:
        raise ValueError(
            "No model selected. Use the 'set_image_model' tool to select a model first, "
            "or provide a model_id parameter."
        )

    response_json = _http_post_json(
        build_url(base_url=base_url, model_id=effective_model),
        body,
        require_api_key(api_key),
    )

    part = _extract_image_part(response_json)
    if not part:
        raise RuntimeError("No image part found in API response.")

    if part.get("data"):
        return ImageResult(
            buffer=_buffer_from_inline(part["data"]),
            mime_type=part.get("mimeType", DEFAULT_MIME_TYPE),
            response=response_json,
        )

    if part.get("fileUri") or part.get("url"):
        target_url = part.get("fileUri") or part.get("url")
        buffer, downloaded_mime = _http_get_bytes(target_url)
        return ImageResult(
            buffer=buffer,
            mime_type=downloaded_mime,
            response=response_json,
            source_url=target_url,
        )

    raise RuntimeError("Unsupported image format in API response.")


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
    except (binascii.Error, ValueError) as exc:
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


def _validate_dimensions(max_width: int, max_height: int) -> None:
    """Ensure provided dimensions are positive integers."""

    if not isinstance(max_width, int) or not isinstance(max_height, int):
        raise ValueError("max_width and max_height must be integers.")
    if max_width <= 0 or max_height <= 0:
        raise ValueError("max_width and max_height must be positive integers.")


def _resize_image_buffer(
    buffer: bytes,
    *,
    max_width: int,
    max_height: int,
    output_format: Optional[str] = None,
    quality: int = 85,
) -> Tuple[bytes, str]:
    """Resize/compress image bytes to fit within max dimensions and format.

    Uses Pillow; raises a friendly error if Pillow is missing.
    """
    _validate_dimensions(max_width, max_height)
    fmt = (output_format or "PNG").upper()
    if fmt == "JPG":
        fmt = "JPEG"

    try:
        from PIL import Image  # pylint: disable=import-outside-toplevel
    except Exception as exc:
        raise RuntimeError("Pillow is required for resizing. Install via requirements.txt") from exc

    q = quality if isinstance(quality, int) and 1 <= quality <= 100 else 85

    with Image.open(io.BytesIO(buffer)) as im:
        resample = getattr(Image, "Resampling", Image).LANCZOS  # type: ignore[attr-defined]
        im.thumbnail((max_width, max_height), resample)

        if fmt == "JPEG" and im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGB")

        save_params: Dict[str, Any] = {}
        if fmt == "JPEG":
            save_params["quality"] = q
            save_params["optimize"] = True
        elif fmt == "PNG":
            save_params["optimize"] = True
        elif fmt == "WEBP":
            save_params["quality"] = q

        output = io.BytesIO()
        im.save(output, format=fmt, **save_params)
        data = output.getvalue()
        mime = f"image/{fmt.lower()}"
        return data, mime



def _ensure_heif_registered() -> None:
    """Register HEIF opener when pillow-heif is available."""

    try:
        import pillow_heif  # type: ignore  # pylint: disable=import-outside-toplevel

        if not pillow_heif.is_registered_heif_opener():  # pragma: no cover
            pillow_heif.register_heif_opener()
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "HEIC/HEIF support requires pillow-heif. Install via requirements.txt."
        ) from exc


def _normalize_target_format(target_format: str) -> str:
    """Validate and normalize the desired output format."""

    fmt = target_format.lower().strip()
    valid = {"png", "jpeg", "jpg", "webp", "heic", "heif", "ico"}
    if fmt not in valid:
        raise ValueError(
            f"Unsupported format '{target_format}'. Choose from: {', '.join(sorted(valid))}."
        )
    return fmt


def _requires_heif_support(fmt: str, path_in: Path) -> bool:
    """Determine whether HEIF registration is needed for input/output."""

    return fmt in {"heic", "heif"} or path_in.suffix.lower() in {".heic", ".heif"}


def _validate_sizes_list(sizes: Optional[List[int]]) -> Optional[List[int]]:
    """Validate optional favicon sizes input."""

    if sizes is None:
        return None

    if not isinstance(sizes, list) or not all(isinstance(s, int) and s > 0 for s in sizes):
        raise ValueError("sizes must be a list of positive integers")

    return sorted(set(sizes))


def _coerce_target_fmt(fmt: str) -> str:
    """Normalize to Pillow-friendly format tokens."""

    return "JPEG" if fmt in {"jpeg", "jpg"} else fmt.upper()


def _build_frames_for_conversion(
    image: "Image.Image",
    target_fmt: str,
    sizes_list: Optional[List[int]],
    resample: Any,
) -> List["Image.Image"]:
    """Prepare frames for saving, handling ICO multi-size and JPEG alpha."""

    if target_fmt == "ICO" and sizes_list:
        frames = []
        for size in sizes_list:
            frame = image.copy()
            if frame.mode not in ("RGBA", "RGB", "L"):
                frame = frame.convert("RGBA")
            frames.append(frame.resize((size, size), resample))
        return frames

    if target_fmt == "JPEG" and image.mode in ("RGBA", "LA", "P"):
        return [image.convert("RGB")]

    return [image.copy()]


def _build_save_kwargs(target_fmt: str, sizes_list: Optional[List[int]]) -> Dict[str, Any]:
    """Choose Pillow save parameters based on target format."""

    if target_fmt == "JPEG":
        return {"quality": 90, "optimize": True}
    if target_fmt == "PNG":
        return {"optimize": True}
    if target_fmt == "WEBP":
        return {"quality": 90}
    if target_fmt == "ICO" and sizes_list:
        return {"sizes": [(s, s) for s in sizes_list]}
    return {}


def _target_mime(target_fmt: str) -> str:
    """Map Pillow format back to MIME type."""

    mime_map = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "ICO": "image/x-icon",
        "HEIC": "image/heic",
        "HEIF": "image/heif",
    }
    return mime_map.get(target_fmt, f"image/{target_fmt.lower()}")


def convert_image_format(
    *,
    input_path: str,
    output_path: str,
    target_format: str,
    sizes: Optional[List[int]] = None,
) -> Tuple[Path, str]:
    """Convert image to a new format; can emit multi-size ICO for favicons.

    - Supports png, jpeg/jpg, webp, heic/heif, ico.
    - For ICO, optional sizes list (e.g., [16, 32, 48, 64, 128]) will generate multi-res icon.
    - For HEIC output, pillow-heif must be installed.
    """
    fmt = _normalize_target_format(target_format)
    path_in = Path(input_path)
    if not path_in.exists():
        raise FileNotFoundError(f"Input image not found: {path_in}")

    if _requires_heif_support(fmt, path_in):
        _ensure_heif_registered()

    try:
        from PIL import Image  # pylint: disable=import-outside-toplevel
    except Exception as exc:
        raise RuntimeError("Pillow is required for image conversion. Install via requirements.txt.") from exc
    sizes_list = _validate_sizes_list(sizes)

    with Image.open(path_in) as image:
        target_fmt = _coerce_target_fmt(fmt)
        resample = getattr(Image, "Resampling", Image).LANCZOS  # type: ignore[attr-defined]
        frames = _build_frames_for_conversion(image, target_fmt, sizes_list, resample)

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        save_kwargs = _build_save_kwargs(target_fmt, sizes_list)
        frames[0].save(out_path, format=target_fmt, **save_kwargs)

    return out_path, _target_mime(target_fmt)


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
    return _generate_with_body(
        body=build_request_body(prompt, aspect_ratio=aspect_ratio, generation_config=generation_config),
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
    )


def generate_image_resized(
    *,
    prompt: str,
    max_width: int,
    max_height: int,
    aspect_ratio: Optional[str] = None,
    model_id: Optional[str] = None,
    output_format: Optional[str] = None,
    quality: int = 85,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
) -> ImageResult:  # pylint: disable=too-many-locals
    """Generate an image then resize/compress it to target bounds.

    Keeps a separate path from the high-res generator so callers can choose
    optimized output without losing the original behavior elsewhere.
    """

    original = generate_image(
        prompt=prompt,
        aspect_ratio=aspect_ratio,
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
        generation_config=generation_config,
    )

    resized_buffer, mime = _resize_image_buffer(
        original.buffer,
        max_width=max_width,
        max_height=max_height,
        output_format=output_format,
        quality=quality,
    )

    return ImageResult(
        buffer=resized_buffer,
        mime_type=mime,
        response=original.response,
        source_url=original.source_url,
    )


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
    result = _generate_with_body(
        body=build_edit_request_body(
            prompt,
            image_data,
            image_mime_type,
            aspect_ratio=aspect_ratio,
            generation_config=generation_config,
        ),
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
    )

    if not result.buffer:
        raise RuntimeError("No image part found in API response. The model may not have edited the image.")

    return result


def generate_image_with_references(
    *,
    prompt: str,
    reference_images: List[Tuple[str, str]],
    aspect_ratio: Optional[str] = None,
    model_id: Optional[str] = None,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
) -> ImageResult:
    """Generate an image using a prompt plus up to 3 reference images.

    Reference images are not limited to style guidance: the prompt can instruct
    the model to preserve and include a referenced object/subject inside the
    generated image (optionally with modifications).
    """
    return _generate_with_body(
        body=build_reference_request_body(
            prompt,
            reference_images,
            aspect_ratio=aspect_ratio,
            generation_config=generation_config,
        ),
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
    )


def generate_image_with_references_resized(  # pylint: disable=too-many-arguments
    *,
    prompt: str,
    reference_images: List[Tuple[str, str]],
    max_width: int,
    max_height: int,
    aspect_ratio: Optional[str] = None,
    model_id: Optional[str] = None,
    output_format: Optional[str] = None,
    quality: int = 85,
    base_url: str = DEFAULT_BASE_URL,
    api_key: Optional[str] = None,
    generation_config: Optional[Dict[str, Any]] = None,
) -> ImageResult:
    """Generate an image from prompt + references, then resize/compress."""
    original = generate_image_with_references(
        prompt=prompt,
        reference_images=reference_images,
        aspect_ratio=aspect_ratio,
        model_id=model_id,
        base_url=base_url,
        api_key=api_key,
        generation_config=generation_config,
    )

    resized_buffer, mime = _resize_image_buffer(
        original.buffer,
        max_width=max_width,
        max_height=max_height,
        output_format=output_format,
        quality=quality,
    )

    return ImageResult(
        buffer=resized_buffer,
        mime_type=mime,
        response=original.response,
        source_url=original.source_url,
    )


def write_image_to_file(buffer: bytes, target_path: "Path | str") -> Path:
    """Write image bytes to a file, creating directories as needed."""
    if not isinstance(buffer, (bytes, bytearray)):
        raise TypeError("Expected bytes for image buffer.")
    path = Path(target_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer)
    return path


# Public exports (include _state for test access)
__all__ = [name for name in globals() if not name.startswith("_")]
__all__.append("_state")
