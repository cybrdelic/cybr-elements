"""Unit tests and numerical execution of the real archived gas source on CPU."""
import ast
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flow

FIXTURE = """
import torch
if not torch.cuda.is_available(): raise RuntimeError('CUDA required')
device='cuda'
torch.set_num_threads(2)
def advect(q, v): return q + v * 0.125
def step(t): return t * 3.4
def radiance(): return 1.05
FPS=30
TOTAL=294
encoder=unsafe_production_encoder()
def render(frame):
    return radiance() + frame
for frame in range(TOTAL): render(frame)
"""


class AdapterTests(unittest.TestCase):
    def test_gas_preserves_functions(self):
        code, report = flow.gas_program(FIXTURE, 1)
        import torch
        namespace = {}
        exec(code, namespace)
        self.assertEqual(namespace['device'], 'cpu')
        self.assertNotIn('encoder', namespace)
        self.assertNotIn('TOTAL', namespace)
        self.assertEqual(namespace['step'](2), 6.8)
        self.assertEqual(namespace['render'](1), 2.05)
        self.assertTrue(report['productionFunctionsIdenticalBeforeExplicitPreviewResize'])

    def test_unsupported_cuda_fails_closed(self):
        text = FIXTURE.replace("device='cuda'", "device='cuda'\ntorch.cuda.set_device(0)")
        with self.assertRaisesRegex(RuntimeError, 'Unadapted CUDA'):
            flow.gas_program(text)

    def test_nontrivial_guard_is_not_removed(self):
        text = FIXTURE.replace("if not torch.cuda.is_available(): raise RuntimeError('CUDA required')",
                               "if not torch.cuda.is_available():\n    important_physics()\n    raise RuntimeError('CUDA')")
        with self.assertRaisesRegex(RuntimeError, 'Unrecognized CUDA guard'):
            flow.gas_program(text)

    def test_missing_boundary_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'FPS boundary'):
            flow.gas_program('def render(frame): pass')

    def test_missing_renderer_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'render'):
            flow.gas_program('FPS=30')

    def test_numerical_cuda_change_rejected(self):
        text = FIXTURE.replace('return t * 3.4', 'return torch.cuda.memory_allocated() + t * 3.4')
        with self.assertRaisesRegex(RuntimeError, 'protected production function'):
            flow.gas_program(text)

    def test_cycles_adaptation(self):
        tree = ast.parse("s.cycles.device='GPU' if full else 'CPU'\ns.cycles.denoiser='OPTIX'\ns.render.engine='BLENDER_EEVEE_NEXT'\nprefs.compute_device_type='OPTIX'\nfor d in prefs.devices: d.use=d.type=='OPTIX'\nbpy.ops.render.render(write_still=True)")
        changed = ast.unparse(flow.CPUAdapter().visit(tree))
        self.assertNotIn("'GPU'", changed)
        self.assertNotIn("'OPTIX'", changed)
        self.assertIn('OPENIMAGEDENOISE', changed)
        self.assertIn('_cpu_render(write_still=True)', changed)

    def test_environment(self):
        env = flow.cpu_environment(3)
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '')
        self.assertEqual(env['OMP_NUM_THREADS'], '3')
        with self.assertRaises(ValueError):
            flow.cpu_environment(0)

    def test_config_relocation(self):
        dst = Path('/safe/workspace')
        source = {'forceRoot': r'C:\Users\alexf\Documents\Codex\u\work\element-motion\full',
                  'keep': 'https://example.test/work/test', 'nested': ['/old/root/outputs/data.json']}
        result = flow.rebase_json(source, dst)
        self.assertEqual(result['forceRoot'], '/safe/workspace/work/element-motion/full')
        self.assertEqual(result['nested'], ['/safe/workspace/outputs/data.json'])
        self.assertEqual(result['keep'], source['keep'])

    def test_config_traversal_rejected(self):
        with self.assertRaises(ValueError):
            flow.rebase_json('C:/old/work/../../outside', Path('/safe/workspace'))

    def test_force_cycles_denoising_is_cpu(self):
        cpu = types.SimpleNamespace(type='CPU', use=False)
        gpu = types.SimpleNamespace(type='OPTIX', use=True)
        scene = types.SimpleNamespace(render=types.SimpleNamespace(engine='BLENDER_EEVEE_NEXT', compositor_device='GPU'),
                                      cycles=types.SimpleNamespace(device='GPU', denoiser='OPTIX', denoising_use_gpu=True))
        prefs = types.SimpleNamespace(compute_device_type='OPTIX', devices=[cpu, gpu])
        fake = types.SimpleNamespace(data=types.SimpleNamespace(scenes=[scene]),
                  context=types.SimpleNamespace(preferences=types.SimpleNamespace(addons={'cycles': types.SimpleNamespace(preferences=prefs)})))
        flow.force_cycles_cpu(fake)
        self.assertEqual(scene.cycles.device, 'CPU')
        self.assertFalse(scene.cycles.denoising_use_gpu)
        self.assertEqual(scene.render.compositor_device, 'CPU')
        self.assertTrue(cpu.use)
        self.assertFalse(gpu.use)


