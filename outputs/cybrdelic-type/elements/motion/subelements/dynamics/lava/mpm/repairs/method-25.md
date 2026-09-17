# Lava repairs — solver 25

This is ongoing CPU development, not a finished lava simulation. The reviewed Mitsuba image is an optical diagnostic of the saved 22-second cooling state. It is not an image-generator substitute and it is not proof of full fracture or photorealism.

## Corrected mechanisms

- Conservative bounded heat transfer prevents FLIP enthalpy overshoot. Before the correction, a 1450 K source produced particle temperatures above 1467 K without sufficient mechanical heat. The corrected transfer blends conservative PIC and FLIP candidates with one bound-preserving coefficient; it adds numerical diffusion when limiting is necessary.
- Crack release uses accepted damage and the failed endpoint's normal. This prevents trial iterations from alternately tearing and reconnecting topology, and prevents intact neighbours from bridging a failed band.
- Safeguarded Anderson iteration accelerates the same coupled equations. A short comparison reduced iterations from 114 to 23 while keeping damage differences below 2.3e-7.
- Pressure cells are eliminated before Coulomb contact. Factor lifetimes and response RHS batches reduce memory peaks. Unloaded friction cones use the already-converged normal solution. Long fragmented flows remain unverified.
- The new natural-flow driver uses a published dry-melt viscosity relation and a separate glass-free basalt power-creep reference. Isochoric rock creep does not relax hydrostatic strain.
- Unbroken crystallizing material retains a smooth volume-constrained surface. Solid fraction alone no longer changes it to exposed quadrature cubes. The final hybrid path surfaces the liquid from density and subtracts only the actual positive gaps between separated coherent faces. An analytic 120 micrometre opening is reproduced without widening, with removed-volume error below 3.2e-24 cubic metres. Closed and compressed faces do not produce cuts. This also avoids representing the five inverted liquid inlet cells as solid surface geometry. The former bounded exterior-projection experiment remains a diagnostic, not the final surfacing path.
- Optical microrelief uses persistent material coordinates and their tangential Jacobian. Its nominal amplitude is 60 micrometres, replacing the former 1.1 mm world-space bump. Phase roughness is interpolated continuously. This optical detail does not create cracks.

## Evidence and limits

32 current-source component/integration checks pass, plus separate material-coordinate and surface-continuity checks. These checks do not certify the complete lava shot.

The cooled lobe reaches 22 seconds, with approximately 17% maximum continuum damage and no separated cracks. The physical inlet test has reached 10.5368 seconds with maximum damage 0.9951, 6 broken connectivity edges, and mass error -8.13e-20 kg. Its last status is incomplete: TimeoutError('CPU screening budget reached').

A historical notched specimen opens completely at the finer tested timestep, but the medium/fine work values differ by 11.4% and crack connectivity differs. Full-fracture temporal convergence is therefore not passed. Spatial convergence is not established.

The melt and solid reference laws are from different experiments. The rock power law was measured at 300 MPa confinement; free-surface use is an extrapolation. Crystal fraction, fracture parameters and crystallization kinetics are not composition-calibrated. The current render is a small CPU check, not a final-quality image.

## Primary references

- [Farrell et al. — experimental lava viscosity, Eq. 3](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019JB018815)
- [Violay et al. — basalt brittle–ductile transition, Table 4](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2011JB008884)
- [Storvik et al. — accelerated staggered phase-field scheme](https://arxiv.org/pdf/2008.11787)

## Reproduction

Use the local `.venv/Scripts/python.exe` and run the CPU jobs sequentially. No GPU renderer or Houdini is used. `lava_mpm_inflation25.py --name fed-contact-batch --until 10 --wall 180 --dt 0.15` resumes only with unchanged solver hashes. `lava_mpm_rebuild25_check.py`, `lava_mpm_rebuild_suite.py` and `lava_mpm_rebuild_smoke.py` produce current-source numerical checks. `lava_mpm_surface25_check.py` and `lava_material_texture_check.py` cover the surface and optical repairs. Incomplete screening runs save accepted state and return a nonzero exit status.
