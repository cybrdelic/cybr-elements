"""Physical regressions for the new lava film, independent of Blender pixels."""
import unittest
import numpy as np
from studio_lava import LavaFilm, enthalpy, temperature, AMBIENT, LIQUIDUS


class LavaPhysicsTests(unittest.TestCase):
    def model(self, **kwargs):
        support = np.zeros((32, 64))
        support[9:23, 17:47] = 1
        return LavaFilm(support, .06, **kwargs)

    def test_mass_and_energy_ledgers_close_after_transport_and_cooling(self):
        m = self.model(); m.advance(4)
        d = m.diagnostics()
        self.assertLess(d['volume_error_relative'], 1e-12)
        self.assertLess(d['energy_balance_relative'], 1e-12)
        self.assertGreater(d['radiated_J'], 0)

    def test_free_surface_spreads_without_negative_film_or_heat(self):
        m = self.model(); original = m.h.copy(); m.advance(2)
        self.assertGreater(np.count_nonzero(m.h > .001), np.count_nonzero(original))
        self.assertGreaterEqual(float(m.h.min()), -1e-12)
        self.assertGreaterEqual(float(m.energy.min()), -1e-5)
        self.assertTrue(np.isfinite(m.velocity).all())

    def test_viscosity_reduces_spreading(self):
        thin, thick = self.model(viscosity=500), self.model(viscosity=5000)
        thin.advance(2); thick.advance(2)
        self.assertLess(float(thin.h.max()), float(thick.h.max()))

    def test_yield_limit_retains_a_static_column(self):
        m = self.model(yield_stress=1e9); h = m.h.copy(); m.advance(.3)
        np.testing.assert_array_equal(m.h, h)

    def test_latent_heat_roundtrip_through_both_phase_boundaries(self):
        t = np.linspace(AMBIENT, 1700, 1000)
        np.testing.assert_allclose(temperature(enthalpy(t)), t, atol=1e-10)

    def test_cooling_and_surface_temperature_remain_bounded(self):
        m = self.model(); m.advance(8)
        wet = m.h > .003
        self.assertTrue(np.all(m.surface[wet] >= AMBIENT))
        self.assertTrue(np.all(m.surface[wet] <= LIQUIDUS))
        self.assertTrue(np.all(m.bulk_temperature()[wet] <= LIQUIDUS+1e-8))
        self.assertLess(float(m.surface[wet].max()), LIQUIDUS)

    def test_invalid_physical_inputs_fail_before_solving(self):
        for value in [np.full((3, 3), np.nan), np.full((3, 3), -1), np.ones(3)]:
            with self.assertRaises(ValueError): LavaFilm(value, .01)
        for kwargs in [{'viscosity': 0}, {'depth': -1}, {'yield_stress': -1}]:
            with self.assertRaises(ValueError): self.model(**kwargs)


if __name__ == '__main__':
    unittest.main()
