"""CPU readback-decoding gates only; no adapter, simulation or rendered claims."""
import sys
import unittest
from pathlib import Path
try:
    import numpy as np
except ImportError:
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'work/smoke-shapes-qa/vendor'))
    import numpy as np
from native_wood_fault import flux_summary,material_peaks


class WoodFaultReadbackTests(unittest.TestCase):
    def test_unsigned64_flux_and_shader_normalization(self):
        words=np.zeros((8,6),np.uint32)
        words[3]=[17,1,9,1,np.float32(2).view(np.uint32),0]
        result=flux_summary(words.tobytes(),{'N':2})
        mass=(2**32+17)/1e8;energy=(2**32+9)/256
        self.assertAlmostEqual(result['totalMassKg'],mass)
        self.assertAlmostEqual(result['totalEnergyJ'],energy)
        peak=result['energyPeak'];self.assertEqual(peak['voxelZYX'],[0,1,1])
        self.assertAlmostEqual(peak['normalizedFuelKgM3'],mass/27*2)
        self.assertAlmostEqual(peak['normalizedSensibleEnthalpy'],energy/(27*1200*1200)*2)

    def test_blocked_flux_is_reported_as_retained_not_consumed(self):
        words=np.zeros((8,6),np.uint32);words[6]=[100000000,0,25600,0,np.float32(4).view(np.uint32),1]
        result=flux_summary(words.tobytes(),{'N':2})
        self.assertEqual(result['blockedMassKg'],1)
        self.assertEqual(result['blockedEnergyJ'],100)
        self.assertTrue(result['energyPeak']['blocked'])
        self.assertEqual(result['energyPeak']['normalizedSensibleEnthalpy'],0)

    def test_material_global_peak_is_distinct_from_actual_occupied_donor(self):
        stock=np.zeros((2,2,2,4),np.float32);metadata=np.zeros_like(stock)
        stock[0,0,0,1]=100;stock[1,0,1]=[.6,3,.2,.1]
        metadata[1,0,1]=[.5,.25,-.5,2]
        result=material_peaks(stock,metadata,.5,[1,2,3])
        self.assertFalse(result['global']['occupied'])
        self.assertEqual(result['occupied']['voxelZYX'],[1,0,1])
        self.assertEqual(result['occupied']['worldAtRest'],[1.25,2.125,2.75])
        self.assertEqual(result['occupied']['heatK'],1793.15)
        self.assertEqual(result['occupied']['dryMassKg'],.25)

    def test_bad_flux_stride_or_length_cannot_be_misdiagnosed(self):
        with self.assertRaises(ValueError):flux_summary(bytes(8*6*4),{'N':2,'stride':5})
        with self.assertRaises(ValueError):flux_summary(bytes(8*6*4-4),{'N':2})


if __name__=='__main__':unittest.main()
