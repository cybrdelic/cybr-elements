"""Bounded checks for selected-frame rerender integrity; no assets or Blender."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

from scripts import rerender_slice as slices


class FrameRangeTests(unittest.TestCase):
    def test_ranges_are_half_open_and_keep_original_frame_ids(self):
        self.assertEqual(slices.validate_range("water", 237, 240), [237, 238, 239])
        self.assertEqual(slices.validate_range("ice", 297, 300), [297, 298, 299])

    def test_full_water_and_other_film_limits(self):
        self.assertEqual(len(slices.validate_range("water", 0, 240)), 240)
        for kind in ("earth", "ice", "lava", "lightning"):
            with self.subTest(kind=kind):
                self.assertEqual(len(slices.validate_range(kind, 0, 300)), 300)

    def test_empty_reversed_negative_and_out_of_bounds_ranges_are_rejected(self):
        for kind, start, end in (("water", -1, 1), ("water", 0, 0),
                                 ("water", 10, 9), ("water", 239, 241),
                                 ("lightning", 0, 301), ("ice", 300, 301)):
            with self.subTest(kind=kind, start=start, end=end):
                with self.assertRaises((ValueError, RuntimeError)):
                    slices.validate_range(kind, start, end)


class FreshOutputTests(unittest.TestCase):
    def test_fresh_output_has_range_specific_name(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "nested" / "runs"
            output = slices.fresh_output(root, "ice", 95, 105)
            self.assertEqual(output, root / "ice-95-105")
            self.assertTrue(output.is_dir())
            self.assertEqual(list(output.iterdir()), [])

    def test_existing_empty_directory_can_be_used(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "water-0-10"
            expected.mkdir()
            self.assertEqual(slices.fresh_output(root, "water", 0, 10), expected)

    def test_any_existing_result_is_protected_without_modification(self):
        for name, contents in (("0000.jpg", b"original render"),
                               ("receipt.json", b'{"completed": false}')):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output = root / "lava-40-50"
                output.mkdir()
                existing = output / name
                existing.write_bytes(contents)
                with self.assertRaises((ValueError, RuntimeError)):
                    slices.fresh_output(root, "lava", 40, 50)
                self.assertEqual(existing.read_bytes(), contents)
                self.assertEqual(list(output.iterdir()), [existing])

    def test_stale_output_fails_before_asset_restore_or_simulation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "ice-95-105"
            output.mkdir()
            (output / "receipt.json").write_text("{}")
            argv = ["rerender_slice.py", "--kind", "ice", "--start", "95",
                    "--end", "105", "--output-root", str(root)]
            with mock.patch.object(sys, "argv", argv), \
                    mock.patch.object(slices.rerender_batch, "restore") as restore, \
                    mock.patch.object(slices, "produce") as produce:
                with self.assertRaises(RuntimeError):
                    slices.main()
            restore.assert_not_called()
            produce.assert_not_called()


class MaterialStageTests(unittest.TestCase):
    def test_frame_selection_is_applied_only_after_full_simulation(self):
        from argparse import Namespace

        for kind in ("ice", "lava", "lightning"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                args = Namespace(kind=kind, input_root=root / "inputs", threads=4,
                                 blender=root / "blender")
                with mock.patch.object(slices.rerender_batch, "checked") as checked, \
                        mock.patch.object(slices, "material_cache_hashes", return_value={"field": "sha"}):
                    images, hashes, _ = slices.produce(args, root / "run", [98, 99])
                calls = [call.args[0] for call in checked.call_args_list]
                self.assertEqual([command[2] for command in calls],
                                 ["prepare", "physics", "atmosphere", "render"])
                for command in calls[:3]:
                    self.assertNotIn("--frames", command)
                render = calls[-1]
                self.assertEqual(render[render.index("--frames") + 1], "98,99")
                self.assertEqual(render[render.index("--width") + 1], 1280)
                self.assertEqual(render[render.index("--height") + 1], 720)
                self.assertEqual(render[render.index("--samples") + 1],
                                 64 if kind == "lightning" else 24)
                self.assertEqual(render[render.index("--engine") + 1],
                                 "eevee" if kind == "lightning" else "cycles")
                self.assertIn("--native-vdb" if kind == "lightning" else "--atlas-volume", render)
                self.assertEqual(images, root / "run" / "materials" / kind / "frames")
                self.assertEqual(hashes, {"field": "sha"})


@unittest.skipUnless(importlib.util.find_spec("numpy"), "Array hashes require numpy")
class CanonicalArrayHashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np = np

    def test_equal_values_ignore_storage_order_and_strides(self):
        np = self.np
        values = np.arange(24, dtype=np.float32).reshape(4, 6)
        strided = np.zeros((4, 12), dtype=np.float32)
        strided[:, ::2] = values
        expected = slices.canonical_array_sha256(values)
        self.assertRegex(expected, r"^[0-9a-f]{64}$")
        self.assertEqual(slices.canonical_array_sha256(np.asfortranarray(values)), expected)
        self.assertEqual(slices.canonical_array_sha256(strided[:, ::2]), expected)

    def test_values_shape_and_dtype_are_part_of_array_identity(self):
        np = self.np
        values = np.arange(12, dtype=np.int32)
        expected = slices.canonical_array_sha256(values)
        changed = values.copy()
        changed[-1] += 1
        for other in (changed, values.reshape(3, 4), values.view(np.uint32),
                      values.astype(">i4")):
            with self.subTest(dtype=other.dtype, shape=other.shape):
                self.assertNotEqual(slices.canonical_array_sha256(other), expected)

    def test_object_arrays_are_rejected(self):
        with self.assertRaises((TypeError, ValueError)):
            slices.canonical_array_sha256(self.np.array([{"density": 1}], dtype=object))

    def test_npz_packaging_does_not_change_array_hashes(self):
        np = self.np
        positions = np.arange(12, dtype=np.float32).reshape(4, 3)
        density = np.array([.1, .5, .9], dtype=np.float64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stored, compressed, changed = (root / name for name in
                                           ("stored.npz", "compressed.npz", "changed.npz"))
            np.savez(stored, positions=positions, density=density)
            np.savez_compressed(compressed, density=density, positions=positions)
            self.assertNotEqual(stored.read_bytes(), compressed.read_bytes())
            expected = slices.npz_array_hashes(stored)
            self.assertEqual(set(expected), {"positions", "density"})
            self.assertEqual(slices.npz_array_hashes(compressed), expected)
            np.savez(changed, positions=positions, density=density + 1)
            changed_hashes = slices.npz_array_hashes(changed)
            self.assertEqual(changed_hashes["positions"], expected["positions"])
            self.assertNotEqual(changed_hashes["density"], expected["density"])


@unittest.skipUnless(importlib.util.find_spec("PIL"), "Frame checks require Pillow")
class FrameIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PIL import Image
        cls.Image = Image

    def write_frame(self, directory, frame, suffix="png", size=(1280, 720)):
        path = directory / f"{frame:04d}.{suffix}"
        self.Image.new("RGB", size, (16, 32, 64)).save(path)
        return path

    def test_only_selected_original_ids_are_required_and_metadata_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = {98: self.write_frame(root, 98, "jpg"),
                        99: self.write_frame(root, 99)}
            (root / "report.json").write_text("{}")
            self.assertEqual(slices.collect_frame_files(root, [98, 99]), expected)

    def test_missing_and_extra_frames_are_rejected(self):
        for present in ([98], [98, 99, 100]):
            with self.subTest(present=present), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for frame in present:
                    self.write_frame(root, frame)
                with self.assertRaises((ValueError, RuntimeError)):
                    slices.collect_frame_files(root, [98, 99])

    def test_duplicate_jpeg_and_png_for_one_id_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_frame(root, 98, "jpg")
            self.write_frame(root, 98, "png")
            with self.assertRaises((ValueError, RuntimeError)):
                slices.collect_frame_files(root, [98])

    def test_noncanonical_image_filenames_are_rejected(self):
        for name in ("98.png", "frame-0098.jpg", "000098.png"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.write_frame(root, 98)
                self.Image.new("RGB", (1280, 720)).save(root / name)
                with self.assertRaises((ValueError, RuntimeError)):
                    slices.collect_frame_files(root, [98])

    def test_resolution_must_be_exactly_720p(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_frame(root, 98, size=(1280, 719))
            with self.assertRaises((ValueError, RuntimeError)):
                slices.collect_frame_files(root, [98])

    def test_image_with_valid_header_but_truncated_pixels_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = self.write_frame(root, 98)
            data = path.read_bytes()
            path.write_bytes(data[:len(data) // 2])
            # Reading dimensions succeeds; validation must also decode pixel data.
            with self.Image.open(path) as image:
                self.assertEqual(image.size, (1280, 720))
            with self.assertRaises((ValueError, RuntimeError, OSError)):
                slices.collect_frame_files(root, [98])


if __name__ == "__main__":
    unittest.main()
