"""Unit tests for core image generation utilities."""
# pylint: disable=missing-function-docstring

import base64
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from imagen_mcp import core


class ModelFallbackTests(unittest.TestCase):
    """Validate model selection fallback order."""
    def setUp(self):
        # Clear env for each test and reset model state
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        core._state._model_id = None  # type: ignore[attr-defined]  # pylint: disable=protected-access

    def tearDown(self):
        core._state._model_id = None  # type: ignore[attr-defined]  # pylint: disable=protected-access
        self.env_patch.stop()

    def test_default_model_used_when_none_configured(self):
        self.assertEqual(core.get_current_model(), core.DEFAULT_MODEL_ID)

    def test_env_overrides_default(self):
        os.environ["IMAGEN_MODEL_ID"] = "env-model"
        self.assertEqual(core.get_current_model(), "env-model")

    def test_runtime_overrides_env(self):
        os.environ["IMAGEN_MODEL_ID"] = "env-model"
        core.set_current_model("runtime-model")
        self.assertEqual(core.get_current_model(), "runtime-model")


class ImageGenerationTests(unittest.TestCase):
    """Unit tests for generation and editing helpers."""
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {core.API_KEY_ENV: "test-key"}, clear=True)
        self.env_patch.start()
        core._state._model_id = None  # type: ignore[attr-defined]  # pylint: disable=protected-access

    def tearDown(self):
        core._state._model_id = None  # type: ignore[attr-defined]  # pylint: disable=protected-access
        self.env_patch.stop()

    def _inline_response(self, mime_type: str, data_b64: str):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "inlineData": {
                                    "mimeType": mime_type,
                                    "data": data_b64,
                                }
                            }
                        ]
                    }
                }
            ]
        }

    @patch("imagen_mcp.core._http_post_json")
    def test_generate_image_uses_explicit_model(self, mock_post):
        data_b64 = base64.b64encode(b"pngdata").decode("utf-8")
        mock_post.return_value = self._inline_response("image/png", data_b64)

        result = core.generate_image(prompt="hello", model_id="explicit-model")

        called_url = mock_post.call_args[0][0]
        self.assertTrue(called_url.endswith("explicit-model:generateContent"))
        self.assertEqual(result.mime_type, "image/png")
        self.assertEqual(result.buffer, base64.b64decode(data_b64))

    @patch("imagen_mcp.core._http_post_json")
    def test_edit_image_sends_prompt_and_image(self, mock_post):
        data_b64 = base64.b64encode(b"pngdata").decode("utf-8")
        mock_post.return_value = self._inline_response("image/png", data_b64)

        image_b64 = base64.b64encode(b"imgbytes").decode("utf-8")
        result = core.edit_image(
            prompt="make it green",
            image_data=image_b64,
            image_mime_type="image/png",
            model_id="edit-model",
        )

        called_url, payload, _ = mock_post.call_args[0]
        self.assertTrue(called_url.endswith("edit-model:generateContent"))

        # Ensure payload contains prompt then inline image in order
        parts = payload["contents"][0]["parts"]
        self.assertEqual(parts[0]["text"], "make it green")
        self.assertIn("inlineData", parts[1])
        self.assertEqual(parts[1]["inlineData"]["data"], image_b64)

        self.assertEqual(result.buffer, base64.b64decode(data_b64))

    def test_read_image_file_validates_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(b"data")
            path = tmp.name
        try:
            data_b64, mime = core.read_image_file(path)
            self.assertEqual(mime, "image/png")
            self.assertEqual(base64.b64decode(data_b64), b"data")
        finally:
            os.remove(path)

    def test_read_image_file_unsupported_extension(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"data")
            path = tmp.name
        try:
            with self.assertRaises(ValueError):
                core.read_image_file(path)
        finally:
            os.remove(path)

    def test_read_image_file_missing(self):
        with self.assertRaises(FileNotFoundError):
            core.read_image_file("/nonexistent/image.png")


