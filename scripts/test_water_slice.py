"""Cheap validation and deterministic physical-cache hashing checks."""
import gzip
from pathlib import Path
import sys
import tempfile
import unittest

import water_slice


class WaterSliceTests(unittest.TestCase):
    def rejected_without_output(self, frames, message):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'fresh' / 'water'
            with self.assertRaisesRegex(ValueError, message):
                water_slice.render_water_slice(directory, output, frames, 4,
                                                'unused-blender', sys.executable)
            self.assertFalse(output.parent.exists())

    def test_out_of_range_frames_fail_before_creating_output(self):
        for frames in ([], [-1], [240], [0, 240]):
            with self.subTest(frames=frames):
                self.rejected_without_output(frames, 'inside 0..239')

    def test_duplicate_frames_fail_before_creating_output(self):
        for frames in ([0, 0], [0, 239, 0]):
            with self.subTest(frames=frames):
                self.rejected_without_output(frames, 'unique')

    def test_fractional_frames_are_rejected(self):
        for frames in ([0.5], [True], ['1']):
            with self.subTest(frames=frames):
                self.rejected_without_output(frames, 'integers')

    def test_gzip_hash_excludes_creation_time_and_compression(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = [Path(directory) / name for name in ('first.gz', 'second.gz')]
            payload = b'physical particle and mesh bytes' * 100
            first.write_bytes(gzip.compress(payload, compresslevel=1, mtime=1))
            second.write_bytes(gzip.compress(payload, compresslevel=9, mtime=99))
            self.assertNotEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(water_slice._gzip_hash(first), water_slice._gzip_hash(second))

    def test_velocity_hash_excludes_archive_order_but_detects_physical_changes(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('NumPy required for velocity cache check')
        with tempfile.TemporaryDirectory() as directory:
            first, second = [Path(directory) / name for name in ('first.npz', 'second.npz')]
            fields = {'surface': np.arange(6, dtype=np.float32).reshape(2, 3),
                      'drops': np.zeros((0, 3), dtype=np.float32),
                      'drop_positions': np.zeros((0, 3), dtype=np.float32)}
            np.savez_compressed(first, **fields)
            np.savez(second, **dict(reversed(list(fields.items()))))
            original = water_slice._velocity_hash(first)
            self.assertEqual(original, water_slice._velocity_hash(second))
            fields['surface'][0, 0] = 1
            np.savez(second, **fields)
            self.assertNotEqual(original, water_slice._velocity_hash(second))


if __name__ == '__main__':
    unittest.main()
