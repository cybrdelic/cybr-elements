"""Real-valued periodic Fourier Helmholtz projection for collocated gas grids.

The derivative of an even grid's self-conjugate Nyquist mode is zero. Keeping a
nonzero Nyquist wave number makes the projection violate conjugate symmetry;
the inverse real FFT then silently discards part of the projected velocity.
Absorbing boundaries and emission remain the caller's responsibility.
"""
from __future__ import annotations

import numpy as np
from scipy.fft import rfftn, irfftn


class FourierProjector:
    def __init__(self, shape, spacing, *, workers=2):
        self.shape = tuple(shape)
        self.spacing = np.asarray(spacing, dtype=float)
        if len(self.shape) != 3 or any(not isinstance(n, (int, np.integer)) or n < 2 for n in self.shape):
            raise ValueError("Gas grid must have three integer dimensions of at least two cells.")
        if self.spacing.shape != (3,) or not np.isfinite(self.spacing).all() or np.any(self.spacing <= 0):
            raise ValueError("Gas grid spacing must contain three positive finite values.")
        self.workers = workers
        frequencies = [2 * np.pi * np.fft.fftfreq(self.shape[i], d=self.spacing[i]) for i in range(2)]
        frequencies.append(2 * np.pi * np.fft.rfftfreq(self.shape[2], d=self.spacing[2]))
        for axis, size in enumerate(self.shape):
            if size % 2 == 0:
                frequencies[axis][size // 2] = 0
        self.k = np.meshgrid(*frequencies, indexing="ij")
        self.k2 = sum(component**2 for component in self.k)
        self.k2[self.k2 == 0] = 1

    def _transform(self, velocity):
        velocity = np.asarray(velocity)
        if velocity.shape != (3, *self.shape) or not np.isfinite(velocity).all():
            raise ValueError("Velocity must be a finite vector field matching the gas grid.")
        return velocity, [rfftn(component, workers=self.workers) for component in velocity]

    def project(self, velocity):
        velocity, transformed = self._transform(velocity)
        longitudinal = sum(self.k[i] * transformed[i] for i in range(3))
        projected = np.stack([
            irfftn(transformed[i] - self.k[i] * longitudinal / self.k2,
                   s=self.shape, workers=self.workers).real
            for i in range(3)
        ])
        return projected.astype(np.float32 if velocity.dtype == np.float32 else np.float64)

    def divergence(self, velocity):
        """Spectral divergence before any caller-applied absorbing edge mask."""
        _, transformed = self._transform(velocity)
        return irfftn(1j * sum(self.k[i] * transformed[i] for i in range(3)),
                      s=self.shape, workers=self.workers).real