@unittest.skipUnless(os.getenv(core.API_KEY_ENV), "GOOGLE_AI_API_KEY not set; integration test skipped")
class ImageEditingIntegrationTests(unittest.TestCase):
    """Integration tests that hit the live Gemini image APIs."""
    red_apple_path: Path | None = None
    green_apple_path: Path | None = None

    def _out_dir(self) -> Path:
        out_dir = Path("test_output")
        out_dir.mkdir(exist_ok=True)
        return out_dir

    def _ts(self) -> str:
        # Include microseconds to avoid collisions across fast test runs.
        return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    def _png_size(self, buf: bytes):
        sig = b"\x89PNG\r\n\x1a\n"
        if not buf.startswith(sig) or len(buf) < 24:
            return None
        width = int.from_bytes(buf[16:20], "big")
        height = int.from_bytes(buf[20:24], "big")
        return width, height

    def _choose_model(self):
        models = core.list_available_models(image_only=True)
        target = next((m.name for m in models if m.name == "gemini-3-pro-image-preview"), None)
        return target or (models[0].name if models else None)

    def test_01_generate_and_edit_apple_color_only(self):
        model = self._choose_model()
        self.assertIsNotNone(model, "No image model available for integration test")
        core.set_current_model(model)

        out_dir = self._out_dir()
        ts = self._ts()

        # Generate red apple
        gen = core.generate_image(
            prompt="A photorealistic red apple on a white background, simple studio lighting"
        )
        self.assertGreater(len(gen.buffer), 0)
        red_png_size = self._png_size(gen.buffer)

        red_path = out_dir / f"red_apple_{ts}.png"
        core.write_image_to_file(gen.buffer, red_path)
        self.assertTrue(red_path.exists())
        self.__class__.red_apple_path = red_path

        # Edit apple to green without altering other attributes
        image_b64 = base64.b64encode(gen.buffer).decode("utf-8")
        edited = core.edit_image(
            prompt=("Change the apple to a green apple. Keep shape, size, texture, position, lighting, and background"
                    " identical; only change the color of the apple."),
            image_data=image_b64,
            image_mime_type=gen.mime_type,
        )

        self.assertGreater(len(edited.buffer), 0)
        self.assertEqual(edited.mime_type, gen.mime_type)
        self.assertNotEqual(edited.buffer, gen.buffer)

        green_path = out_dir / f"green_apple_{ts}.png"
        core.write_image_to_file(edited.buffer, green_path)
        self.assertTrue(green_path.exists())
        self.__class__.green_apple_path = green_path

        green_png_size = self._png_size(edited.buffer)
        if red_png_size and green_png_size:
            self.assertEqual(red_png_size, green_png_size)


    def test_02_generate_with_reference_apple_held_by_man(self):
        model = self._choose_model()
        self.assertIsNotNone(model, "No image model available for integration test")
        core.set_current_model(model)

        out_dir = self._out_dir()
        ts = self._ts()

        ref_path = self.__class__.red_apple_path
        if not ref_path or not ref_path.exists():
            gen = core.generate_image(
                prompt="A photorealistic red apple on a white background, simple studio lighting"
            )
            ref_path = out_dir / f"red_apple_{ts}.png"
            core.write_image_to_file(gen.buffer, ref_path)
            self.assertTrue(ref_path.exists())
            self.__class__.red_apple_path = ref_path

        ref_b64, ref_mime = core.read_image_file(ref_path)

        prompt = (
            "Generate a photorealistic image of a man holding the exact same red apple from the reference image. "
            "The apple must be identical in shape, size, texture, stem, lighting, highlights, shadows, and color; "
            "do not alter any details of the apple. Keep the apple exactly as-is; only add the man and his hand "
            "holding it naturally. Use a clean, simple studio background."
        )

        out = core.generate_image_with_references(
            prompt=prompt,
            reference_images=[(ref_b64, ref_mime)],
        )

        self.assertGreater(len(out.buffer), 0)
        out_path = out_dir / f"man_holding_same_apple_{ts}.png"
        core.write_image_to_file(out.buffer, out_path)
        self.assertTrue(out_path.exists())


    def test_03_generate_with_multiple_references_two_apples_held_by_man(self):
        model = self._choose_model()
        self.assertIsNotNone(model, "No image model available for integration test")
        core.set_current_model(model)

        out_dir = self._out_dir()
        ts = self._ts()

        red_path = self.__class__.red_apple_path
        green_path = self.__class__.green_apple_path

        if not red_path or not red_path.exists():
            gen = core.generate_image(
                prompt="A photorealistic red apple on a white background, simple studio lighting"
            )
            red_path = out_dir / f"red_apple_{ts}.png"
            core.write_image_to_file(gen.buffer, red_path)
            self.assertTrue(red_path.exists())
            self.__class__.red_apple_path = red_path

        if not green_path or not green_path.exists():
            red_b64, red_mime = core.read_image_file(red_path)
            edited = core.edit_image(
                prompt=(
                    "Change the apple to a green apple. Keep shape, size, texture, position, lighting, and background "
                    "identical; only change the color of the apple."
                ),
                image_data=red_b64,
                image_mime_type=red_mime,
            )
            green_path = out_dir / f"green_apple_{ts}.png"
            core.write_image_to_file(edited.buffer, green_path)
            self.assertTrue(green_path.exists())
            self.__class__.green_apple_path = green_path

        red_b64, red_mime = core.read_image_file(red_path)
        green_b64, green_mime = core.read_image_file(green_path)

        prompt = (
            "Generate a photorealistic image of a man holding TWO apples: the exact red apple from reference image 1 "
            "and the exact green apple from reference image 2. Each apple must be identical to its reference in "
            "shape, size, texture, stem, lighting, highlights, shadows, and color; do not alter any details of either "
            "apple. Only add the man and his hands holding them naturally. Use a clean, simple studio background."
        )

        out = core.generate_image_with_references(
            prompt=prompt,
            reference_images=[(red_b64, red_mime), (green_b64, green_mime)],
        )

        self.assertGreater(len(out.buffer), 0)
        out_path = out_dir / f"man_holding_red_and_green_apples_{ts}.png"
        core.write_image_to_file(out.buffer, out_path)
        self.assertTrue(out_path.exists())


    def test_04_generate_with_reference_style_only_no_apple_present(self):
        model = self._choose_model()
        self.assertIsNotNone(model, "No image model available for integration test")
        core.set_current_model(model)

        out_dir = self._out_dir()
        ts = self._ts()

        red_path = self.__class__.red_apple_path
        if not red_path or not red_path.exists():
            gen = core.generate_image(
                prompt="A photorealistic red apple on a white background, simple studio lighting"
            )
            red_path = out_dir / f"red_apple_{ts}.png"
            core.write_image_to_file(gen.buffer, red_path)
            self.assertTrue(red_path.exists())
            self.__class__.red_apple_path = red_path

        red_b64, red_mime = core.read_image_file(red_path)

        prompt = (
            "Use the reference image only to match the photography style (lighting, contrast, background cleanliness). "
            "Generate a photorealistic portrait of a man smiling, with a clean studio background and similar lighting. "
            "Do NOT include any apples or apple-like objects anywhere in the image."
        )

        out = core.generate_image_with_references(
            prompt=prompt,
            reference_images=[(red_b64, red_mime)],
        )

        self.assertGreater(len(out.buffer), 0)
        out_path = out_dir / f"style_reference_no_apple_{ts}.png"
        core.write_image_to_file(out.buffer, out_path)
        self.assertTrue(out_path.exists())


if __name__ == "__main__":
    unittest.main()
