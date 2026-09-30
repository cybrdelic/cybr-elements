"""CPU-only tests for Earth render cache protection; no Blender installation."""
from pathlib import Path
import tempfile
import unittest

from scripts import rerender_earth as earth


class EarthRenderSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.images = self.output / "source-frames"
        self.images.mkdir()
        self.settings = {"engine": "cycles", "resolution": [1280, 720], "samples": 16}

    def tearDown(self):
        self.temp.cleanup()

    def test_same_settings_can_resume_existing_images(self):
        earth.ensure_render_settings(self.output, "full", self.images, self.settings)
        (self.images / "000240.png").write_bytes(b"already-rendered")
        earth.ensure_render_settings(self.output, "full", self.images, self.settings)
        self.assertEqual((self.images / "000240.png").read_bytes(), b"already-rendered")

    def test_engine_change_rejects_stale_images(self):
        earth.ensure_render_settings(self.output, "full", self.images, self.settings)
        changed = dict(self.settings, engine="eevee")
        with self.assertRaisesRegex(RuntimeError, "different render settings"):
            earth.ensure_render_settings(self.output, "full", self.images, changed)

    def test_quality_change_rejects_stale_images(self):
        earth.ensure_render_settings(self.output, "full", self.images, self.settings)
        for changed in (dict(self.settings, samples=32), dict(self.settings, resolution=[1920,1080])):
            with self.subTest(changed=changed):
                with self.assertRaisesRegex(RuntimeError, "different render settings"):
                    earth.ensure_render_settings(self.output, "full", self.images, changed)

    def test_unrecorded_existing_images_are_not_adopted(self):
        (self.images / "000240.png").write_bytes(b"unknown-render")
        with self.assertRaisesRegex(RuntimeError, "no settings receipt"):
            earth.ensure_render_settings(self.output, "full", self.images, self.settings)


if __name__ == "__main__":
    unittest.main()