class WorkspaceTests(unittest.TestCase):
    def test_isolation_and_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'original'; source.mkdir()
            (source / 'work').mkdir()
            (source / 'work/file.py').write_text('original')
            destination = root / 'cpu'
            receipt = flow.stage(source, destination)
            self.assertEqual(len(receipt['sourceHashes']), 1)
            (destination / 'work/file.py').write_text('changed CPU copy')
            self.assertEqual((source / 'work/file.py').read_text(), 'original')
            self.assertTrue(flow.verify_original(destination)['unchanged'])
            (source / 'work/file.py').write_text('external edit')
            with self.assertRaisesRegex(RuntimeError, 'Original checkout changed'):
                flow.verify_original(destination)

    def test_inside_checkout_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                flow.stage(root, root / 'cpu')
            with self.assertRaises(ValueError):
                flow.stage(root, root)

    def test_existing_workspace_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source').mkdir(); (root / 'dest').mkdir()
            with self.assertRaises(FileExistsError):
                flow.stage(root / 'source', root / 'dest')

    def test_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'source').mkdir()
            (root / 'real').write_text('data')
            (root / 'source/link').symlink_to(root / 'real')
            with self.assertRaisesRegex(RuntimeError, 'Symlink'):
                flow.stage(root / 'source', root / 'dest')

    def test_image_comparison(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            Image.new('RGB', (8, 8), 'white').save(root / 'a.png')
            Image.new('RGB', (8, 8), 'white').save(root / 'b.png')
            result = flow.compare_images(root / 'a.png', root / 'b.png', root / 'report.json')
            self.assertTrue(result['identical'])
            Image.new('RGB', (7, 8), 'white').save(root / 'b.png')
            with self.assertRaises(ValueError):
                flow.compare_images(root / 'a.png', root / 'b.png', root / 'report.json')


class OriginalGasTests(unittest.TestCase):
    """No copied solver: execute the actual current repository source on an analytic fixture."""
    def test_original_fire_and_air_step_and_render(self):
        import numpy as np
        import torch
        paths = [flow.ROOT / flow.ELEMENTS / f'sigil_02_{kind}_v2.py' for kind in ('fire', 'air')]
        if not all(path.is_file() for path in paths):
            self.skipTest('Original repository sources not present in this local add-on-only checkout')
        for path in paths:
            with self.subTest(source=path.name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / 'sigil-02-v2'; source.mkdir()
                z, x = np.meshgrid(np.linspace(-1, 1, 18), np.linspace(-1, 1, 32), indexing='ij')
                support = np.exp(-(x*x+z*z)*8).astype('float32')
                np.savez_compressed(source / 'source.npz', support=support, sdf=support*.2,
                                    arrival=np.zeros_like(support), dirx=np.ones_like(support), dirz=np.zeros_like(support))
                code, report = flow.gas_program(path.read_text(), 1, (64, 36))
                namespace = {'__name__': '__cpu_test__', '__file__': str(root / path.name)}
                with patch.object(sys, 'argv', [str(path), '--size', '32', '8', '18', '--fps', '30', '--substeps', '3']):
                    exec(code, namespace)
                for i in range(4):
                    divergence = namespace['step'](i / 90)
                    self.assertTrue(np.isfinite(divergence))
                self.assertEqual(namespace['state'].device.type, 'cpu')
                self.assertTrue(bool(torch.isfinite(namespace['state']).all()))
                self.assertGreater(float(namespace['state'][:, 3:].abs().sum()), 0)
                buffer = io.BytesIO()
                namespace.update(encoder=types.SimpleNamespace(stdin=buffer), TOTAL=1)
                namespace['render'](0)
                self.assertEqual(len(buffer.getvalue()), 64*36*3)
                self.assertTrue(report['productionFunctionsIdenticalBeforeExplicitPreviewResize'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
