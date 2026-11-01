# ELEMENTS composition runtime

Eighteen existing film entrypoints now select policies, rather than own engines.
The pinned pre-consolidation baseline is `7566fb64a3b91d8b638c560601446b9209e4532e`.

| Owner | Responsibility |
|---|---|
| `element_scenes.py` | Original scene/motion/source/artifact configuration |
| `fire_dynamics.py` | Reactive injection, chemistry, heat and fed-fuel policies |
| `air_dynamics.py` | Passive tracer/source policies, including distinct style-02 densities/loss |
| `dust_dynamics.py` | Existing dust injection/loss policy |
| `element_flow.py` | Unchanged shared transport, limiter, vorticity/projection |
| `element_choreography.py` | Composes domain stage, prescribed steering and flow projection |
| `element_session.py` | Independent field/state/grid, control cache, native sample index |
| `element_optics.py` | Distinct preserved radiance, volume integration and capture policies |
| `element_runner.py` | CLI, state checkpoints, actual PNG samples, encoder and receipts |
| `element_receipts.py` | Bounded state readback also used by the film differential runner |

No original numerical functions are loaded through runtime AST execution or
copied into the thin entrypoints. Tests load pinned Git originals as oracles.
The historical generators no longer overwrite the maintained style-02 engines.

## Run and resume

```sh
python fire-v3.py --device cpu --seconds 2 --fps 24 --output /path/to/new-run
python fire-v3.py --device cpu --seconds 2 --fps 24 --output /path/to/new-run --resume latest
```

Automatic selection uses available CUDA, otherwise CPU; explicit overrides are supported. Production style-02 source requires
its actual 896 x 504 NPZ fields and a matching grid. Only diagnostic tests resize
source fields. Source, geometry and camera bounds are not fitted to the output.

Every encoded frame follows one actual simulation sample with `substeps` steps
of `dt = 1 / (fps * substeps)`. Movie fps equals sample fps. The preserved 294
style-02 samples last 12.25 seconds at 24 fps or 9.8 seconds at 30 fps; explicit
`--seconds` instead selects a native simulation duration. No duplicate padding,
interpolated motion, reverse playback, optical fade or artificial slowed loop is
introduced by the runner.

Style-02 review gates stop after frame 135, save a checkpoint and report the
original continuation-marker path. The runtime does not create that marker.
No full-film completion is written until all actual samples and encoding pass.

Checkpoints include the fed-fuel reservoir, mutated control-frame cache, native
sample position, configuration, backend and source/asset hashes. Mismatched
lineage is rejected. Completed outputs and numbered checkpoints are preserved.
A resumed interrupted encode preserves its uncompleted movie under an
`.incomplete-<timestamp>` suffix before rebuilding from existing native PNGs.

## Scope of verification

Legacy domains: 180 exact whole-step comparisons and 15 original 1080p RGB
comparisons. Maintained style-02: 24 exact whole-step comparisons, two 1080p RGB
comparisons and normalized-AST optics identity. Original air recipe and actual
CLI checkpoint/resume are additionally checked. A fresh original spline-scene
48-frame 1080p run matched every original state and RGB sample exactly.

These establish scoped behavior preservation and consolidation, not a new
visual quality improvement, full-film/GPU parity, physical calibration, or a
replacement for latest/best FIRE/FOREST assets. Distinct domain methods remain
separate. Other historical recipes outside this registry remain to migrate.

The optional root Python wheel currently exports the portable NumPy lava optics
API, `cybr_elements.lava_optics`, for real SCENES consumers. It preserves the
analytic-observer port, not an assertion of Mitsuba CIE-table equivalence. Its
Planck temperature is kelvin, unlike the flow solver's normalized temperature.

## Source acceptance and CPU resources

`python element_availability.py` lists real input readiness for every recipe.
`python fire-shared.py --check-inputs` checks one recipe without allocating its
simulation grid. Input-ready is deliberately not labeled film-complete. The
restored shared trail matches the original public source byte-for-byte. All 18
default recipes now include their required inputs. The fed-fire stroke at
`sigil-native/c-stroke.npz` is the exact 6,417-byte original from the v0.1.0
`project-assets-047.zip` release, verified against `docs/assets.json`; its compact
provenance is retained in `sigil-native/c-stroke.provenance.json`. Both source
inputs are tracked and included in runtime source archives. Optional gesture21/21b
still requires the original modules. Missing inputs are reported before allocation,
not replaced with fabricated trajectories. Restoring input readiness does not
qualify execution, CUDA parity or any completed film.

The CPU transport performs the identical independent scalar operations one
channel at a time, bounding correction/pool temporaries. The CUDA arithmetic
path remains unchanged and unqualified on this CPU-only worker. No spatial
tiling, source resizing, reduced grid or altered timestep is used.

An actual original 896 x 56 x 504 CPU sample completed all three substeps, full
1080p reconstruction, native-cadence encoding and a complete 809,238,528-byte
state checkpoint. Its checkpoint state bytes exactly match the native receipt.
The serialized trial took 98.6 seconds at two CPU threads and approximately
3.63 GB sampled resident memory. This was pre-ignition feasibility evidence,
not a visually active clip or a completed 294-frame film. Reserve additional
RAM for the environment; measured state bytes alone are not peak solver memory.
The earlier full-channel CPU trial was SIGKILLed before producing a frame.

Backend selection defaults to `--device auto`: available CUDA selects CUDA;
otherwise CPU. Explicit `--device cpu` and `--device cuda` remain authoritative.
An unavailable explicitly requested CUDA backend fails, and a CUDA allocation or
execution failure never triggers a CPU retry. Existing CUDA resource guards
remain active. Checkpoint identities and completion receipts record the resolved
backend (`cpu` or `cuda`), not the `auto` selection policy.
