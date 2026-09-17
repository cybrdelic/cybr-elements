# Lava material stages

The stage images are authored material views: magma as an illustrative cutaway, exposed lava, heavy cooling crust, cold basalt, and a separate silica-rich obsidian branch. They are not five frames from a complete crystallization simulation.

All simulation, rendering, volume integration, denoising and encoding in this study run on the CPU. Mitsuba uses `scalar_rgb`; OIDN explicitly selects its CPU device. Run jobs through `bounded.py` (two logical cores, 3 GiB process-tree limit, at most 180 seconds per job).

## Reproduce

Run from the `mitsuba-rebuild` folder using `.venv/Scripts/python.exe`:

```text
bounded.py --seconds 90 lava_stages_build.py
bounded.py --seconds 30 lava_magma_cutaway.py
bounded.py --seconds 160 lava_stage_flow.py --frames 32 --seconds 12
bounded.py --seconds 35 lava_stage_grid_qa.py
bounded.py --seconds 180 lava_stage_job.py cooling --width 960 --spp 8
bounded.py --seconds 160 lava_movie_job.py --start 0 --end 6
```

Other still names are `magma`, `lava`, `basalt`, and `obsidian`. Movie batches may contain at most six frames. Resume completed batches using their source mesh hashes. `lava_stages_publish.py --prepare-only` prepares contact sheets and a movie in this work directory before publication.

## What is simulated

- Conservative finite-volume, depth-averaged viscous flow with a Bingham yield approximation. Positive lagged mobility is solved with backward Euler; fluxes retain a donor-volume limit. Five liquid substeps run per gas step.
- Temperature is advected conservatively and loses heat by radiation and convection. The viscosity depends on the depth-averaged temperature. Effective reference viscosity is 6,500 Pa·s for the heavy-crust motion study.
- Crust pieces follow the flow as rigid translations and changes in surface height. They do not receive fracture, collision, rotation, or contact forces.
- The plume uses staggered MAC velocities, pressure projection, buoyancy, semi-Lagrangian heat/moisture transport, diffusion, and vorticity confinement. Condensate opacity is an approximate equilibrium diagnostic. Latent heat and gas chemistry are omitted. The velocity domain is closed with an absorbing upper scalar layer.

## What is rendered

Mitsuba traces the surfaces. Thermal emission comes from integrated Planck radiance. Rock pores use a CPU three-dimensional gradient texture instead of stretched two-dimensional UVs. The obsidian still uses the opaque optical limit of a thick, strongly absorbing glass specimen, with dielectric Fresnel reflection and faint residual scattering. `LAVA_TRANSMISSIVE_OBSIDIAN=1` retains a comparison preset with true transmission and absorption.

Motion uses deterministic CPU single scattering over the saved plume field: Beer–Lambert extinction, a Henyey–Greenstein phase function, volume light attenuation and Mitsuba depth occlusion. Area lights and hot patches use point quadrature; multiple scattering and plume-to-surface lighting feedback are omitted.

`motion/simulation.json` records the mass and thermal ledgers. `motion/grid-qa.json` records timestep sensitivity and a height-grid curvature check. These numerical checks do not establish photorealism or agreement with measured lava.

The old lava gallery and source meshes are preserved. Only regenerable PLY render intermediates were removed when the disk filled.
