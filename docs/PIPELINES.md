# Simulation and rendering pipelines

The supported browser entry point is `python scripts/serve.py`. It serves
rendered films and font specimens, without starting a simulation. Production
sources live in `work/element-motion/`; they form an offline graphics research
archive rather than a single packaged renderer.

## Current pipeline sources

All filenames below are relative to `work/element-motion/`.

| Material | Main sources | Method |
| --- | --- | --- |
| Fire | `sigil_02_source.py`, `sigil_02_build_v2.py`, `sigil_02_fire_v2.py` | Artwork source fields, reactive gas transport, cooling, buoyancy and custom volume rendering |
| Air | `sigil_02_air_v2.py` | 3D gas transport and turbulent smoke rendering |
| Earth | `sigil_02_ground_earth_build.py`, `sigil_02_ground_earth_render.py`, subsequent arrival revisions | Guided fragments, then Bullet rigid collisions and floor settling |
| Water | `sigil_02_active_water.mjs`, `sigil_02_active_mesh.py`, `sigil_02_active_water_render.py` | APIC/FLIP, pressure projection, reconstructed liquid surfaces and Cycles optics |
| Ice / lava | `sigil_02_new_materials.py`, `sigil_02_atmosphere.py` | Fractured solids, Bullet release, advected gas and surface rendering |
| Lightning | `sigil_02_electric_tree_export.py`, `sigil_02_atmosphere.py`, `sigil_02_new_materials.py` | 3D growth trees, pulse timing, channel lights and volumetric clouds |

The current films are in
`outputs/cybrdelic-type/elements/motion/bending/sigils/02/`. Historical production
notes and diagnostic files remain under
`work/element-motion/sigil-02-active-elements/`; their completion records describe
past render runs, not current automated test results.

## Water

`sigil_02_active_water.mjs` runs the vendored JavaScript `FlipSolver` through
Node.js. The solver uses quadratic APIC/FLIP transfers, affine particle data,
multigrid-preconditioned conjugate-gradient pressure solves, surface tension
and floor collisions. The water production segment evolves 138,022 parcels
for 240 frames; the smaller CPU configuration uses 24,698 parcels.

The unsupported hovering form is deliberately controlled. Gravity remains
active during the hold. Bounded horizontal/depth forces contain the mark, and
vertical recovery waits for sag. A deterministic 1/193 subset of parcels is
exempted from upward recovery, allowing small droplets to fall. These external
forces are authored animation controls, not a naturally stable fluid shape.

Reconstruction uses the liquid particles for both the main surface and detached
clusters. Isolated clusters become droplets with volume/velocity taken from
their particles. Their resolution is limited by particle spacing.

The final edit retains a 3.4-second opening from the previous film and overlaps
the new segment by 0.2 seconds. That opening is reverse playback of a solved
breakup; the new hold and release run forward. The full film is therefore an
edited sequence, not one continuous forward simulation.

## Fire and gas

The fire implementation uses PyTorch/CUDA to transport velocity, fuel, oxidizer
and heat on a 3D grid. It includes projected velocity, limited MacCormack
scalar transport, reaction, cooling, buoyancy and authored wind/source controls.
It is a graphics combustion model, without calibrated chemical kinetics.

The ice/lava/lightning atmosphere implementation uses CPU semi-Lagrangian
advection, buoyancy, dissipation and Fourier-space Helmholtz pressure projection.
The FFT solve is periodic; padding and absorbing edges reduce visible boundary
effects. Emission and small-scale forcing are authored. Ice/lava emitters follow
the per-frame fracture transforms.

The current `gas_projection.py` zeros derivatives at self-conjugate Nyquist
modes to keep the real-valued FFT projection valid. The divergence guarantee
applies to the periodic projection step; the absorbing-edge mask can introduce
local divergence afterward. The included films predate this solver correction
and have not been rerendered.

PNG atlases encode slices of the 3D density field. The renderer samples those
fields as volumes. Eevee uses explicit trilinear atlas sampling to avoid mip
filtering across unrelated slices; Cycles uses its volume sampling path.

## Fractured solids and electricity

Earth, ice and lava use authored assembly and suspension trajectories. Released
fragments use Bullet inter-body/floor collision handling. Ice and lava each use
174 fragments, with material-specific mass, friction and damping.

