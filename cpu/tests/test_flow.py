"""CPU contracts, immutable source, safe assets, and process supervision tests."""
from __future__ import annotations
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

CPU = Path(__file__).resolve().parents[1]
ROOT = CPU.parent
sys.path.insert(0, str(CPU))
from adapter import GAS, BLENDER, CORE, Diagnostic, adapt, adapt_javascript_manifest, functions, sha256, signature
from assets import copy_new, restore, safe_path, verify
from run import (Flow, FULL_GRID, ROOT as FLOW_ROOT, cpu_environment, force_root,
                 isolated_output, parser, plan, required_inputs, run_group, selected)


class AdapterTests(unittest.TestCase):
    def source(self, filename):
        return (ROOT / 'work/element-motion' / filename).read_text(encoding='utf-8')

    def test_all_five_production_adapters_compile(self):
        for filename in GAS | BLENDER:
            with self.subTest(filename=filename):
                text, receipt = adapt(self.source(filename), filename)
                compile(text, filename, 'exec')
                self.assertIsNone(receipt['diagnostic'])
                self.assertEqual(receipt['visualAcceptance'], 'pending')

    def test_every_numerical_function_is_identical(self):
        for filename in GAS:
            original = functions(ast.parse(self.source(filename)))
            text, _ = adapt(self.source(filename), filename)
            generated = functions(ast.parse(text))
            for name in (*CORE, 'render'):
                with self.subTest(filename=filename, function=name):
                    self.assertIn(name, original)
                    self.assertEqual(original[name], generated[name])

    def test_material_builder_functions_are_preserved(self):
        for filename in BLENDER:
            original = functions(ast.parse(self.source(filename)))
            text, _ = adapt(self.source(filename), filename)
            generated = functions(ast.parse(text))
            for name, body in original.items():
                with self.subTest(filename=filename, function=name):
                    self.assertEqual(body, generated[name])

    def test_cpu_settings_are_explicit(self):
        for filename in GAS:
            text, _ = adapt(self.source(filename), filename)
            self.assertIn("device = 'cpu'", text)
            self.assertNotIn('torch.cuda.', text)
        for filename in BLENDER:
            text, _ = adapt(self.source(filename), filename)
            self.assertIn("s.cycles.device = 'CPU'", text)
            self.assertIn("s.cycles.denoiser = 'OPENIMAGEDENOISE'", text)
            self.assertIn("prefs.compute_device_type = 'NONE'", text)
            self.assertIn('denoising_use_gpu = False', text)
            self.assertIn("compositor_device = 'CPU'", text)

    def test_original_evee_choice_preserved(self):
        text, _ = adapt(self.source('sigil_02_new_materials.py'), 'sigil_02_new_materials.py')
        self.assertIn("'BLENDER_EEVEE_NEXT'", text)
        self.assertIn("full and kind == 'lightning'", text)
        self.assertIn('CYBR_EEVEE_SOFTWARE_VERIFIED', text)

    def test_source_files_never_mutated(self):
        before = {name: sha256(ROOT / 'work/element-motion' / name) for name in GAS | BLENDER}
        for name in before:
            adapt(self.source(name), name)
        after = {name: sha256(ROOT / 'work/element-motion' / name) for name in before}
        self.assertEqual(before, after)

    def test_diagnostic_is_explicit_and_keeps_equations(self):
        for name in GAS:
            text, receipt = adapt(self.source(name), name, diagnostic=Diagnostic(frames=144))
            self.assertIn('TOTAL = 144', text)
            self.assertIn('W, H = (320, 180)', text)
            self.assertIn('size=(180, 320)', text)
            self.assertFalse(receipt['productionVolumeRendererPreserved'])
            original, modified = functions(ast.parse(self.source(name))), functions(ast.parse(text))
            for function in CORE:
                self.assertEqual(original[function], modified[function])

    def test_production_resolution_and_duration_not_lowered(self):
        for name in GAS:
            text, _ = adapt(self.source(name), name)
            self.assertIn('TOTAL = 294', text)
            self.assertIn('W, H = (1920, 1080)', text)
            self.assertIn('size=(1080, 1920)', text)

    def test_interactive_waits_removed_without_fake_approval(self):
        for name in GAS | BLENDER:
            text, _ = adapt(self.source(name), name)
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.While):
                    self.assertNotIn('hero-approved.json', ast.unparse(node.test))
                    self.assertNotIn('/continue', ast.unparse(node.test))
            self.assertNotIn('"userAccepted": true', text)

    def test_cache_waits_not_removed(self):
        text, _ = adapt(self.source('sigil_02_active_water_render.py'), 'sigil_02_active_water_render.py')
        self.assertIn('while', text)
        self.assertIn('manifest.json', text)

    def test_source_drift_rejected_by_guard(self):
        name = 'sigil_02_fire_v2.py'
        source = self.source(name).replace("device='cuda'", "device='unexpected'")
        with self.assertRaises(ValueError):
            adapt(source, name)

    def test_unknown_script_rejected(self):
        with self.assertRaises(ValueError):
            adapt('pass', 'unknown.py')

    def test_invalid_threads_rejected(self):
        with self.assertRaises(ValueError):
            adapt(self.source('sigil_02_fire_v2.py'), 'sigil_02_fire_v2.py', threads=0)

    def test_diagnostic_blender_rejected(self):
        with self.assertRaises(ValueError):
            adapt(self.source('sigil_02_new_materials.py'), 'sigil_02_new_materials.py', diagnostic=Diagnostic())

    def test_module_docstrings_preserved(self):
        for name in BLENDER | GAS:
            source = self.source(name)
            text, _ = adapt(source, name)
            self.assertEqual(ast.get_docstring(ast.parse(source)), ast.get_docstring(ast.parse(text)))

    def test_upstream_lock_matches_checked_out_sources(self):
        lock = json.loads((CPU / 'upstream.json').read_text())
        for relative, digest in lock['sha256'].items():
            with self.subTest(source=relative):
                self.assertEqual(sha256(ROOT / relative), digest)


