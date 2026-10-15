# CYBR Elements — CPU companion

A separate CPU execution path for the existing CYBR Elements code. The GPU
scripts, published films, artwork, player and root README remain unchanged.
This work lives on `feat/cpu-only-flow`; it is not merged into `master`.

## What runs here

**Fire and air:** an end-to-end CPU path from the original approved artwork,
through the existing source-field builder, original PyTorch simulation and
original volume renderer, to a decoded/verified MP4. This is not a replacement
simulation or an image-generated approximation. The production solver and
optics functions are extracted from the actual repository scripts; AST hashes
must match before execution. Unsupported CUDA calls fail closed.

**Blender scenes:** a CPU Cycles adapter for the existing earth, water, ice,
lava and lightning scene scripts. It preserves scene geometry, materials,
cameras, animation and the selected script's sampling/resolution settings.
It forces CPU rendering, CPU OpenImageDenoise and CPU compositing before each
render. Every invocation writes into a new CPU frame directory, so old GPU
frames cannot be silently reused as CPU-rendered results.

The Blender adapter is a rendering entry point, **not a turnkey seven-material
cache-rebuilding orchestrator**. The original scene-specific preparation,
simulation caches, assets and review gates still apply. In particular, the
old Windows-specific `sigil_02_active_water_run.py` queue has not been changed;
do not launch that queue expecting this adapter to change its child processes.

## Install

Use Python 3.11+ (CI uses 3.12). Keep the virtual environment outside the source
checkout so it is not copied into the render workspace. FFmpeg and ffprobe must
be on PATH. Blender scenes require a separate Blender installation compatible
with their source; the original archive used Blender 4.5.3 LTS.

```sh
python -m venv ../cybr-elements-cpu-venv
# Linux/macOS:
source ../cybr-elements-cpu-venv/bin/activate
# Windows PowerShell instead:
# ..\cybr-elements-cpu-venv\Scripts\Activate.ps1

python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r cpu/requirements.txt
```

Blender uses its own Python environment, not the activated virtual environment.
The adapter does not require PyTorch inside Blender. Geometry/cache preparation
scripts may have additional dependencies documented in the original pipeline.

## Production fire or air

Start from a checkout of this branch, or apply the additive `cpu/` directory to
an unchanged compatible checkout. Prepare a fresh workspace **outside** it:

```sh
python cpu/flow.py prepare --workspace ../cybr-elements-cpu-run
python cpu/flow.py gas fire --workspace ../cybr-elements-cpu-run --profile production --threads 8
python cpu/flow.py gas air --workspace ../cybr-elements-cpu-run --profile production --threads 8
python cpu/flow.py verify-original --workspace ../cybr-elements-cpu-run
```

If required retained artwork/assets are missing, restore them into the copied
workspace, not into the source checkout:

```sh
python ../cybr-elements-cpu-run/scripts/fetch_assets.py --all
```

`--all` restores the archive's retained assets and may require substantial disk
space. It is unnecessary when the selected pipeline's inputs already exist.
No substitute artwork is generated for missing inputs.

The production gas preset is **896 × 56 × 504 cells, 1920 × 1080 output,
30 fps, 294 frames, three substeps per frame**. It does not silently select the
legacy low-quality CPU preview. `--frames` explicitly truncates the duration;
`--substeps` explicitly changes the temporal resolution. Both are recorded.
The full grid requires substantially more RAM and computation than the smoke
check. No CPU/GPU speedup or full-production runtime has been established.

Outputs:

```text
../cybr-elements-cpu-run/cpu-results/fire/fire-production.mp4
../cybr-elements-cpu-run/cpu-results/fire/receipt.json
../cybr-elements-cpu-run/cpu-results/air/air-production.mp4
../cybr-elements-cpu-run/cpu-results/air/receipt.json
../cybr-elements-cpu-run/cpu-original-integrity.json
```

A material's existing CPU result directory is not overwritten. Prepare another
workspace for a rerun or a different quality profile. The gas loop replaces
legacy interactive queue waits with an explicit finite execution loop; it does
not manufacture human approval receipts. `humanReviewed` remains false.

## Explicit diagnostic profile

This is a low-resolution functionality test, **not a finished production film**:

```sh
python cpu/flow.py prepare --workspace ../cybr-elements-cpu-smoke
python cpu/flow.py gas fire --workspace ../cybr-elements-cpu-smoke --profile smoke --frames 30 --threads 2 --save-state
python cpu/flow.py gas air --workspace ../cybr-elements-cpu-smoke --profile smoke --frames 30 --threads 2 --save-state
```

The smoke profile uses 128 × 24 × 72 cells and 640 × 360 output. It resamples
source fields and the output integration explicitly; equation/radiance AST
invariants are checked before the diagnostic resize. Full-frame numerical
finiteness checks, actual CPU tensor assertions, FFprobe frame counts and a full
FFmpeg decode run for both profiles. `--save-state` writes the final tensor for
subsequent comparisons; it is not a simulation-resume feature.

