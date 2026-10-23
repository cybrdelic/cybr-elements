"""Ensure bounded-memory receipts hash exactly the original state bytes."""
import hashlib
import contextlib
import io
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

torch.set_num_threads(2)

from render_flow_regression import ROOT, state_digest, validate_source
from examples.counter_rotating_sources import generate


class StateReceiptTest(unittest.TestCase):
    def test_new_example_uses_the_production_source_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'two-rings.npz'
            with contextlib.redirect_stdout(io.StringIO()):
                generate(path)
            validate_source(path)
            with np.load(path) as source:
                active=source['support']>0
                self.assertGreater(int(active.sum()),100)
                norm=np.sqrt(source['dirx'][active]**2+source['dirz'][active]**2)
                np.testing.assert_allclose(norm,1,rtol=1e-6)
                self.assertGreaterEqual(float(source['arrival'][active].min()),.29999)
                self.assertLessEqual(float(source['arrival'][active].max()),3.90001)

    def test_production_source_has_full_contract(self):
        validate_source(ROOT/'sigil-02-v2/source.npz')

    def test_reduced_source_is_rejected_for_full_film(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'reduced.npz'
            np.savez(path,support=np.zeros((90,160),np.float32))
            with self.assertRaisesRegex(ValueError,'Full-grid'):
                validate_source(path)

    def test_exact_multislab_multichannel_bytes(self):
        torch.manual_seed(937)
        # Crosses two 64-plane boundaries and includes signed values, zeros,
        # subnormal magnitudes, and channel-distinct data in native float32.
        state=torch.randn((1,8,137,7,9),dtype=torch.float32)
        state[:,0]=0
        state[:,1]*=1e-30
        state[:,2]*=1e20
        reference=hashlib.sha256(memoryview(state.numpy())).hexdigest()
        self.assertEqual(state_digest(state),reference)

    def test_matches_contiguous_logical_order(self):
        state=torch.arange(2*8*137*7*9,dtype=torch.float32).reshape(2,8,137,7,9)
        state=state[:,:,:,:,::2]
        reference=hashlib.sha256(memoryview(state.contiguous().numpy())).hexdigest()
        self.assertEqual(state_digest(state),reference)


if __name__=='__main__':
    unittest.main()
