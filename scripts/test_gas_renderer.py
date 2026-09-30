"""Numerical regression checks for CPU execution of the original gas solvers.

Dependencies are optional for the ordinary repository checks. The dedicated
render workflow installs CPU PyTorch and runs these checks before rendering.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

_REQUIRED = ('torch', 'numpy', 'scipy', 'PIL')
_AVAILABLE = all(importlib.util.find_spec(name) for name in _REQUIRED)


@unittest.skipUnless(_AVAILABLE, 'Gas renderer checks require CPU PyTorch, NumPy, SciPy and Pillow')
class GasRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        import torch
        import torch.nn.functional as native
        import scripts.rerender_gas as renderer
        cls.np, cls.torch, cls.native, cls.renderer = np, torch, native, renderer
        torch.set_num_threads(2)

    def test_separable_limiter_matches_original_at_faces_edges_and_corners(self):
        torch = self.torch
        torch.manual_seed(11)
        values = torch.randn((1, 5, 10, 8, 12))
        for inputs in (values, -values):
            expected = self.native.max_pool3d(inputs, 3, stride=1, padding=1)
            actual = self.renderer.CPUFunctional().max_pool3d(inputs, 3, stride=1, padding=1)
            self.assertTrue(torch.equal(actual, expected))

    def _source(self, root, grid):
        np = self.np
        x, _, z = grid
        rows, columns = np.meshgrid(np.linspace(-1, 1, z), np.linspace(-1, 1, x), indexing='ij')
        sdf = (.65 - np.hypot(columns, rows)).astype('float32')
        arrival = (.3 + 1.6 * (columns + 1)).astype('float32')
        direction = (columns + .3).astype('float32')
        fields = {'support': np.clip(sdf / .2 + .5, 0, 1), 'sdf': sdf, 'arrival': arrival,
                  'dirx': np.cos(direction), 'dirz': np.sin(direction),
                  'lo': np.array([-7., -.6, -1.05]), 'extent': np.array([14., 1.2, 7.875])}
        path = root / 'sigil-02-v2/source.npz'
        path.parent.mkdir()
        np.savez_compressed(path, **fields)
        return path

    def test_channel_specialization_preserves_full_solver_state(self):
        from argparse import Namespace
        torch = self.torch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            grid = [12, 8, 10]
            source = self._source(root, grid)
            base = dict(repo=Path(__file__).resolve().parents[1], source=source, output=root, grid=grid,
                        fps=30, frames=5, substeps=3, threads=2, resolution=[1280, 720], save_every=30)
            for kind in ('fire', 'air'):
                a = Namespace(**base, kind=kind, native_transport=True)
                original, _ = self.renderer.load_solver(a)
                original['F'] = self.native
                a.native_transport = False
                optimized, _ = self.renderer.load_solver(a)
                torch.manual_seed(17)
                initial = original['state'].clone()
                initial[:, :3] = torch.randn_like(initial[:, :3]) * 100
                if kind == 'fire':
                    initial[:, 3] = torch.rand_like(initial[:, 3]) * .5
                    initial[:, 4] = torch.rand_like(initial[:, 4])
                    initial[:, 5] = torch.rand_like(initial[:, 5]) * .5
                    initial[:, 6] = torch.rand_like(initial[:, 6]) * .1
                    initial[:, 7] = torch.rand_like(initial[:, 7]) * 500
                else:
                    initial[:, 6] = torch.rand_like(initial[:, 6]) * .3
                original['state'], optimized['state'] = initial.clone(), initial.clone()
                for time in (.03, .84, 3.9, 7.3):
                    divergence_original = original['step'](time)
                    divergence_optimized = optimized['step'](time)
                    with self.subTest(element=kind, time=time):
                        self.assertTrue(torch.equal(original['state'], optimized['state']))
                        self.assertTrue(torch.equal(original['state'].view(torch.int32), optimized['state'].view(torch.int32)))
                        self.assertEqual(divergence_original, divergence_optimized)
                        self.assertTrue(bool(torch.isfinite(optimized['state']).all()))

    def test_source_resampling_preserves_world_bounds_and_rejects_nonfinite_data(self):
        from argparse import Namespace
        np = self.np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self._source(root, [32, 8, 18])
            output = root / 'output'
            output.mkdir()
            a = Namespace(grid=[16, 8, 10], source=source, output=output)
            destination = output / 'resampled.npz'
            original_checksum = self.renderer.checksum(source)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                self.renderer.resample_source(a, source)
            self.assertEqual(self.renderer.checksum(source), original_checksum)
            report = self.renderer.resample_source(a, destination)
            with np.load(destination) as resampled:
                self.assertEqual(resampled['support'].shape, (10, 16))
                self.assertTrue(np.array_equal(resampled['lo'], [-7., -.6, -1.05]))
                self.assertTrue(np.array_equal(resampled['extent'], [14., 1.2, 7.875]))
                self.assertTrue(np.isfinite(resampled['arrival']).all())
            self.assertEqual(report['sha256_original'], self.renderer.checksum(source))
            with np.load(source) as original:
                fields = {name: original[name].copy() for name in original.files}
            fields['arrival'][0, 0] = np.nan
            np.savez_compressed(source, **fields)
            with self.assertRaisesRegex(ValueError, 'nonfinite'):
                self.renderer.resample_source(a, destination)


if __name__ == '__main__':
    unittest.main()