## CPU Blender rendering

Use the actual scene script and its normal full-quality arguments. For example,
**after preparing that scene's geometry, textures and density caches in the
CPU workspace**, render the ice scene:

```sh
python cpu/flow.py blender --workspace ../cybr-elements-cpu-run --executable blender --script work/element-motion/sigil_02_new_materials.py -- ice --full
```

`--executable` accepts a Blender executable path containing spaces as a quoted
argument. The source script is read from the workspace and adapted in memory;
its file is not rewritten. Material `--full` arguments still select the
original full sampling and resolution; only the compute/denoising backend and
output destination change.

The inspected scene entry points include:

| Material | Existing script | Required upstream work |
| --- | --- | --- |
| Earth | `sigil_02_ground_earth_render.py --full` | Original fracture geometry and scanned rock textures; retained later revisions can be selected explicitly |
| Water | `sigil_02_active_water_render.py --full` | Native APIC/FLIP simulation and mesh caches, including their streaming producer/consumer coordination |
| Ice / lava | `sigil_02_new_materials.py ice --full` or `lava --full` | Fracture geometry, material inputs, rigid trajectories and per-frame gas atlases |
| Lightning | `sigil_02_new_materials.py lightning --full` | Exported discharge trees, gas atlases, black background asset and the original hero-review gate |

Paths in this table are relative to `work/element-motion/`. They are not a
claim that every historical variant has been validated. The renderer refuses
unknown output conventions rather than risking old-frame reuse.

For ice/lava, the existing `--physics-only` mode can export the rigid
trajectories through the CPU Blender adapter. The existing
`sigil_02_atmosphere.py ice` / `lava` is already a CPU solver and generates the
per-frame density atlases from those trajectories. Complete those prerequisites
before starting the render. Consult `docs/PIPELINES.md` and the active-elements
README for retained source dependencies and the original review gates.

New Blender outputs go under:

```text
<workspace>/cpu-results/blender/<script-name>-<unique-id>/frames/
<workspace>/cpu-results/blender/<script-name>-<unique-id>/receipt.json
```

Receipts record actual successful render calls and preserve `completed:false`
on errors. A physics-only execution can complete with zero rendered frames;
that is not proof of rendering. Legacy Blender review gates are not automatically
approved, and missing cache producers can still make those legacy scripts wait.

## What “same output” does and does not mean

For fire/air, the original source-field geometry, solver equations and optics
are reused. CPU and GPU floating-point execution is not guaranteed bit-identical;
matching equation hashes alone does not establish long-sequence visual parity.

For Cycles scenes, the scene and full-quality settings are retained, but CPU
OpenImageDenoise replaces OptiX denoising. Noise and denoised details may differ.

**Lightning is a larger exception:** the published film used Eevee volumetric
lighting. The CPU adapter uses Cycles because this flow must not require a GPU.
It retains the scene's inputs, not an assertion of identical Eevee appearance.
That material needs a native-render comparison before visual parity is claimed.

Nothing here upgrades the physics model: the baseline rigid-fragment lava/ice
remain those baseline effects. The separate lava-development branch is not
merged or modified by this addition.

## Validation and comparison

```sh
python -m unittest discover -s cpu -p 'test_*.py' -v
python cpu/flow.py compare reference.png candidate.png --report parity.json
```

Image comparison requires identical dimensions, performs no registration or
resizing, and reports display-RGB MAE/RMSE/PSNR. It does not auto-approve images.
The original-image file and candidate are each hashed.

Evidence recorded on 2026-09-20:

- The first GitHub Actions run passed all 17 original tests on a CPU-only
  PyTorch wheel, including actual fire and air source execution and rendering.
- The expanded local suite passed **24 tests, no skips**, including fresh
  Blender output isolation and failure-receipt checks. The Blender-specific
  execution checks use a mock and are not a native Blender-render benchmark.
- Both original-artwork gas pipelines completed **30-frame, 640 × 360 CPU
  smoke videos**, passed every finite-state check and fully decoded. Original
  copied-input source hashes remained unchanged.
- Full-resolution CPU production films, native Blender scene renders and
  GPU-versus-CPU visual parity have **not** been validated in this delivery.

`VALIDATION.json` provides machine-readable smoke receipts and the exact source
and video hashes. The CI workflow preserves its own current test log separately.

## Preservation contract

Workspace creation refuses an existing destination, nested source/destination
paths and symlinks. Files are independent byte copies, not hardlinks. Archived
absolute config paths are rebased only inside the copy. Original source hashes
are verified after each managed execution. These checks detect unexpected
changes; they are not an operating-system sandbox for arbitrary third-party
Python scripts. Run only trusted scene sources.

No existing production script, published video, player or `master` ref is
changed by installing or using this companion. The original source license
continues to apply.
