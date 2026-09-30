# Adaptive volume candidate

An initial implementation is available behind the existing Fire Studio page.
The sparse flow, chemistry pool and fine pressure work lists are experimental
and disabled by default. They have not earned a replacement or mobile claim.
Precise incident-light receiver support is also opt-in pending a stable
complete-frame cost gate, despite exact pixels and lower isolated lighting cost.
Original's solver and fire detail are unchanged.
Sparse composite pressure and eliminating dense fallback backing remain
unfinished. This candidate does not yet meet the requested replacement target.

The default's generated simulation, pressure and renderer operators match
rc.10 after ignoring comments/whitespace. A two-frame production-host comparison
also matches all 271 GPU resources, 32 recorded operations and 20 uploaded
payloads. Fine-flow support atomics are compiled only when that solver is
explicitly selected. The gated architecture adds no default GPU workload.

## Storage and execution

| Part | Implementation | Important constraint |
| --- | --- | --- |
| Fine chemistry | Direct RGBA16F atlas transport and combustion at 256³ voxel spacing | Soot, temperature, fuel and oxygen deficit are all retained. |
| Chemistry work | Original 8³ active-brick source/transport list | Allocation padding never creates additional reaction work. |
| Physical pool | Fixed 16³ pages, stable slots, two page tables and generation/owner checks | Current/predictor/destination share a frozen topology during a substep. |
| Sampling support | Conservative source/CFL request halo, hardware filtering within pages and eight logical voxel reads across seams | No copied texture halo or dropped neighbor reads. |
| Flow | Global 64³ MAC evolution with conservative face restriction/prolongation and local 128³ overrides | Fine residual, chemistry, source, obstacle and neighbor support participate in refinement. |
| Pressure | Canonical global 128³ projection and its 64³-to-4³ multigrid hierarchy | Optional fine smoothing work lists preserve the global pressure response. |
| Incident lighting | Separate eight-bit receiver support per optical brick | Every positive-soot interpolation footprint is covered; camera and shadow masks retain their full existing halo. |

The initial safe pool integration retains three dense chemistry textures for
lossless capacity fallback. The runtime's 1,024-page pool adds **96 MiB** to the
existing **384 MiB** dense chemistry allocation. This is not a memory saving or
a mobile solution. The allocator's capacity, density and generation preflight
selects sticky dense mode before changing ownership. It migrates every current
RGBA channel once, acknowledges migration, and continues on dense storage.
It never drops tiles, resizes GPU resources during a step, or waits on a CPU map
to decide dispatch.

New slots clear all three chemistry generations. Retained slots keep their
contents; reused slots receive a new generation. Buoyancy, normal/tree surface
damage, particles, camera rays, emission gathering, room bounce and shadow rays
all read the same current logical chemistry field. Migration precedes those
consumers. Restart resets allocation and refinement eligibility in place.

Dense flow fallback is also sticky until a clean reset. The unchanged fine
coverage and outer packed-face guards disable bulk flow classification after
fallback. Dense physics continues; simulation frames are not skipped. The
small finalizer uses a direct workgroup because a buffer cannot be writable
storage and an indirect argument source within the same compute dispatch.

## Pressure remains global

