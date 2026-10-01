"""CPU-only geometry/mass tests of the actual offline producer."""
import importlib.util
import unittest
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("wood_metadata", Path(__file__).with_name("wood-metadata.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MetadataTests(unittest.TestCase):
    def field(self):
        value = np.zeros((8, 8, 8, 4), np.float32)
        value[..., 0] = 1
        return value

    def test_actual_materials_and_finite_mass(self):
        field = self.field()
        field[2:6, 2:6, 2:6] = [-.1, 1.5, .3, 1]
        field[2, 2, 2, 3] = 3  # inert chimney
        field[6, 2, 2] = [.04, .3, .3, 8]  # porous foliage
        field[6, 2, 3] = [.08, .3, .3, 8]  # outside thermal lamina
        metadata, stats = module.build_metadata(field)
        h = 3 / 8
        self.assertEqual(stats["woodDonors"], 63)
        self.assertEqual(stats["foliageDonors"], 1)
        self.assertEqual(metadata[2, 2, 2, 3], 0)
        self.assertEqual(metadata[6, 2, 3, 3], 0)
        self.assertAlmostEqual(stats["dryMassModelKg"], 495 * h ** 3 * 63.2, places=4)
        self.assertTrue(np.isfinite(metadata).all())
        np.testing.assert_allclose(metadata[6, 2, 2, :3], (np.array([2, 2, 6]) + .5) * h - 1.5)

    def test_nearest_destination_avoids_all_solid_materials(self):
        field = self.field()
        field[1:7, 1:7, 1:7] = [-.1, 1.5, .3, 1]
        field[1, 1, 1, 3] = 3
        metadata, _ = module.build_metadata(field)
        donors = metadata[..., 3] > 0
        index = np.rint((metadata[..., :3][donors] + 1.5) / (3 / 8) - .5).astype(int)
        self.assertTrue(np.all(field[index[:, 2], index[:, 1], index[:, 0], 0] > 0))

    def test_full_solid_grid_uses_actual_air_outside_bounds(self):
        field = self.field()
        field[:] = [-.1, 1.5, .3, 1]
        metadata, stats = module.build_metadata(field)
        self.assertEqual(stats["woodDonors"], 512)
        self.assertEqual(stats["outsideAssetDestinations"], 512)
        self.assertTrue(np.all(np.any(np.abs(metadata[..., :3]) > 1.5, axis=-1)))
        self.assertLessEqual(float(np.abs(metadata[..., :3]).max()), 1.5 + .5 * 3 / 8)

    def test_rejects_nonfinite_geometry(self):
        field = self.field()
        field[0, 0, 0, 0] = np.nan
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            module.build_metadata(field)


if __name__ == "__main__":
    unittest.main()
