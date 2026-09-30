"""Bounded checks for worker supervision, portable inputs and sparse liquid."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work" / "element-motion"


def module_from_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = module_from_file("water_runner", WORK / "sigil_02_active_water_run.py")


class SupervisionTests(unittest.TestCase):
    def test_fast_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "revision"
            with self.assertRaisesRegex(RuntimeError, "sim exited 7"):
                runner.supervise([("sim", [sys.executable, "-c", "raise SystemExit(7)"])],
                                 output, minimum_free_bytes=0, poll_interval=.01)
            self.assertTrue((output / "sim.log").exists())

    def test_success_requires_every_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            commands = [(name, [sys.executable, "-c", f"print({name!r})"])
                        for name in ("sim", "mesh", "render")]
            runner.supervise(commands, output, minimum_free_bytes=0, poll_interval=.01)
            for name, _ in commands:
                self.assertEqual((output / f"{name}.log").read_text().strip(), name)

    def test_timeout_reaps_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "timeout"):
                runner.supervise([("sim", [sys.executable, "-c", "import time; time.sleep(60)"])],
                                 output, minimum_free_bytes=0, timeout=.05, poll_interval=.01)
            pid = json.loads((output / "processes.json").read_text())["sim"]
            if sys.platform != "win32":
                import os
                with self.assertRaises(ChildProcessError):
                    os.waitpid(pid, os.WNOHANG)

    def test_failed_launch_reaps_started_workers(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                runner.supervise([
                    ("sim", [sys.executable, "-c", "import time; time.sleep(60)"]),
                    ("mesh", [str(Path(directory) / "missing-executable")]),
                ], Path(directory), minimum_free_bytes=0)


class PreflightTests(unittest.TestCase):
    def fixture(self, root):
        inputs = root / "inputs"
        force = root / "force"
        inputs.mkdir()
        force.mkdir()
        config = dict(forceRoot="../force", sourceRoot="../force", h=.05, spaceScale=.35,
                      timeScale=.4, nx=8, ny=8, nz=8, frames=2,
                      origin=[.2, .05, .2], extent=[.4, .4, .4], releaseAt=5)
        (inputs / "config.json").write_text(json.dumps(config))
        (inputs / "parcels.f32").write_bytes(struct.pack("<9f", 0, 0, 0, .18, .25, .18, 0, 0, 0))
        (inputs / "guides.npz").write_bytes(b"test")
        for axis in range(3):
            (force / f"guide-{axis}.f32").write_bytes(bytes(9**3 * 8))
        return argparse.Namespace(full=False, input_root=inputs, output=root / "fresh",
                                  force_root=None, node=sys.executable, blender=sys.executable)

    def test_relative_inputs_and_new_revision_are_portable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = self.fixture(root)
            plan = runner.make_plan(args)
            self.assertEqual(plan["config"]["forceRoot"], str(root / "force"))
            self.assertFalse(args.output.exists())
            runner.prepare_inputs(plan)
            self.assertEqual((args.output / "parcels.f32").read_bytes(), (args.input_root / "parcels.f32").read_bytes())
            self.assertEqual(json.loads((args.output / "config.json").read_text())["forceRoot"], str(root / "force"))
            self.assertTrue(all("--output" in command for _, command in plan["commands"]))

    def test_missing_inputs_fail_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            (args.input_root / "guides.npz").unlink()
            with self.assertRaisesRegex(ValueError, "fetch_assets.py --all"):
                runner.make_plan(args)
            self.assertFalse(args.output.exists())

    def test_existing_particle_revision_is_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            (args.output / "particles").mkdir(parents=True)
            (args.output / "particles" / "manifest.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "fresh --output"):
                runner.make_plan(args)

    def test_unavailable_tool_reports_configuration_option(self):
        with self.assertRaisesRegex(ValueError, "--blender"):
            runner.resolve_tool("definitely-no-cybr-blender-executable", "Blender")

    def test_malformed_config_fails_before_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            path = args.input_root / "config.json"
            config = json.loads(path.read_text())
            config["spaceScale"] = 0
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, "spaceScale"):
                runner.make_plan(args)
            self.assertFalse(args.output.exists())

    def test_force_grid_size_is_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            (Path(directory) / "force" / "guide-1.f32").write_bytes(b"wrong")
            with self.assertRaisesRegex(ValueError, "dimensions"):
                runner.make_plan(args)


class RenderCliTests(unittest.TestCase):
    def test_runner_rejects_nonpositive_render_values_before_creating_output(self):
        for flag, value in (("--width", "0"), ("--height", "-1"), ("--samples", "0"), ("--threads", "-2")):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "fresh"
                result = subprocess.run([sys.executable, str(WORK / "sigil_02_active_water_run.py"),
                                         flag, value, "--output", str(output)], capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 2)
                self.assertIn("must be positive", result.stderr)
                self.assertFalse(output.exists())

    def test_renderer_rejects_invalid_settings_without_loading_blender(self):
        for flags in (("--width", "0"), ("--height", "-1"), ("--samples", "0"),
                      ("--threads", "-1"), ("--device", "invalid")):
            with self.subTest(flags=flags), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "frames"
                result = subprocess.run([sys.executable, str(WORK / "sigil_02_active_water_render.py"),
                                         "--", *flags, "--render-output", str(output)], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Invalid render dimensions", result.stderr)
                self.assertNotIn("No module named 'bpy'", result.stderr)
                self.assertFalse(output.exists())

    def test_out_of_range_selected_frames_fail_before_creating_output(self):
        for frames in ("-1", "3", "0,3"):
            with self.subTest(frames=frames), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "mesh").mkdir()
                (root / "mesh" / "manifest.json").write_text(json.dumps({"config": {"frames": 3}}))
                output = root / "rendered"
                result = subprocess.run([sys.executable, str(WORK / "sigil_02_active_water_render.py"), "--",
                                         "--output", str(root), "--frames", frames, "--render-output", str(output)],
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Selected frames must lie inside", result.stderr)
                self.assertFalse(output.exists())

    def test_duplicate_selected_frames_are_rejected_before_loading_blender(self):
        for frames in ('0,0', '0,1,0'):
            with self.subTest(frames=frames), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'mesh').mkdir()
                (root / 'mesh' / 'manifest.json').write_text(json.dumps({'config': {'frames': 3}}))
                output = root / 'rendered'
                result = subprocess.run([sys.executable, str(WORK / 'sigil_02_active_water_render.py'), '--',
                                         '--output', str(root), '--frames', frames, '--render-output', str(output)],
                                        capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('Selected frames must be unique', result.stderr)
                self.assertNotIn("No module named 'bpy'", result.stderr)
                self.assertFalse(output.exists())

    def test_render_overrides_reach_the_renderer_without_changing_solver_grid(self):
        with tempfile.TemporaryDirectory() as directory:
            args = PreflightTests.fixture(self, Path(directory))
            args.width, args.height, args.samples, args.threads, args.device = 1280, 720, 32, 6, "cpu"
            plan = runner.make_plan(args)
            render_command = dict(plan['commands'])['render']
            for flag, value in (("--width", "1280"), ("--height", "720"), ("--samples", "32"),
                                ("--threads", "6"), ("--device", "cpu")):
                self.assertEqual(render_command[render_command.index(flag) + 1], value)
            self.assertEqual(plan['config']['nx'], 8)
            self.assertEqual(plan['config']['h'], .05)


@unittest.skipUnless(shutil.which("node"), "Native solver smoke check requires Node")
class NativeSolverTests(unittest.TestCase):
    fixture = PreflightTests.fixture

    def test_tiny_forward_solve_is_finite_and_conserves_parcels(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            plan = runner.make_plan(args)
            runner.prepare_inputs(plan)
            result = subprocess.run([shutil.which("node"), str(WORK / "sigil_02_active_water.mjs"),
                                     "--output", str(args.output), "--force-root", str(Path(directory) / "force")],
                                    text=True, capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((args.output / "particles" / "manifest.json").read_text())
            self.assertTrue(manifest["complete"])
            self.assertEqual(len(manifest["frames"]), 2)
            for frame in manifest["frames"]:
                self.assertTrue(frame["finite"])
                self.assertTrue(frame["pressure"]["converged"])
                self.assertEqual(frame["particles"], 1)
                self.assertAlmostEqual(frame["sourceVolumeBalance"], 0)

    def test_explicit_missing_force_root_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            result = subprocess.run([shutil.which("node"), str(WORK / "sigil_02_active_water.mjs"),
                                     "--output", str(args.input_root), "--force-root", str(Path(directory) / "missing")],
                                    text=True, capture_output=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(str(Path(directory) / "missing"), result.stderr)
            self.assertFalse((args.input_root / "particles").exists())

    def test_offline_mode_retains_every_frame_without_a_consumer(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            config_path = args.input_root / "config.json"
            config = json.loads(config_path.read_text())
            config['frames'] = 12
            config_path.write_text(json.dumps(config))
            result = subprocess.run([shutil.which('node'), str(WORK / 'sigil_02_active_water.mjs'),
                                     '--full', '--offline', '--output', str(args.input_root),
                                     '--force-root', str(Path(directory) / 'force')],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((args.input_root / 'particles' / 'manifest.json').read_text())
            self.assertTrue(manifest['complete'])
            self.assertEqual(len(list((args.input_root / 'particles').glob('*.gz'))), 12)

    def test_streamed_mode_waits_at_its_cache_bound_without_a_consumer(self):
        with tempfile.TemporaryDirectory() as directory:
            args = self.fixture(Path(directory))
            config_path = args.input_root / 'config.json'
            config = json.loads(config_path.read_text())
            config['frames'] = 12
            config_path.write_text(json.dumps(config))
            process = subprocess.Popen([shutil.which('node'), str(WORK / 'sigil_02_active_water.mjs'),
                                        '--full', '--output', str(args.input_root),
                                        '--force-root', str(Path(directory) / 'force')],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                deadline = time.monotonic() + 5
                while len(list((args.input_root / 'particles').glob('*.gz'))) < 10 and time.monotonic() < deadline:
                    if process.poll() is not None:
                        self.fail('Streamed solver exited before reaching its cache bound')
                    time.sleep(.02)
                time.sleep(.05)
                self.assertIsNone(process.poll())
                self.assertEqual(len(list((args.input_root / 'particles').glob('*.gz'))), 10)
                manifest = json.loads((args.input_root / 'particles' / 'manifest.json').read_text())
                self.assertFalse(manifest.get('complete', False))
                self.assertEqual(len(manifest['frames']), 10)
            finally:
                process.terminate()
                process.wait(timeout=5)


@unittest.skipUnless(importlib.util.find_spec("numpy"), "Sparse reconstruction checks require numpy")
class SparseLiquidTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.mesher = module_from_file("active_mesh", WORK / "sigil_02_active_mesh.py")

    def test_empty_frame_has_well_formed_droplet_arrays(self):
        np = self.np
        empty = np.empty((0, 3), np.float32)
        positions, radii, velocities = self.mesher.small_particle_droplets(empty, empty, .032)
        self.assertEqual(positions.shape, (0, 3))
        self.assertEqual(velocities.shape, (0, 3))
        self.assertEqual(radii.shape, (0,))

    def test_sparse_droplets_preserve_positions_velocities_and_liquid_volume(self):
        np = self.np
        positions = np.array([[1, 2, 3], [2, 3, 4]], np.float32)
        velocities = np.array([[.2, -.5, .3], [.1, -.2, .7]], np.float32)
        h = .032
        drops, radii, drop_velocities = self.mesher.small_particle_droplets(positions, velocities, h)
        np.testing.assert_array_equal(drops, positions)
        np.testing.assert_array_equal(drop_velocities, velocities)
        volume = float((4 * np.pi / 3 * radii.astype(np.float64)**3).sum())
        self.assertAlmostEqual(volume, len(positions) * (h / 2)**3, delta=volume * 1e-6)
        drops[0, 0] = 100
        self.assertEqual(positions[0, 0], 1)

    def test_nonfinite_liquid_is_rejected(self):
        np = self.np
        positions = np.array([[0, np.nan, 0]], np.float32)
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            self.mesher.small_particle_droplets(positions, np.zeros((1, 3)), .032)

    def test_large_isolated_frame_preserves_every_primary_parcel(self):
        np = self.np
        count = 2049
        positions = np.arange(count * 3, dtype=np.float32).reshape(count, 3) * .1
        velocities = np.random.default_rng(5).normal(size=(count, 3)).astype(np.float32)

        class UnsupportedReconstructor:
            previous_iso = 1.8

            def reconstruct(self, positions, velocities, history, obstacles, dt):
                self.parcels_received = len(positions)
                self.isolated = np.ones(len(positions), bool)
                raise RuntimeError('Liquid field has insufficient support')

        reconstructor = UnsupportedReconstructor()
        result = self.mesher.reconstruct_or_droplets(reconstructor, positions, velocities,
                                                   np.zeros((count, 6), np.float32), 1 / 30, .032)
        _, _, vertices, normals, faces, drops, radii, drop_velocities, iso, measure = result
        self.assertEqual(reconstructor.parcels_received, count)
        self.assertEqual(vertices.shape, (0, 3))
        self.assertEqual(normals.shape, (0, 3))
        self.assertEqual(faces.shape, (0, 3))
        np.testing.assert_array_equal(drops, positions)
        np.testing.assert_array_equal(drop_velocities, velocities)
        self.assertTrue(reconstructor.isolated.all())
        self.assertEqual(iso, 1.8)
        self.assertEqual(measure['fallbackReason'], 'insufficient-field-support')
        self.assertEqual(measure['renderedSubgridDrops'], count)
        self.assertAlmostEqual(measure['renderedDropVolume'], count * (.032 / 2)**3,
                               delta=measure['renderedDropVolume'] * 1e-6)

    def test_unrelated_reconstruction_error_is_not_masked(self):
        np = self.np

        class BrokenReconstructor:
            def reconstruct(self, *args):
                raise RuntimeError('Invalid liquid field dimensions')

        with self.assertRaisesRegex(RuntimeError, 'Invalid liquid field dimensions'):
            self.mesher.reconstruct_or_droplets(BrokenReconstructor(), np.zeros((2049, 3)),
                                               np.zeros((2049, 3)), np.zeros((2049, 6)), 1 / 30, .032)


@unittest.skipUnless(importlib.util.find_spec("numpy") and importlib.util.find_spec("scipy"),
                     "Fourier projection checks require numpy and scipy")
class GasProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np
        cls.projector_module = module_from_file("gas_projection", WORK / "gas_projection.py")

    def test_even_grid_projection_removes_real_divergence(self):
        np = self.np
        projector = self.projector_module.FourierProjector((16, 12, 10), (.1, .12, .2))
        velocity = np.random.default_rng(42).normal(size=(3, 16, 12, 10))
        before = np.linalg.norm(projector.divergence(velocity))
        projected = projector.project(velocity)
        after = np.linalg.norm(projector.divergence(projected))
        self.assertLess(after / before, 1e-12)
        self.assertLessEqual(float(np.sum(projected**2)), float(np.sum(velocity**2)) + 1e-8)
        np.testing.assert_allclose(projector.project(projected), projected, atol=1e-13)

    def test_odd_grid_highest_mode_is_projected(self):
        np = self.np
        shape = (7, 9, 11)
        projector = self.projector_module.FourierProjector(shape, (1, 1, 1))
        velocity = np.zeros((3, *shape))
        velocity[0] = np.sin(2 * np.pi * 3 * np.arange(7)[:, None, None] / 7)
        self.assertGreater(np.linalg.norm(projector.divergence(velocity)), 1)
        self.assertLess(np.linalg.norm(projector.divergence(projector.project(velocity))), 1e-12)

    def test_float32_projection_retains_precision_and_uniform_flow(self):
        np = self.np
        projector = self.projector_module.FourierProjector((8, 8, 8), (1, 1, 1))
        uniform = np.ones((3, 8, 8, 8), np.float32)
        np.testing.assert_array_equal(projector.project(uniform), uniform)
        velocity = np.random.default_rng(1).normal(size=uniform.shape).astype(np.float32)
        projected = projector.project(velocity)
        self.assertEqual(projected.dtype, np.float32)
        self.assertLess(np.linalg.norm(projector.divergence(projected)) /
                        np.linalg.norm(projector.divergence(velocity)), 1e-6)

    def test_nonfinite_field_is_rejected(self):
        np = self.np
        projector = self.projector_module.FourierProjector((8, 8, 8), (1, 1, 1))
        velocity = np.zeros((3, 8, 8, 8))
        velocity[0, 0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "finite"):
            projector.project(velocity)


if __name__ == "__main__":
    unittest.main()
