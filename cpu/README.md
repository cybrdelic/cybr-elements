# CYBR ELEMENTS — parallel CPU flow

An **additive, offline CPU execution path for the seven published 02 element films**.
The existing GPU scripts, films, site, and research branches are not changed.
This flow uses the adopted source at `280770daa8b78274339d26ad45a58f62aeeda39b`;
it does not substitute the later, unmerged lava experiments for the published lava.

## Run

Use Python 3.12 or 3.13, FFmpeg/FFprobe, and a fresh virtual environment.
Blender **4.5 LTS** is required for earth, water, ice, lava, and lightning;
4.5.3 was the adopted production version. Water also needs Node.js 20 or newer.

```sh
python -m venv .venv-cpu
# Linux/macOS: source .venv-cpu/bin/activate
# PowerShell: .venv-cpu\Scripts\Activate.ps1
python -m pip install -r cpu/requirements.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu

python cpu/run.py plan --elements all
python cpu/run.py doctor --elements all --blender /path/to/blender
python cpu/run.py run --elements all --output ../elements-cpu-01 \
  --restore-inputs --blender /path/to/blender --threads 8
```

On macOS install the normal CPU-capable PyTorch wheel with `python -m pip install torch`.
No CUDA toolkit, NVIDIA GPU, OptiX, or hardware video encoder is required.
`--restore-inputs` retrieves **only required assets** from the repository's existing
release packs, checks their published SHA-256/size, and writes them into the new
workspace. It does not restore or overwrite files in your checkout.
The optional `--input-cache /path/to/cache` reads an existing mirror of those
asset paths, with the same manifest verification.

**Lightning:** the published scene uses Eevee, not Cycles. Its CPU-equivalent
route requires **Linux + Mesa software rendering + Xvfb**. For example, on Ubuntu:

```sh
sudo apt-get update
sudo apt-get install ffmpeg xvfb xauth libgl1-mesa-dri libegl1 \
  libxi6 libxrender1 libxxf86vm1 libxkbcommon0 libsm6
python cpu/run.py probe --elements ice lightning --output ../cpu-backend-probe \
  --blender /path/to/blender
```

The probe actually renders with Cycles CPU and software Eevee; the latter must
report `llvmpipe` or `softpipe`. The full run repeats these checks before work.
It does **not** silently use a physical GPU or change the lightning renderer.
Windows/macOS users can run the other six with
`--elements fire air earth water ice lava`; the same-Eevee lightning route is Linux-only.
The Linux route can also be used in a suitable Linux VM or WSL environment with
Mesa/Xvfb installed, but those environments have not been validated here.

## What is preserved

| Element | CPU execution | Production target |
|---|---|---|
| Fire | Original PyTorch reactive flow, FFT projection, MacCormack transport and volume integration, tensors on CPU | 896 × 56 × 504 cells; 294 frames |
| Air | Original PyTorch gas solve and original optical integration on CPU | 896 × 56 × 504 cells; 294 frames |
| Earth | Original geometry, materials, authored motion, Bullet release, Cycles CPU | 390 fresh source frames, original 300-frame arrival edit |
| Water | Original native JavaScript APIC/FLIP → original surface reconstruction → Cycles CPU | Original full grid/particles; 240 fresh native frames; published edit produces 336 frames |
| Ice / lava | Original fracture/Bullet scene, original CPU atmosphere solve, Cycles CPU | 300 frames each |
| Lightning | Original discharge geometry, atmosphere, materials and Eevee scene, executed by a CPU rasterizer | 300 frames |

Production outputs remain **1920 × 1080 at 30 fps**. Original production sample
counts, materials, cameras, reconstruction settings and bounce limits are retained.
Gas is explicitly advanced at 30 simulation frames/second with three substeps;
the original parser defaults to three substeps, but the archived GPU receipt does
not record its complete launch command. Exact historical timing/parity therefore
still needs a reference-film comparison. The new receipt records the full command.

The numerical functions `advect`, `derivative`, `divergence`, `step`, and `radiance`
and the production `render` function are checked for AST equality before a gas
adapter is executed. Blender material/geometry builder functions are also covered
by preservation tests. Generated execution copies and an exact change receipt
are kept under the new workspace; the originals are never edited.

### Necessary differences and provenance