A plume affects surrounding air even where chemistry is zero. Houdini's sparse
mode documents different interaction between distant puffs when their inactive
regions are treated as vacuum. This candidate keeps the globally connected
pressure domain. [SideFX sparse pyro documentation](https://www.sidefx.com/docs/houdini/pyro/sparsity.html)

The exact fine pressure work list matched pressure, projected MAC velocity and
divergence in 30 native comparisons at 32³ and 128³. Its isolated sparse smoothing
segment improved 1.271 → 1.141 ms on Intel UHD, but a complete V-cycle regressed
4.027 → 4.115 ms. Global prolongation makes much of post-smoothing work dense;
classification and inactive copies erase the local saving. It stays optional.

An attempted coarse-first solve failed convergence even with dense fine
fallback. At 32³, residual L1 rose 0.595 → 0.839 for a compact source,
0.552 → 0.782 at an interface, and 0.0411 → 0.172 near floor/open boundaries.
Two cycles also failed. That alternative is rejected. This implementation is
not a completed sparse composite pressure hierarchy: dense fine backing and
global fine projection remain necessary for its current conservation contract.

A private exact three-sweep temporal pressure tile also failed its cost gate.
It matched current pressure, projected MAC velocity and divergence in 60 native
checks at 32³ and 128³ on both GPUs. At 128³, a compact-source complete V-cycle
cost rose 5.187 → 20.874 ms on Intel and 1.110 → 2.272 ms on RTX. Its halo performs
2,008 updates per 256 final cells versus 768 in three dense passes and uses
15,680 bytes of shared memory. Removing dispatches and texture writes did not
offset that work. It remains private; production pressure is unchanged.

## Measured lighting improvement

The precise receiver path keeps the original 4³ lighting workgroups,
64³ light texture, shadow samples and lighting formulas. Support generation is
fused with the existing optical dilation. Every output texel is refreshed,
including clears after support shrinks or disappears.

- Intel UHD: total support-generation plus incident-lighting cost fell
  **8.7–14.2%** across five views.
- RTX 4060: the same cost fell **6.7–8.3%**.
- **34 paired real/synthetic views were pixel-identical**, including faint soot,
  cold soot, heat without soot, boundary support and angled smoke inspection.
- Required incident components and full camera/shadow masks matched exactly.

These are calibrated native GPU measurements on held production chemistry.
They are not whole-solver gains or browser FPS. Generic compacted, shared-light
and parallel-ray lighting alternatives were slower; they are not the default.

A later production-command check confirmed lower held lighting cost even for
thin fire at 0.4 seconds (1.244 → 1.155 ms) and at 2 seconds (2.739 → 2.663 ms),
with identical pixels. Fused support adds only 4–5 µs; incident lighting drops
70–229 µs. Unpaired complete-frame Intel runs measured 23.04 ms reference versus
24.07 ms receivers. Instrumented identical replays varied 35.34 → 103.29 ms,
including large variation in unchanged velocity kernels. These whole-frame
results are inconclusive. Receivers remain opt-in until a stable gate passes.

## Current candidate results and limits

Before sticky fallback, a matched four-second Intel bonfire measured 29.60 ms
dense versus 32.18 ms candidate median completed native wall time. At 1.5 seconds,
fine coverage was only 28%, but the positive outer-face ownership guard forced
dense flow. Continuing to rebuild sparse lists then added work. The sticky
fallback addresses that specific overhead. The final production-command replay
uses a separate matched 60-frame, one-simulated-second sequence with source
movement and several camera views. All four variants passed native command,
binding and measured CFL checks on Intel UHD and RTX 4060. The following are
calibrated submitted GPU milliseconds for frames 8–59; compilation, evidence
readbacks and angle-only frames are excluded. These are short cost comparisons,
not sustained frame-rate measurements.
All four frozen QA variants used matching fine-flow support bits. The final
default omits those unused atomics, so this table is a matched development
comparison rather than a measurement of the shipped default.

| Variant | Intel median / p95 (ms) | RTX median / p95 (ms) |
| --- | ---: | ---: |
| Dense | 27.27 / 101.64 | 4.12 / 13.36 |
| Chemistry pool | 36.79 / 115.33 | 7.75 / 58.08 |
| Coarse/fine flow | 24.10 / 81.54 | 6.63 / 49.86 |
| Pool plus flow | 31.65 / 126.15 | 5.12 / 40.09 |

The pool and combined path fail the speed gate. Flow improves this Intel
fixture but regresses on RTX. All remain disabled by default. A private scalar
page lookup cache preserved every tested half-float field and image, but measured
40.06 / 133.57 ms on Intel and 5.46 / 17.50 ms on RTX. It was rejected for
production because it worsened Intel cost and still exceeded dense RTX cost.

A second private trial changed scalar execution from eight 64-lane groups to
two 256-lane groups per fine brick. Full chemistry fields, predictor, transport
and optical masks, and all 13 captured images were exact on both GPUs. Held
scalar cost fell 4.5–5.9% for dense Intel chemistry and only 0.7–0.9% on RTX;
pooled chemistry became 5.3–7.2% slower on Intel and 1.4–1.5% slower on RTX.
The layout is not promoted. These are scalar-stage measurements, not
complete-frame improvements.

The existing solver already dispatches chemistry over active 8³ bricks. A
physical pool therefore does not remove those chemistry invocations; it changes
storage and adds address resolution. Globally moving air also makes fine flow
refinement expand or fall back to dense work. These measurements do not support
sparse storage as a standalone speed fix for this implementation.

Atlas filtering is not bit-identical to dense hardware filtering. One-step
fixtures differed by a few half-float ULP; the RTX moving fixture exceeded its
provisional 0.003 absolute-temperature gate (0.00390625). Masks matched, and
dense fallback was half-bit identical. This is an open quality gate, not a
reason to silently relax the threshold.

At one second, pooled chemistry had relative per-channel L1 differences up to
0.225% on Intel and 0.386% on RTX; RTX fuel sum changed by −0.188%. There were no
stale mappings or non-finite values. Paired contact sheets look consistent, but
these results do not establish exact quality equivalence. The reference fire
also retains broad lobes and a weak upper plume; matching it does not establish
offline or movie quality.

Allocator, seam/domain reads, all-channel clearing, stale generations,
overflow/migration, dense fallback, actual host bind groups and consumers have
native Intel/RTX evidence. Full mobile memory, sustained browser pacing,
film/offline detail parity and composite pressure refinement remain open.

## Same-page development switches

All options use `fire-live/?simulation=volume` and preserve existing interaction
controls, room and preset library:

- `solver=adaptive`: candidate global coarse/local fine flow.
- `bricks=1`: direct chemistry pool and generation-safe consumers.
- `pressureWork=1`: exact fine pressure work lists.
- `lightWork=1`: experimental generic incident-light work queue.
- `receivers=1`: exact precise incident receivers; reference lighting is default.

All five are development options. They are independent so a
component can be measured without attributing another component's savings to it.
Grid spacing, render detail and reaction coefficients do not adapt downward.

## Evidence and replacement gates

CPU checks live in `tools/fire-studio/`: adaptive flow/pressure/runtime,
adaptive lifecycle, brick-pool, pooled-coupling and lighting-work fixtures, together with the existing
Original startup, reset, transition, mask and long-run contracts.

Native evidence is on disk under `work/adaptive-volume-qa/`:

- `pressure-native-integrated-{32,128}.json` and `PRESSURE-RESULTS.md`.
- `pool/native-{integrated,discrete}.json` and `pool/CONTRACT.md`.
- `lighting/receiver-results.json`, `INTEGRATION.md`, `promoted-proof.json`.
- `pool/layout-256/comparison.json` and `RESULTS.md` retain the rejected layout
  trial, including parity checks and alternating held-stage distributions.
- `PRESSURE-TEMPORAL-RESULTS.md` and four `pressure-temporal-native-*.json`
  reports retain exactness and rejected cost evidence.
- `default-reference.json` and `default-host-comparison.json` check that gated
  components add no default operators, resource descriptors or GPU commands.
- Actual host recordings and `native-{integrated,discrete}/report.json` capture
  explicit production bind groups, pass boundaries, dispatches, source movement,
  logical fields and reduced images. GPU time uses the native timestamp period.

The bounded tracked summary is [evidence/adaptive-rc11.json](evidence/adaptive-rc11.json).
It includes hashes of the private full reports for provenance.

Replace the canonical solver only after complete-frame cost, p95, interface
conservation, moving-source chemistry, smoke/flame motion, capacity transitions
and browser/device compatibility pass together. A faster isolated kernel is
insufficient.

## Reproduce the production command comparison

Run from the source repository. Use new recording names and new replay output
names; the tools preserve existing evidence. `FIRE_STUDIO_ROOT` can point the
recorder at a packaged runtime. Native replay needs `wgpu`, `numpy` and `Pillow`
in the Python environment, or the existing local QA vendor directory.

```powershell
node tools/fire-studio/record-volume-runtime.mjs reference-new --receivers --frames 60 --move
node tools/fire-studio/record-volume-runtime.mjs adaptive-new --pool --flow --receivers --frames 60 --move
python tools/fire-studio/replay-volume-runtime.py reference-new --adapter integrated --profile --save-fields
python tools/fire-studio/replay-volume-runtime.py adaptive-new --adapter integrated --profile --save-fields
python tools/fire-studio/compare-volume-runtime.py reference-new adaptive-new --adapter integrated
```

Run one native GPU process at a time. The recorder executes real production
host methods with a fixed CFL telemetry fixture; the replay checks actual
velocity-derived CFL, but does not reproduce asynchronous browser telemetry or
RAF pacing. It adds texture copy usage and timestamp brackets for evidence.
The replayer rejects measured CFL violations, non-finite chemistry and stale
page ownership. The fixed-speed recording became unsafe after about 3.2 seconds
in a later bonfire probe; it must not be used as a sustained-run performance
fixture. Longer acceptance needs native telemetry feedback and dynamic substeps.
The comparator writes metrics and a contact sheet capped at 1600 pixels. Large
fields and frames stay on disk under `work/adaptive-volume-qa/`.
