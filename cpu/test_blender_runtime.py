"""Structural and mocked-execution checks, not claims of real Blender rendering."""
import ast
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_runtime import BlenderAdapter, main


class BlenderIsolationTests(unittest.TestCase):
    def test_only_module_output_is_redirected(self):
        source = "out=O/'frames'\nif full: out=O/'pilot'\ndef local():\n out=27\n return out\ns.cycles.samples=96\n"
        adapter = BlenderAdapter()
        tree = ast.fix_missing_locations(adapter.visit(ast.parse(source)))
        text = ast.unparse(tree)
        self.assertEqual(adapter.output_assignments, 2)
        self.assertEqual(text.count('out = _cpu_frame_dir'), 2)
        self.assertIn('out = 27', text)
        self.assertIn('s.cycles.samples = 96', text)

    def test_chained_output_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'chained output'):
            BlenderAdapter().visit(ast.parse('out=other=some_path'))

    def test_unknown_output_fails_before_blender_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cpu-workspace.json').write_text('{}')
            script = root / 'scene.py'
            script.write_text('important_side_effect()')
            with self.assertRaisesRegex(RuntimeError, 'Unknown scene output'):
                main(['--script', str(script)])

    def test_nonworkspace_script_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / 'scene.py'
            script.write_text("out=Path('frames')")
            with self.assertRaisesRegex(RuntimeError, 'prepared CPU workspace'):
                main(['--script', str(script)])

    def fake_blender(self):
        cpu = types.SimpleNamespace(type='CPU', use=False)
        gpu = types.SimpleNamespace(type='OPTIX', use=True)
        settings = types.SimpleNamespace(engine='BLENDER_EEVEE_NEXT', compositor_device='GPU',
                    filepath='', threads_mode='AUTO', threads=1, resolution_x=1920,
                    resolution_y=1080, resolution_percentage=100)
        cycles = types.SimpleNamespace(device='GPU', denoiser='OPTIX', denoising_use_gpu=True, samples=96)
        scene = types.SimpleNamespace(render=settings, cycles=cycles, frame_current=150)
        prefs = types.SimpleNamespace(compute_device_type='OPTIX', devices=[cpu, gpu])
        fake = types.SimpleNamespace(data=types.SimpleNamespace(scenes=[scene]),
                    context=types.SimpleNamespace(scene=scene, preferences=types.SimpleNamespace(
                         addons={'cycles': types.SimpleNamespace(preferences=prefs)})))
        calls = []
        def render(**kwargs):
            self.assertEqual(scene.render.engine, 'CYCLES')
            self.assertEqual(scene.cycles.device, 'CPU')
            self.assertFalse(scene.cycles.denoising_use_gpu)
            self.assertEqual(scene.render.compositor_device, 'CPU')
            self.assertFalse(gpu.use)
            self.assertEqual(scene.cycles.samples, 96)
            Path(scene.render.filepath).write_bytes(b'mocked CPU render; not an image')
            calls.append(kwargs)
            return {'FINISHED'}
        fake.ops = types.SimpleNamespace(render=types.SimpleNamespace(render=render))
        return fake, calls

    def test_fresh_frames_cpu_enforcement_and_success_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cpu-workspace.json').write_text('{}')
            legacy = root / 'frames'; legacy.mkdir()
            (legacy / '0150.jpg').write_bytes(b'old GPU image')
            script = root / 'scene.py'
            script.write_text("import bpy\nfrom pathlib import Path\nout=Path(__file__).parent/'frames'\ns=bpy.context.scene\ns.cycles.device='GPU'\ns.cycles.samples=96\ns.render.filepath=str(out/'0150.jpg')\nif not (out/'0150.jpg').exists(): bpy.ops.render.render(write_still=True)\n")
            fake, calls = self.fake_blender()
            with patch.dict(sys.modules, {'bpy': fake}):
                self.assertEqual(main(['--script', str(script), '--threads', '3']), 0)
            self.assertEqual(len(calls), 1)
            self.assertEqual((legacy / '0150.jpg').read_bytes(), b'old GPU image')
            path = next((root / 'cpu-results').rglob('receipt.json'))
            receipt = json.loads(path.read_text())
            self.assertTrue(receipt['completed'])
            self.assertEqual(receipt['renderCalls'], 1)
            self.assertEqual(receipt['frames'][0]['samples'], 96)
            self.assertFalse(receipt['visualParityVerified'])
            self.assertEqual(fake.context.scene.render.threads, 3)

    def test_failed_execution_never_records_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cpu-workspace.json').write_text('{}')
            script = root / 'scene.py'
            script.write_text("out=None\nraise RuntimeError('scene failed')")
            fake, _ = self.fake_blender()
            with patch.dict(sys.modules, {'bpy': fake}), self.assertRaisesRegex(RuntimeError, 'scene failed'):
                main(['--script', str(script)])
            receipt = json.loads(next((root / 'cpu-results').rglob('receipt.json')).read_text())
            self.assertFalse(receipt['completed'])
            self.assertEqual(receipt['renderCalls'], 0)

    def test_render_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cpu-workspace.json').write_text('{}')
            script = root / 'scene.py'
            script.write_text("import bpy\nfrom pathlib import Path\nout=None\nbpy.context.scene.render.filepath=str(Path(__file__).parent/'escape.jpg')\nbpy.ops.render.render(write_still=True)")
            fake, calls = self.fake_blender()
            with patch.dict(sys.modules, {'bpy': fake}), self.assertRaisesRegex(RuntimeError, 'outside the new CPU'):
                main(['--script', str(script)])
            self.assertFalse(calls)
            self.assertFalse((root / 'escape.jpg').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
