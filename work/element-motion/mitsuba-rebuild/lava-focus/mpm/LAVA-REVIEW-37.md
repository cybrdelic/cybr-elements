# Lava revision 37 — still incomplete

The user's full objective is **not achieved**. Do not call this world class,
photoreal, a completed fracture simulation, or a finished video.

The local repairs page now displays `basalt-material-37.png` at 1440 × 900.
Previous page retained as `solver-25.html`. This is an optical/material revision
using the existing R31 Newton MPM / XPBD cache at 0.75 seconds, whose initial
basalt fragments were authored. It is not the new continuous-crust run.

## Kept material changes

- `lava_relief36.py`: bounded volumetric cavities and chipped relief on the
  rigid collision envelopes, fixed in material coordinates. About 3 million
  triangles. Fluid volume error 9.52e-6. Relief is authored render geometry.
- `lava_crust_heat37.py`: replaced the old exponential vertical temperature
  profile with 1D finite-volume enthalpy preparation and exposed-face cooling.
  Selected 1250 K core, 600 seconds of preparation. Those are initial-condition
  choices, not a calibrated lava composition or simulated fracture history.
- `lava_display34.py`: Stephen Hill ACES fitted display transform, no bloom.
- Geometry-sampled Planck emission avoids large image atlases. The new emitter
  initially had a wrong PLY attribute name and an overly strict visibility ray
  test. Both were caught by `lava_emitter36_check.py` and corrected before the
  final render. Validation versus Mitsuba's native area emitter: image relative
  L2 1.05e-5; total radiance difference 2.09e-7.
- Final native CUDA render: 192 samples, 1440 × 900, 14.47 seconds including
  CPU OIDN and image writing. Exact black background verified. No smoke added.

## Unresolved visible and physical failures

The large fragments still look like extruded slabs. Microrelief helps the rock
surface but does not correct the initial 2D Voronoi / convex plate construction.
The thermal revision is not fed back into the cached mechanical solve.
Rock–melt heat exchange, emergent breakup, and sustained convincing motion are
not solved. Do not disguise these with smoke, exposure, a close crop, or more
render samples. The new image is a material study, not a full simulation pass.

## Continuous-crust numerical work

R32–36 fixed relative grid-coordinate hashing (half-cell world offsets aliased
nodes), validated active tangential contact reduction, warm starting, and stable
pressure line-search energy differences. Warm-pressure and grid-translation
checks pass; 16 active-contact comparisons pass with max velocity difference
1.97e-8. Restored `lava_mpm_linear27.py` after a disk-full edit and checked all
lava Python source syntax. The experimental `cpu_reuse` factor path is slower
and is not selected. GPU dense factorization now checks host memory headroom.

Latest continuous-crust cache: `rebuild-33/continued-36/state.npz` at 2.2 seconds,
4314 particles, max damage 0.01924, **zero broken edges**. The next pressure step
failed its residual check, and the trial rolled back at the wall deadline.
This is not visually or physically accepted. No later run is active.

## Resource constraints and reproduction

The C: drive repeatedly ran out of space, including one interrupted source
write (restored) and one partial render archive. Regenerable PLY/EXR/mesh NPZ
caches were removed; raw mechanical state NPZs, source files and public images
were preserved. `.venv-newton` was removed earlier to recover space; version
requirements remain under `rebuild-28/requirements-newton.txt`. Do not assume
that environment or old derived mesh files still exist. The main `.venv` and
all selected render inputs remain available.

Rebuild R36 geometry from `rebuild-31/closed-crust/frame-000750.npz` with
`lava_relief36.py`, then run `lava_crust_heat37.py` with `--preparation 600`.
The selected high-resolution image is under
`rebuild-31/closed-crust/frame-000750-relief36/thermal37-600/review/`.

Do not use the rejected R35 macro render as a successful lava result. Its
`linear.npz` is partially corrupt (raw readable, clean incomplete).
