# Lava GPU rebuild review

**The requested visual result has not been achieved. Do not promote these trials as finished lava.**

The public `repairs/index.html` and its `cooling-25.png` remain unchanged. The new experiments are isolated in this working directory. No new final video was produced.

## What the new work established

- Newton 1.6 / Warp 1.17 run in the separate `.venv-newton` environment. Mitsuba rendering remains in the original `.venv`.
- The GPU gravity probe passed with approximately 1.2e-6 m/s velocity error. The new SPH heat kernel passed the CPU quadratic-temperature conduction check (1.51% error) and boundary energy check.
- The original experimental phase transition changed bulk stiffness abruptly. Holding bulk modulus fixed reduced a 1.03 m/s spike to 0.013 m/s in the comparison. However, the FP32 elastic-strain remapping unit check still missed its 1% gate (1.82% error). That thermomechanical experiment is not accepted.
- Newton reaction stress uses a compression-positive convention. The experimental damage calculation had the opposite sign; correcting it did not produce acceptable fracture geometry.
- The separate MPM/rigid-body experiment uses real bidirectional contact impulses. Its basalt pieces are supplied as initial geometry, not claimed as emergent fractures.
- A sixteen-layer thermal skin model replaces use of particle-average temperature for surface radiation. It allocates skin mass within each particle, rather than adding extra mass. Its CPU result differed from an independent same-resolution reference by 0.00017 K; doubling thermal resolution changed surface temperature by 2.22 K. The single-column energy residual was 0.000131 J.
- Small native Mitsuba CUDA path-traced renders were inspected. OIDN denoising ran on the CPU. No generated photographs or smoke overlays were substituted for simulation.

## Visual trials and why they were rejected

1. **R28 thermomechanical flow:** rounded, waffled slab. High damage values did not create resolved open cracks. Not acceptable.
2. **R29 separate basalt pieces:** real thickness and roughness, but wide, uniform gaps made the result look like rocks assembled in an orange pool. The finite initial volume also looked like a puck.
3. **R30 thermal skin and loose clinkers:** surface cooling changed the flat orange toward a deeper red, but did not fix the assembled mosaic. Some detached pieces also weakened the composition. Not accepted.
4. **R31 closely packed crust:** the narrower gaps produced an overly regular block structure and hid most of the molten interior. CPU geometry inspection was sufficient to reject it; no additional beauty render was made.

## Last completed bounded run

`rebuild-31/closed-crust/receipt.json`: 47,899 MPM particles, 45 initial basalt bodies, quadratic B2 velocity interpolation, 3.5 mm particle spacing, 7 mm grid spacing, 0.002 s mechanical steps. Eight seconds of thermal preparation were performed with the initial geometry held fixed, followed by one second of mechanical simulation. Runtime was 147.6 seconds including thermal preparation. This is a prepared initial condition, not eight seconds of solved flow history.

All saved arrays at one second were finite. The reported thermal residual was 3.17 J against 4.06 MJ of starting thermal energy. This does **not** establish mechanical convergence, realistic fracture, or acceptable motion. Several large bodies had intermittent velocities around 0.23–0.38 m/s while the median body speed was about 0.01 m/s; contact stability remains unresolved. The liquid surface also penetrated the nominal bed by about 3.7 mm at the most extreme particle.

## Work that remains necessary

The main missing mechanism is a coherent crust created, stressed, and broken by the same moving material. Supplied polygonal fragments can test contact and optics, but the inspected results do not reproduce that mechanism or the required appearance. The current trials also lack resolved crust melting, rock/fluid heat exchange, sustained feed, and coupled gas/smoke. These omissions must not be relabeled as a finished full simulation.

The next solver work needs an independently verified fracture/contact benchmark and a resolved thermal crust on a sustained flow before another beauty pass. Increasing samples, changing exposure, adding procedural noise, or adding more supplied fragments did not solve the central visual failure.

## Preserved evidence

- `rebuild-28/heat-cpu.json`, `rebuild-28/material-cpu.json`
- `rebuild-29/refined-front/frame-001000-surface-optics/beauty-6.png`
- `rebuild-30/skin-cpu-check.json`
- `rebuild-30/cooled-front/frame-000750-surface-optics/beauty-6.png`
- `rebuild-31/closed-crust/frame-000750-surface-diagnostic.png`
- Per-case receipts, selected numerical checkpoints, and bounded logs.

To avoid a full disk, regenerable triangle atlases and intermediate checkpoints from rejected trials were removed. Representative states, rendered comparisons, source code, and receipts were retained. No user-authored source assets or public media were deleted.
