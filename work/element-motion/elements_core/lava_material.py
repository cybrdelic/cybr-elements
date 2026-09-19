"""Auditable shading controls for the continuum lava surface.

The continuum solver carries the material state.  This module converts the
resolved surface temperature and constitutive damage into slowly varying BSDF
controls and thermal radiance.  It deliberately does *not* invent a second
motion field or a hidden hot mask.  Fine spatial breakup is supplied later by
material-coordinate procedural textures and is documented as sub-grid optical
roughness, not resolved fracture geometry.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

_H = 6.62607015e-34
_C = 299792458.0
_K = 1.380649e-23
_VISIBLE_WAVELENGTHS = np.array([610.0, 550.0, 460.0], dtype=np.float64) * 1e-9
_VISIBLE_BAND_WIDTH = 60e-9
# Blender's RGB emission strength is not a spectral radiance unit.  Keep the
# physical three-band radiance for audit, then map it into scene-linear shader
# strength with one explicit conversion constant rather than letting AgX clip
# raw W m^-2 sr^-1 values toward white.
_SCENE_VISIBLE_RADIANCE_UNIT = 62.0


def smoothstep01(x):
    x = np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def planck_rgb(temperature, emissivity=.90):
    """Three narrow visible bands of Planck spectral radiance.

    The returned values are linear radiance-like RGB controls.  They are not a
    calibrated camera response or a claim of full spectral transport.
    """
    t = np.asarray(temperature, dtype=np.float64)
    if np.any(~np.isfinite(t)) or np.any(t <= 0):
        raise ValueError('temperature must be positive and finite')
    if not np.isfinite(emissivity) or not 0 <= emissivity <= 1:
        raise ValueError('emissivity must lie in [0, 1]')
    wl = _VISIBLE_WAVELENGTHS
    exponent = _H * _C / (wl[None, :] * _K * t.reshape(-1, 1))
    radiance = (2.0 * _H * _C**2 / wl**5) / np.expm1(exponent)
    radiance *= _VISIBLE_BAND_WIDTH * emissivity
    return radiance.reshape(t.shape + (3,))


def material_controls(temperature, damage, *, solidus=1250.0, liquidus=1450.0):
    """Return resolved-state BSDF controls for the surface vertices.

    ``crust`` comes only from the phase interval. ``fracture`` is a *shading
    weight* for damage-gated sub-grid relief; it is intentionally not presented
    as a resolved crack topology.  The hot melt remains smoother and glossier,
    while the cooled load-bearing skin becomes rougher and more diffuse.
    """
    t = np.asarray(temperature, dtype=np.float64)
    d = np.asarray(damage, dtype=np.float64)
    if t.shape != d.shape or np.any(~np.isfinite(t)) or np.any(~np.isfinite(d)):
        raise ValueError('temperature and damage must be finite arrays of the same shape')
    if liquidus <= solidus:
        raise ValueError('liquidus must exceed solidus')
    d = np.clip(d, 0.0, 1.0)
    crust_linear = np.clip((liquidus - t) / (liquidus - solidus), 0.0, 1.0)
    crust = smoothstep01(crust_linear)
    melt = 1.0 - crust
    # Obsidian is a thermal state, not a damage-history mask.  Damage only
    # controls fissure detail below.  This makes the black-glass transition
    # auditable from the simulated surface temperature.
    obsidian = smoothstep01(np.clip((solidus - t) / 220.0, 0.0, 1.0))
    transitional = crust * (1.0 - obsidian)
    # Thermal-shock damage should become visible well before catastrophic
    # failure.  Keep it strictly subordinate to the thermal phase state.
    fracture = crust * smoothstep01(np.clip((d - .03) / .42, 0.0, 1.0))
    relief = np.clip(.55 * transitional + .28 * obsidian + .55 * fracture, 0.0, 1.0)
    # Fresh melt is smooth, transitional crust is matte, and fully quenched
    # obsidian returns to a sharp glassy grazing response.
    # Hot melt is viscous and optically rougher than polished glass. Raising
    # its roughness removes the plastic/white specular dots seen in the first
    # seconds while preserving the sharp cooled-obsidian response.
    roughness = .31 * melt + .60 * transitional + .16 * obsidian + .12 * fracture
    roughness = np.clip(roughness, .12, .88)
    coat = .018 * melt + .060 * transitional + .42 * obsidian * (1.0 - .55 * fracture)
    coat = np.clip(coat, .025, .46)
    hot = np.array([.0060, .00135, .00030])
    crust_color = np.array([.0046, .0031, .0020])
    # Keep the quenched phase black but not mirror-silver under the key lights.
    glass = np.array([.0016, .0023, .0038])
    base = (hot[None, :] * melt.reshape(-1, 1)
            + crust_color[None, :] * transitional.reshape(-1, 1)
            + glass[None, :] * obsidian.reshape(-1, 1))
    base *= (1.0 - .34 * fracture.reshape(-1, 1))
    base = base.reshape(t.shape + (3,))
    radiance = planck_rgb(t, emissivity=.90)
    peak = np.maximum(np.max(radiance, axis=-1, keepdims=True), 1e-30)
    thermal_color = radiance / peak
    thermal_strength = np.sum(radiance, axis=-1) / _SCENE_VISIBLE_RADIANCE_UNIT
    return {
        'crust': crust,
        'melt': melt,
        'obsidian': obsidian,
        'transitionalCrust': transitional,
        'relief': relief,
        'fracture': fracture,
        'roughness': roughness,
        'coat': coat,
        'baseColor': base,
        'thermalRadiance': radiance,
        'thermalColor': thermal_color,
        'thermalStrength': thermal_strength,
    }
