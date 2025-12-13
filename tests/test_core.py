import base64
import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import image_generator.core as core


class ModelFallbackTests(unittest.TestCase):
    def setUp(self):
        # Clear env for each test and reset model state
        self.env_patch = patch.dict(os.environ, {}, clear=True)
        self.env_patch.start()
        core._state._model_id = None  # type: ignore[attr-defined]

    def tearDown(self):
        core._state._model_id = None  # type: ignore[attr-defined]
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
    def setUp(self):
        self.env_patch = patch.dict(os.environ, {core.API_KEY_ENV: "test-key"}, clear=True)
        self.env_patch.start()
        core._state._model_id = None  # type: ignore[attr-defined]

    def tearDown(self):
        core._state._model_id = None  # type: ignore[attr-defined]
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

    @patch("image_generator.core._http_post_json")
    def test_generate_image_uses_explicit_model(self, mock_post):
        data_b64 = base64.b64encode(b"pngdata").decode("utf-8")
        mock_post.return_value = self._inline_response("image/png", data_b64)

        result = core.generate_image(prompt="hello", model_id="explicit-model")

        called_url = mock_post.call_args[0][0]
        self.assertTrue(called_url.endswith("explicit-model:generateContent"))
        self.assertEqual(result.mime_type, "image/png")
        self.assertEqual(result.buffer, base64.b64decode(data_b64))

    @patch("image_generator.core._http_post_json")
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

    def test_generate_and_edit_apple_color_only(self):
        model = self._choose_model()
        self.assertIsNotNone(model, "No image model available for integration test")
        core.set_current_model(model)

        out_dir = Path("test_output")
        out_dir.mkdir(exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")

        # Generate red apple
        gen = core.generate_image(
            prompt="A photorealistic red apple on a white background, simple studio lighting"
        )
        self.assertGreater(len(gen.buffer), 0)
        red_png_size = self._png_size(gen.buffer)

        red_path = out_dir / f"red_apple_{ts}.png"
        core.write_image_to_file(gen.buffer, red_path)
        self.assertTrue(red_path.exists())

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

        green_png_size = self._png_size(edited.buffer)
        if red_png_size and green_png_size:
            self.assertEqual(red_png_size, green_png_size)


if __name__ == "__main__":
    unittest.main()
