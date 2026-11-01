"""Source availability is not film completion or hardware qualification."""
import contextlib,hashlib,io,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from element_availability import recipe_availability,ROOT
from element_runner import main,parser,resolve_device
from element_scenes import SCENES

class Availability(unittest.TestCase):
    def test_auto_selection_and_explicit_overrides(self):
        self.assertEqual(parser("sigil_02_fire_v2").parse_args([]).device,"auto")
        for available in (False,True):
            with patch('element_runner.torch.cuda.is_available',return_value=available):
                self.assertEqual(resolve_device('auto'),'cuda' if available else 'cpu')
                self.assertEqual(resolve_device('cpu'),'cpu')
                if available:self.assertEqual(resolve_device('cuda'),'cuda')
                else:
                    with self.assertRaisesRegex(RuntimeError,'explicitly requested'):resolve_device('cuda')

    def test_cuda_failure_is_not_retried_on_cpu(self):
        with patch('element_runner.torch.cuda.is_available',return_value=True), patch('element_runner.ElementSession',side_effect=RuntimeError('CUDA allocation failed')) as session:
            with self.assertRaisesRegex(RuntimeError,'CUDA allocation failed'):
                main('fire-v3',[])
            self.assertEqual(session.call_count,1)
            self.assertEqual(session.call_args.args[2],'cuda')

    def test_real_recovered_trail(self):
        r=recipe_availability('fire-shared')
        self.assertTrue(r['inputs_ready'])
        self.assertEqual(r['source_sha256']['shared-trail.json'],'31c5b92889f212c7792848e04865f605d1431d5c487f478c9c4bc02c37b2ecc0')
        self.assertFalse(r['film_complete']);self.assertTrue(r['cpu_supported'])
        self.assertFalse(r['cuda_parity_verified'])

    def test_real_recovered_stroke_and_provenance(self):
        r=recipe_availability('sigil_native_fire_fed')
        self.assertTrue(r['inputs_ready']);self.assertFalse(r['film_complete'])
        path=ROOT/'sigil-native/c-stroke.npz'
        expected='613009fb76653b0c15ddc99cc8b33496028b2511a3744dbfcd8bee4990884d67'
        self.assertEqual(path.stat().st_size,6417)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected)
        self.assertEqual(r['source_sha256']['sigil-native/c-stroke.npz'],expected)
        provenance=json.loads(path.with_suffix('.provenance.json').read_text())
        self.assertEqual(provenance['asset']['sha256'],expected)
        self.assertEqual(provenance['asset']['pack'],'project-assets-047.zip')
        with np.load(path,allow_pickle=False) as data:
            self.assertEqual(data['points'].shape,(283,2))
            self.assertEqual(data['times'].shape,(283,))
            self.assertTrue(np.isfinite(data['points']).all())
            self.assertTrue((np.diff(data['times'])>0).all())

    def test_missing_input_and_gesture_are_explicit(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);shutil.copy(ROOT/'sigil_native_motion.py',root/'sigil_native_motion.py')
            r=recipe_availability('sigil_native_fire_fed',root=root)
            self.assertFalse(r['inputs_ready']);self.assertIn('sigil-native/c-stroke.npz',r['missing'])
        for version in ('21','21b'):
            r=recipe_availability('fire-v3',gesture_version=version)
            self.assertIn('bending_fire_choreography_v'+version+'.py',r['missing'])

    def test_preflight_does_not_allocate_simulation(self):
        with patch('element_runner.ElementSession',side_effect=AssertionError('Must not allocate')):
            for name in SCENES:
                with contextlib.redirect_stdout(io.StringIO()):r=main(name,['--check-inputs'])
                self.assertTrue(r['inputs_ready'],name)
            with tempfile.TemporaryDirectory() as d:
                missing=recipe_availability('sigil_native_fire_fed',root=Path(d))
                with patch('element_availability.recipe_availability',return_value=missing):
                    with self.assertRaisesRegex(FileNotFoundError,'c-stroke'):
                        main('sigil_native_fire_fed',['--device','cpu'])

    def test_corrupt_trail_is_not_ready(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);shutil.copy(ROOT/'shared_motion.py',root/'shared_motion.py')
            (root/'shared-trail.json').write_text('{"frames":[],"sampleRate":120}')
            self.assertFalse(recipe_availability('fire-shared',root=root)['inputs_ready'])

if __name__=='__main__':unittest.main()
