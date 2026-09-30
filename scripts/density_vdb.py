"""Lossless float32 solved-density export using OpenVDB bundled with Blender bpy.

Run with the Python environment matching the installed Blender bpy wheel.
No apt packages or extra Python wheels are required. Array axes are world XYZ.
The transform places index (i,j,k) at lo + (index + 0.5) * spacing, matching
sigil_02_atmosphere's physical solver cell centers. Material noise stays in the
original Blender shader, preserving its continuous detail rather than baking
an approximation into the solved density field.
"""
from __future__ import annotations

from pathlib import Path
import importlib
import os
import site
import sys
import tempfile

import numpy as np


def _load_openvdb():
    try:
        return importlib.import_module('openvdb')
    except ModuleNotFoundError as error:
        if error.name != 'openvdb':
            raise
    # The bpy wheel keeps its native extension in Blender's own bundled
    # site-packages, outside the ordinary venv module search path.
    for installed in site.getsitepackages():
        for directory in sorted(Path(installed).glob('bpy/*/python/lib/python*/site-packages')):
            if list(directory.glob('openvdb*.so')):
                sys.path.insert(0, str(directory))
                try:
                    return importlib.import_module('openvdb')
                except ModuleNotFoundError as error:
                    if error.name != 'openvdb':
                        raise
    raise ImportError('Native OpenVDB is available in the bpy Python 3.11 environment. '
                      'Use the Python environment matching the installed Blender bpy wheel.')


vdb = _load_openvdb()


def write_density(path, density, lo, spacing):
    """Write and verify an exact FloatGrid at the supplied solver cell centers.

    Requires a finite nonnegative float32 XYZ array. Zero voxels stay inactive;
    every nonzero float32 value is retained without a sparsification tolerance.
    Returns a compact receipt; the destination is replaced only after complete
    roundtrip and transform verification.
    """
    target = Path(path)
    array = np.asarray(density)
    if array.ndim != 3 or array.dtype != np.float32 or any(size <= 0 for size in array.shape):
        raise ValueError('Density must be a nonempty three-dimensional float32 XYZ array.')
    if not np.isfinite(array).all() or np.any(array < 0):
        raise ValueError('Density must contain finite nonnegative values.')
    origin, pitch = np.asarray(lo, dtype=np.float64), np.asarray(spacing, dtype=np.float64)
    if origin.shape != (3,) or pitch.shape != (3,) or not np.isfinite(origin).all() or not np.isfinite(pitch).all() or np.any(pitch <= 0):
        raise ValueError('lo and spacing must contain three finite coordinates; spacing must be positive.')
    array = np.ascontiguousarray(array)
    grid = vdb.FloatGrid()
    grid.name = 'density'
    grid.gridClass = vdb.GridClass.FOG_VOLUME
    grid.copyFromArray(array, tolerance=0.0)
    first_center = origin + pitch * 0.5
    grid.transform = vdb.createLinearTransform((
        (float(pitch[0]), 0.0, 0.0, 0.0),
        (0.0, float(pitch[1]), 0.0, 0.0),
        (0.0, 0.0, float(pitch[2]), 0.0),
        (float(first_center[0]), float(first_center[1]), float(first_center[2]), 1.0),
    ))
    grid['cybr.mapping'] = 'XYZ solver cell centers: lo + (index + 0.5) * spacing'
    grid['cybr.source'] = 'Fresh finite incompressible CPU density; float32 lossless, zero tolerance'
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix='.density-', suffix='.vdb', dir=target.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        vdb.write(str(temporary), grids=[grid])
        restored = vdb.read(str(temporary), 'density')
        check = np.zeros(array.shape, dtype=np.float32)
        restored.copyToArray(check)
        if not np.array_equal(array, check):
            raise RuntimeError('OpenVDB density roundtrip changed float32 solver values.')
        last_index = np.asarray(array.shape, dtype=np.float64) - 1
        for index in (np.zeros(3), last_index):
            world = np.asarray(restored.transform.indexToWorld(tuple(index)))
            expected = origin + (index + 0.5) * pitch
            if not np.allclose(world, expected, rtol=0, atol=1e-12):
                raise RuntimeError('OpenVDB world transform changed the solver grid placement.')
        receipt = {
            'path': str(target), 'shape': list(array.shape),
            'lo': origin.tolist(), 'spacing': pitch.tolist(),
            'activeVoxels': int(restored.activeVoxelCount()),
            'bytes': temporary.stat().st_size, 'exactFloat32Roundtrip': True,
        }
        temporary.replace(target)
        del restored
        return receipt
    finally:
        temporary.unlink(missing_ok=True)
        del grid