**CPU does not imply lower resolution.** It does imply different execution cost.
No automatic quality reduction is made. Full-resolution jobs can require substantial
RAM and long offline render time. Peak RAM and elapsed times from the small diagnostic
are not reliable estimates for the production jobs; no full-film CPU benchmark is claimed.

CPU and GPU floating-point implementations can diverge over time, especially in
fluid simulations. **CPU OpenImageDenoise replaces OptiX denoising** in Cycles;
its final pixels can differ even with identical scene and sample settings.
Software Eevee is gated by a real renderer probe, but this is not a pixel-parity proof.

The published earth entrance is an edit, not a fresh forward gathering simulation.
The CPU flow applies the same source-frame mapping to its newly rendered 390-frame
clip: `[330..210 descending] + [211..389 ascending]`.

The published water r8 edit includes a retained r7 opening. By default the CPU flow
retains those first 102 source frames and crossfades the freshly CPU-simulated
240-frame segment using the original 0.20-second overlap at 3.20 seconds.
The receipt explicitly records the reuse; **the opening is not claimed as a new CPU render**.
For a wholly fresh simulation/render sequence, omit the historical edit:

```sh
python cpu/run.py run --elements water --native-water --output ../water-cpu-native \
  --restore-inputs --blender /path/to/blender
```

This produces the original eight-second native segment, not the 11.2-second edited film.
The current published lava is a rigid-fracture/material treatment, not a calibrated
viscoelastic lava solver; changing execution device does not change that model.

## Outputs and safety

`--output` must identify a **new directory outside the checkout**. Existing directories,
checkout descendants, and checkout ancestors are refused. No publication script runs,
and no existing gallery, README, film, cache, or default branch is updated.

```text
elements-cpu-01/
  index.html                 separate CPU candidate player
  receipt.json               commands, source/input hashes, devices, changes, timing
  films/                     verified CPU films and retained native intermediates
  logs/                      one log per process/stage
  workspace/                 copied inputs and generated CPU execution drivers
```

Inputs are copied, never hard-linked. CPU accelerator visibility is disabled;
Cycles CPU/device/denoiser/compositor settings are enforced. FFmpeg uses software
`libx264`. Each finished film is checked for resolution, frame count, frame rate,
SHA-256, and successful complete decoding before the overall run succeeds.

Water's producer, mesher, and renderer run concurrently because the original
bounded-cache protocol would deadlock if they were run sequentially. Only manifest
publication is made atomic in the copied JavaScript/mesher drivers; simulation and
reconstruction equations are not changed. Completed caches are consumed inside the
isolated workspace, never from the original project.

A worker failure, disk-reserve violation, timeout, or Ctrl-C terminates its process
group/peers and preserves logs. `--timeout` sets the per-stage limit in seconds
(default 604800); `--disk-reserve-mib` defaults to 1024. `--threads` is per worker,
not an aggregate cap across water's concurrent stages. Some original NumPy/Numba
helpers retain their own two-thread settings.

Interactive source/hero pauses are skipped for unattended execution. **No approval
files are fabricated:** every receipt keeps visual acceptance pending. This version
requires a new output revision for each run and does not claim checkpoint resume.

## Validation

```sh
python -m unittest discover -s cpu/tests -v
python cpu/run.py smoke --elements fire air --frames 144 --output ../cpu-smoke-01 \
  --restore-inputs --threads 2
```

Smoke mode is explicit: **128 × 16 × 72 cells, 320 × 180 output**, using a resampled
copy of the original source field and unchanged gas equations. It is an execution
test, not a production-quality preview or a GPU/CPU parity demonstration.

Local validation executed both 144-frame gas sequences end-to-end with CPU-only
PyTorch, decoded every frame, and verified the original source hashes were unchanged.
See `verification.json` for measured results and their scope. Blender production
films and the complete native water pipeline were **not** executed in that environment,
which did not contain Blender and was limited to 4 GiB RAM.

The separate `elements-cpu.yml` workflow runs contract tests and gas integration
on CPU-only GitHub-hosted runners, plus actual Cycles/Mesa backend probes. Backend
probe success alone does not certify the full production scenes. CI results are
reported by GitHub; this document does not pre-claim that a newly scheduled run passed.

`upstream.json` pins the adopted source bytes. A change to those drivers fails closed
until the adapter and tests are reviewed and the source lock is deliberately updated.
No old GPU source is overwritten to make the CPU tests pass.