class StreamingIOTests(unittest.TestCase):
    def test_mesher_manifest_publication_is_atomic(self):
        source = (ROOT / 'work/element-motion/sigil_02_active_mesh.py').read_text()
        text, receipt = adapt(source, 'sigil_02_active_mesh.py')
        self.assertIn('_cpu_atomic_write_text', text)
        self.assertIn('temporary.replace(path)', text)
        self.assertIn('atomic manifest publication', str(receipt['changes']))

    def test_javascript_solver_unchanged_except_manifest_publication(self):
        source = (ROOT / 'work/element-motion/sigil_02_active_water.mjs').read_text()
        text, receipt = adapt_javascript_manifest(source)
        body = text.split('\nfunction _cpuWriteManifest(){', 1)[0]
        original_writer = "fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));"
        self.assertEqual(body.replace('_cpuWriteManifest();', original_writer).rstrip(), source.rstrip())
        self.assertIn('fs.renameSync', text)

    def test_javascript_writer_drift_rejected(self):
        with self.assertRaises(ValueError):
            adapt_javascript_manifest('changed source')


class PlanTests(unittest.TestCase):
    def test_all_presets_have_full_quality(self):
        data = plan(ROOT, selected(['all']), None, False)
        self.assertEqual(data['resolution'], [1920, 1080])
        self.assertEqual(data['gasGrid'], [896, 56, 504])
        self.assertEqual(data['expectedFrames'], dict(fire=294, air=294, earth=300, water=336,
                                                     ice=300, lava=300, lightning=300))
        self.assertFalse(data['writesToSourceCheckout'])

    def test_native_water_does_not_reuse_film(self):
        data = plan(ROOT, ['water'], None, True)
        self.assertEqual(data['expectedFrames']['water'], 240)
        self.assertFalse(any(path.endswith('.mp4') for path in data['requiredInputs']))

    def test_original_water_edit_disclosed(self):
        data = plan(ROOT, ['water'], None, False)
        self.assertIn('retained', data['waterOpening'])
        self.assertTrue(any(path.endswith('water-02-r7.mp4') for path in data['requiredInputs']))

    def test_force_root_rebased_from_windows_full_not_cpu(self):
        self.assertEqual(force_root(ROOT), 'work/element-motion/sigil-02-bending-ground/full')

    def test_cpu_environment_hides_accelerators_and_distrusts_flags(self):
        with patch.dict(os.environ, {'CUDA_VISIBLE_DEVICES': '0', 'CYBR_EEVEE_SOFTWARE_VERIFIED': '1'}):
            env = cpu_environment(3)
        self.assertEqual(env['CUDA_VISIBLE_DEVICES'], '')
        self.assertEqual(env['HIP_VISIBLE_DEVICES'], '')
        self.assertEqual(env['GALLIUM_DRIVER'], 'llvmpipe')
        self.assertEqual(env['OMP_NUM_THREADS'], '3')
        self.assertNotIn('CYBR_EEVEE_SOFTWARE_VERIFIED', env)

    def test_selections_deduplicate(self):
        self.assertEqual(selected(['fire', 'air', 'fire']), ['fire', 'air'])

    def test_mixed_all_is_rejected(self):
        with self.assertRaises(ValueError):
            selected(['all', 'fire'])

    def test_unknown_element_is_rejected(self):
        with self.assertRaises(ValueError):
            selected(['banana'])

    def test_invalid_diagnostic_dimensions(self):
        for kwargs in ({'frames': 0}, {'frames': 295}, {'width': 321}, {'x': 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Diagnostic(**kwargs)

    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileExistsError):
                isolated_output(ROOT, Path(tmp))

    def test_checkout_and_ancestor_output_refused(self):
        for path in (ROOT, ROOT / 'new-output', ROOT.parent):
            with self.subTest(path=path), self.assertRaises(ValueError):
                isolated_output(ROOT, path)

    def test_sibling_output_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'new-run'
            self.assertEqual(isolated_output(ROOT, target), target.resolve())

    def test_smoke_requires_gas_selection(self):
        args = parser().parse_args(['smoke', '--elements', 'ice', '--output', '/tmp/unused-cpu-test-path'])
        with self.assertRaises(ValueError):
            Flow(args)


class AssetTests(unittest.TestCase):
    def test_unsafe_paths_rejected(self):
        for value in ('../escape', '/etc/passwd', 'C:/file', 'a\\b', 'a/../../b', ''):
            with self.subTest(value=value), self.assertRaises(ValueError):
                safe_path(Path('/tmp/root'), value)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'root';root.mkdir()
            (root / 'escape').symlink_to(Path(tmp), target_is_directory=True)
            with self.assertRaises(ValueError):
                safe_path(root, 'escape/file')

    def test_real_copy_not_hardlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / 'source', Path(tmp) / 'output'
            src.write_bytes(b'original')
            copy_new(src, dst)
            dst.write_bytes(b'changed')
            self.assertEqual(src.read_bytes(), b'original')

    def test_overwrite_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            src, dst = Path(tmp) / 'a', Path(tmp) / 'b'
            src.write_bytes(b'a');dst.write_bytes(b'b')
            with self.assertRaises(FileExistsError):
                copy_new(src, dst)
            self.assertEqual(dst.read_bytes(), b'b')

    def test_asset_checksum_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'input';path.write_bytes(b'hello')
            verify(path, {'bytes': 5, 'sha256': hashlib.sha256(b'hello').hexdigest()})
            with self.assertRaises(ValueError):
                verify(path, {'bytes': 5, 'sha256': 'bad'})

    def test_cached_assets_require_manifest_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work, cache = [Path(tmp) / n for n in ('root', 'work', 'cache')]
            for path in (root, work, cache):path.mkdir()
            (cache / 'data').write_bytes(b'input')
            with self.assertRaises(ValueError):
                restore(root, work, ['data'], input_cache=cache)

    def test_verified_cache_copied_to_workspace_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, work, cache = [Path(tmp) / n for n in ('root', 'work', 'cache')]
            for path in (root, work, cache):path.mkdir()
            (root / 'docs').mkdir();(cache / 'data').write_bytes(b'input')
            record = {'path': 'data', 'bytes': 5, 'sha256': hashlib.sha256(b'input').hexdigest()}
            (root / 'docs/assets.json').write_text(json.dumps({'assets': [record]}))
            receipt = restore(root, work, ['data'], input_cache=cache)
            self.assertEqual((work / 'data').read_bytes(), b'input')
            self.assertFalse((root / 'data').exists())
            self.assertEqual(receipt[0]['origin'], 'verified-input-cache')


class ProcessTests(unittest.TestCase):
    def test_successful_group_and_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = run_group([('one', [sys.executable, '-c', 'print("one")']),
                                ('two', [sys.executable, '-c', 'print("two")'])],
                               root, root, cpu_environment(1), 10, 0)
            self.assertEqual(result['returnCodes'], {'one': 0, 'two': 0})
            self.assertIn('one', (root / 'logs/one.log').read_text())

    def test_failure_terminates_waiting_peer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);start = time.monotonic()
            with self.assertRaises(RuntimeError):
                run_group([('fail', [sys.executable, '-c', 'raise SystemExit(7)']),
                           ('peer', [sys.executable, '-c', 'import time;time.sleep(60)'])],
                          root, root, cpu_environment(1), 10, 0)
            self.assertLess(time.monotonic() - start, 8)

    def test_deadline_terminates_cache_wait(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp);start = time.monotonic()
            with self.assertRaises(TimeoutError):
                run_group([('wait', [sys.executable, '-c', 'import time;time.sleep(60)'])],
                          root, root, cpu_environment(1), .3, 0)
            self.assertLess(time.monotonic() - start, 8)

    def test_disk_reserve_aborts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(OSError):
                run_group([('wait', [sys.executable, '-c', 'import time;time.sleep(60)'])],
                          root, root, cpu_environment(1), 10, 10**30)


if __name__ == '__main__':
    unittest.main(verbosity=2)
