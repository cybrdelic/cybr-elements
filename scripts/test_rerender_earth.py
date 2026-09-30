"""CPU-only tests for Earth render cache protection; no Blender installation."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

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


class EarthFilmSelectionTests(unittest.TestCase):
    def test_default_remains_full_300_frame_map(self):
        args = earth.arguments(["--mode", "full"])
        self.assertEqual(earth.output_frame_ids(args), list(range(300)))
        self.assertEqual(earth.scene_frames_for_output(earth.output_frame_ids(args)), set(range(211,391)))

    def test_selection_maps_first_join_release_and_last_indices(self):
        args = earth.arguments(["--mode", "full", "--skip-encode", "--film-frames", "299,154,153,121,120,0"])
        self.assertEqual(args.film_frames, [0,120,121,153,154,299])
        expected = {0: 331, 120: 211, 121: 212, 153: 244, 154: 245, 299: 390}
        for output_id, scene_frame in expected.items():
            self.assertEqual(earth.scene_frames_for_output([output_id]), {scene_frame})

    def test_shared_editorial_pose_is_rendered_once(self):
        args = earth.arguments(["--mode", "full", "--skip-encode", "--film-frames", "0,240"])
        self.assertEqual(earth.scene_frames_for_output(args.film_frames), {331})

    def test_invalid_selection_fails_before_inputs_or_output(self):
        for value in ("", " ", "0,,1", "0,", "-1", "300", "1,1", "1,01", "1.5", "nope"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "untouched"
                argv = ["earth", "--mode", "full", "--skip-encode", "--output", str(output), "--film-frames", value]
                with patch.object(earth.sys, "argv", argv), patch.object(earth, "preflight") as preflight:
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                        earth.main()
                    self.assertEqual(error.exception.code, 2)
                    preflight.assert_not_called()
                    self.assertFalse(output.exists())

    def test_selection_requires_full_mode_and_skip_encode(self):
        for flags in (["--film-frames", "0", "--skip-encode"], ["--mode", "full", "--film-frames", "0"]):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    earth.arguments(flags)
                self.assertEqual(error.exception.code, 2)

    def test_selected_preflight_reports_pose_deduplication_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "untouched"
            argv = ["earth", "--mode", "full", "--skip-encode", "--film-frames", "0,240,299",
                    "--preflight", "--output", str(output)]
            text = io.StringIO()
            with patch.object(earth.sys, "argv", argv), contextlib.redirect_stdout(text):
                with patch.object(earth, "preflight", return_value=(Path("source.py"), {}, 174)):
                    with patch.object(earth, "build_scene") as build:
                        earth.main()
                        build.assert_not_called()
            report = json.loads(text.getvalue())
            self.assertEqual(report["selectedOutputFrames"], [0,240,299])
            self.assertEqual(report["outputFrames"], 3)
            self.assertEqual(report["uniqueSourceFrames"], 2)
            self.assertFalse(output.exists())


class FakeVector(tuple):
    @property
    def z(self):
        return self[2]


class FakeMatrix:
    def __init__(self, frame):
        self.translation = FakeVector((float(frame), 0.0, 1.0))

    def __iter__(self):
        return iter(((1,0,0,self.translation[0]), (0,1,0,0), (0,0,1,1), (0,0,0,1)))

    def to_quaternion(self):
        return (1.0, 0.0, 0.0, 0.0)


class EarthSelectedRenderOrchestrationTests(unittest.TestCase):
    def run_fake_render(self, base, output_name, selected=None):
        output = base / output_name
        source = base / "scene.py"
        source.write_text("fixture source")
        frames_set = []
        rendered = []
        scene = SimpleNamespace(render=SimpleNamespace(filepath=""), current_frame=0)

        def set_frame(frame):
            scene.current_frame = frame
            frames_set.append(frame)

        def render(write_still):
            self.assertTrue(write_still)
            rendered.append(scene.current_frame)
            Path(scene.render.filepath).write_bytes(f"new pixels for scene frame {scene.current_frame}".encode())

        scene.frame_set = set_frame
        obj = SimpleNamespace(name="fixture rigid", rigid_body=SimpleNamespace(mass=1.0))
        obj.evaluated_get = lambda depsgraph: SimpleNamespace(matrix_world=FakeMatrix(scene.current_frame))
        bpy = SimpleNamespace(app=SimpleNamespace(version_string="4.5.3"),
                              context=SimpleNamespace(evaluated_depsgraph_get=lambda: None),
                              ops=SimpleNamespace(render=SimpleNamespace(render=render)))
        argv = ["earth", "--mode", "full", "--skip-encode", "--output", str(output)]
        if selected is not None:
            argv += ["--film-frames", selected]
        with patch.object(earth.sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            with patch.object(earth, "preflight", return_value=(source, {}, 174)):
                with patch.object(earth, "build_scene", return_value=(bpy, scene, [obj])):
                    with patch.object(earth, "encode") as encode:
                        earth.main()
                        encode.assert_not_called()
        return output, frames_set, rendered, json.loads((output / "render-report.json").read_text())

    def test_selection_runs_full_physics_and_keeps_final_frame_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            output, frames, rendered, report = self.run_fake_render(Path(directory), "selection", "0,240,299")
            self.assertEqual(frames, list(range(1,391)))
            self.assertEqual(rendered, [331,390])
            self.assertEqual({p.name for p in (output / "frames").iterdir()}, {"0000.png","0240.png","0299.png"})
            self.assertEqual((output / "frames/0000.png").read_bytes(), (output / "frames/0240.png").read_bytes())
            self.assertEqual((output / "frames/0299.png").read_bytes(), b"new pixels for scene frame 390")
            self.assertEqual(report["selectedOutputFrames"], [0,240,299])
            self.assertEqual(report["physicsFrames"], 390)
            self.assertTrue(report["selectionComplete"])
            self.assertFalse(report["complete"])
            self.assertNotIn("film", report)

    def test_default_still_writes_all300_and180_unique_poses(self):
        with tempfile.TemporaryDirectory() as directory:
            output, frames, rendered, report = self.run_fake_render(Path(directory), "full")
            self.assertEqual(frames, list(range(1,391)))
            self.assertEqual(rendered, list(range(211,391)))
            self.assertEqual({p.name for p in (output / "frames").iterdir()}, {f"{n:04d}.png" for n in range(300)})
            self.assertTrue(report["complete"])

    def test_selection_changes_neither_quality_settings_nor_physics_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            first, _, _, first_report = self.run_fake_render(base, "first", "0,240")
            last, _, _, last_report = self.run_fake_render(base, "last", "299")
            self.assertEqual(first_report["physicsTrajectorySha256"], last_report["physicsTrajectorySha256"])
            self.assertEqual(json.loads((first / "full-settings.json").read_text()),
                             json.loads((last / "full-settings.json").read_text()))

    def test_quaternion_sign_and_signed_zero_have_canonical_digest(self):
        first = FakeMatrix(1)
        second = FakeMatrix(1)
        second.translation = FakeVector((1.0, -0.0, 1.0))
        second.to_quaternion = lambda: (-1.0, -0.0, -0.0, -0.0)
        a, b = hashlib.sha256(), hashlib.sha256()
        earth.update_trajectory_digest(a, 1, [first])
        earth.update_trajectory_digest(b, 1, [second])
        self.assertEqual(a.hexdigest(), b.hexdigest())


if __name__ == "__main__":
    unittest.main()