Ice uses transmission, blue absorption and fracture surface detail. Lava uses
displaced basalt crust over emissive interior geometry, with authored cooling.
These are solid-fracture effects. There is no latent-heat solve, freezing or
melting transition, liquid-lava rheology or thermally driven fracture creation.

Lightning uses retained 3D branching growth trees with trunk, fork and finer
branch widths. Irregular authored pulses and channel lights illuminate advected
gas. This is a visual discharge model rather than an electromagnetic or plasma
simulation. `sigil_02_native_volume_experiment.py` and `sigil_02_electric_paths.py`
are retained experiments, not the current final lightning pipeline.

Cycles renders the current water, ice and lava surfaces. Lightning uses Eevee
volumetric lighting. Full-resolution OptiX settings were developed for the
original NVIDIA production machine.

## Rebuilding

The production environment used Windows, Python 3.12, Node.js 20+, Blender 4.5.3
LTS and an NVIDIA RTX 4060 Laptop GPU. Browser playback and repository tooling
do not depend on this environment. Full rendering has not been verified across
operating systems or GPU vendors.

Restore retained inputs with `python scripts/fetch_assets.py --all`. The release
excludes regenerated per-frame render caches, solver checkpoints, gas atlases,
local environments and compiled caches. Restoring inputs does not make a render
resumable without rebuilding those outputs.

Python dependencies vary by pipeline:

| Pipeline | Dependencies |
| --- | --- |
| Water reconstruction | NumPy, SciPy, scikit-image, Numba; Node.js for the solver |
| Local atmospheres | NumPy, SciPy, Pillow |
| Reactive fire | Compatible CUDA/PyTorch installation, NumPy, Pillow |
| Blender rendering | Blender and the packages available in its Python environment |
| Fonts | NumPy, OpenCV, Pillow, Shapely, fontTools, Brotli; see specimen sources |
| Encoding/showcase | FFmpeg/ffprobe, Pillow |

Other retained experiments use Mitsuba, Warp, OpenCV and Shapely. They are not
universal prerequisites and are not needed to view the current showcase.

Before a production run:

1. Inspect the chosen source and configuration for local input paths, output
   revisions and renderer settings. Historical scripts still contain absolute
   Windows paths and cache references.
2. Use a fresh output revision. Existing completed simulations have guards
   against replacement, and some queues wait for review files.
3. Run the small configuration and representative render frames first. Inspect
   finite state, convergence, silhouettes, volume accounting and floor contact.
4. Reserve storage for regenerated per-frame data and run one GPU render at a
   time. Concurrent rendering slowed the original laptop production machine.
5. Encode and fully decode the final film, inspect its motion, and run the
   repository/player checks before promoting it.

`sigil_02_active_water_run.py` orchestrates the solver, reconstruction and
Cycles rendering. It accepts executables from PATH, `--node`/`--blender`, or
`NODE_BIN`/`BLENDER_BIN`; `--output` selects a fresh revision. `--input-root`
and `--force-root` allow retained inputs to be located explicitly. The input
preflight can run without starting workers or writing files:

```sh
python work/element-motion/sigil_02_active_water_run.py \
  --output work/element-motion/sigil-02-active-elements/water-preview-new \
  --dry-run
```

The default pipeline is a CPU preview; `--full` selects production settings.
Preflight verifies input files and executable paths, not every installed
render dependency. Fresh revisions copy the selected configuration, parcels
and reconstruction guides; legacy input paths fall back to repository-relative
locations. CPU previews use OpenImageDenoise. Full rendering selects an available
Blender compute backend and falls back to CPU when none is available.
The supervisor propagates worker failures and terminates
the remaining workers. `--timeout` and `--minimum-free-mb` bound runtime and
the remaining disk reserve. These improvements to orchestration do not imply
that full renders have been verified on another platform.

`sigil_02_active_material_queue.py` queues ice/lava/lightning
production with existing review gates. Inspect their inputs before execution;
neither is a general batch runner for the whole research directory.

## Fonts and README montage

Typeface sources, coverage and rebuild instructions are in
`outputs/cybrdelic-type/typefaces/README.md`.

With FFmpeg and Pillow installed, `python scripts/build_showcase.py` rebuilds
`docs/media/elements-02.gif` from the current seven MP4s on the CPU. It also writes
the still montage and timing/source metadata. This does not run a simulation or
change the films.
