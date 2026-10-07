# Validation of the consolidated tree

## Original motion unit correction

The preserved public baseline is merge `5cd55fee659afff3368f844045f3ba1541040b62`.
The tested correction is `9a008c23d97c93a2a517092f01cb3cabd7b6391f`. Source jets and
confinement already enter normalized velocity after division by the world-space
domain extent. Ambient horizontal curl and planar swirl skipped that conversion,
scaling their implied world acceleration with the domain width/height. The
correction applies the same conversion only to Original free fire and fireball.
It leaves the inlet, heat, fuel, damping, cast timing and other Original force
units intact. Every Volume/Sparse runtime file retains its baseline bytes.

Actual Chrome runs completed on 2026-10-07, 03:26:38-03:27:44 UTC, using the
production clock, native grids and unchanged rendering quality on NVIDIA ANGLE.
Before and after use identical camera, lighting, fuel and source inputs. The
following matched paused observations are descriptive, with no invented
acceptance threshold:

| Source | Native simulation age | Before sampled peak world speed | After sampled peak world speed |
| --- | ---: | ---: | ---: |
| Free fire | 0.433333 s | 1.497573 | 0.868453 |
| Free fire | 1.033333 s | 2.673362 | 1.732667 |
| Free fire | 2.200000 s | 4.929841 | 3.565864 |
| Fireball | 0.415000 s | 1.481318 | 1.543691 |
| Fireball | 1.005000 s | 2.830031 | 2.736791 |
| Fireball | 2.215000 s | 2.989606 | 2.861951 |

Free fire is visibly more upright and less spread in the matched late capture.
Fireball's change is smaller; its aimed travel, burning wake and authored breakup
remain. This fixes inconsistent force units, without claiming that the prior
solver diverged or that every artistic motion concern is closed.

Both versions passed pause, reset, persistent free-source drag/release and stop,
four-slot repeated casts, and actual Chrome touch charge/aim/release/cancel.
Candidate sooty-plume, finite-wood campfire and smoke-column runs also completed.
No page or failed HTTP responses occurred. Three full depth slices of both
velocity and chemistry were read at each paused observation: all sampled values
were finite, including after controls. These are sampled-field checks, not a
whole-volume or long-duration stability proof. Courant observations exceed one
in both versions; they are recorded diagnostics, not a stability pass criterion
for the existing semi-Lagrangian transport.

All 61 CPU suite files pass: 428 node:test cases plus the retained custom assertion
suites. Package tests pass 9/9; dependency/asset closure is valid for 180 runtime
files, build `69ed2381c88953e8`. Original-only cache tokens carry the corrected
module through the loader chain. The owned browser and server closed before
video encoding; a separate read-only check reported NVIDIA 0% / 0 MiB.

- [Free fire before at 2.2 s](media/original-free-before.png) and [after](media/original-free-after.png).
- [Fireball before at 1.005 s](media/original-fireball-before.png) and [after](media/original-fireball-after.png).
- [Actual before/after recording](media/original-motion-before-after.mp4): baseline left, correction right, normal wall-time playback. The video is not aligned by simulation age; the paused captures and field observations above are.

Actual Android hardware, sustained performance, conservation and all fuel/power
combinations remain outside this bounded check. No adaptive-flow, renderer,
geometry or resolution changes were made.

The first consolidation was merged in [PR #7](https://github.com/cybrdelic/cybr-elements/pull/7)
at `9519beb11276a2a35dbfad417b87137dba5c8a61`. Its tree exactly matches the
reviewed head `7526d31ab8798e6d26afd43ad0b2679330d79b40`.

The follow-up incorporates the owner's final coherent 49-file batch, captured
on 2026-10-07 at 01:12:34–01:12:40 UTC from the canonical working source on
`codex/fire-studio-release-rc6`, Git HEAD
`960470167ec18968a3b53ca2026286cc5310f4a5`. All 1,446 selected source files have
equal before/after hashes and match the prior verified owner boundary. All 85
runtime hashes in the owner's final `studio-rc-37-repair` register match.
The active task's last completed turn was at 00:20:33 UTC; no later source
movement was observed during selection. Original checkout and rollback copies
remain intact.

Three runtime files deliberately change Original free fire: its scale is 1.1
instead of 1.5, and it shares the plume's broad inlet/feed, cold-vapor ignition,
slower buoyancy and stronger confinement. The matching source-profile test,
44 cache-token updates and one cache/formatting update complete the batch.
Volume/Sparse formulas and all native assets, films, fonts and offline numerical
authoring code retain their merged-master bytes.

## Final owner batch checks

All 60 Node suite files pass: 426 `node:test` cases plus two custom assertion
suites. Three added startup checks record actual production Original uniforms
for free fire, sooty plume and campfire using the existing fake WebGL fixture.
Free fire and plume send scale 1.1; campfire retains its separate finite-wood
contract. Running the same new checks against the merged baseline detects its
old free-fire scale of 1.5, demonstrating the intended behavior difference.
These fixtures do not compile native shaders or establish rendered appearance.

Package tests pass 9/9; asset-restoration tests pass 4/4. Package validation
passes for rc.37, build `0bbc2a90b45f8c7a`, with 180 runtime files
(204,721,288 bytes). Actual local HTTP GET/hash checks pass for all 235
launcher/player/typeface/runtime routes. The imported batch matches the owner's
canonical LF hashes; all remaining source/assets match merged master except
the three documentation files and the extended startup test. A public-payload
scan finds no recognized secret patterns or environment/auth files.

The owner's prior shader, timing and live-control results are supporting
historical evidence; they have not been rerun as current follow-up validation.
Subsequent bounded browser controls, source preservation captures and staged
progress recording completed; the motion correction above records its own
matched before/after validation. These checks make no sustained-performance claim.

## Earlier consolidation preservation checks

On 2026-10-07, all 60 retained Node suite files completed successfully: 423
`node:test` cases plus two custom assertion suites. The Python package tests
passed 9/9, and the asset-restoration tests passed 4/4. Package validation passed
for rc.37, build `2189cfd9524a2d93`, with 180 runtime files (204,721,244 bytes).
Its different build token follows the shortened runtime README; equations,
renderers, controls and native assets retain their captured bytes.

All 14 retained 02 MP4s passed full CPU FFmpeg decoding. Representative existing
film frames and the actual regenerated source review were inspected. Isolated
baseline/staged runs of `sigil_02_source.py sigil-02-v2` produced exactly equal
arrays in all seven fields and identical decoded review pixels. Source silhouette
IoU was 0.9945017763491795, with five components and one hole preserved. This
checks native source preparation; it is not a new fire simulation render.

A small actual APIC/FLIP CPU component run also matches the baseline exactly:
27 controlled parcels, a 12 x 12 x 12 grid, 12 steps at 1/120 s and seed 20261007. Its
positions/velocities state SHA-256 is
`c696dcb0a17238365e4b6bad84352538585b3444dbc9dd4d2599d0a61d9233e2`.
This validates a retained numerical component, not the complete 02 water pipeline.
[Workflow/source matrix](OFFLINE_WORKFLOWS.md) records what was retained and what
has not been rerendered or tested live.

The font specimen's ZIP was already missing from the original checkout. Its
existing v0.1.0 member was restored after verifying the full historical pack
checksum and member checksum; no font was rebuilt or changed. ZIP SHA-256:
`d66196fe201ceb05c9cb6aea33c6943d2b0a824c224eee87b235f3fda3edd3a0`.

Live consolidated browser behavior, motion, GPU pacing and the progress video
remain pending the coordinated slot. No current performance improvement is claimed.

## Preservation checks

- Hash the runtime JavaScript, HTML, CSS, native assets, films and numerical
  authoring source before/after cleanup. Documentation changes are listed separately.
- Run retained CPU lifecycle/control/numerical fixtures and package validation.
  These are useful regressions but do not establish actual rendered behavior.
- Decode the delivered films fully with FFmpeg and inspect representative frames.
- Regenerate approved-artwork source fields in isolated baseline and staged
  preparation directories; compare numerical arrays and review-image pixels.
- Serve the actual consolidated entrypoints and request required assets over HTTP.
  Confirm the historical viewer's missing-cache limitation separately.

## Actual browser/GPU gate

Install the pinned browser-runner dependencies only when needed:

```sh
npm --prefix tools/fire-browser ci
node tools/fire-browser/run.mjs --url=http://127.0.0.1:8776/elements/motion/bending/sigils/02/fire-live/ --matrix --seconds=6 --exercise-controls
```

This launches real graphics work and must wait for the shared GPU/browser slot.
Use one browser/session at a time. No automatic benchmark, Ice rendering or
solver tuning is required for consolidation.

Check Original, Volume and Sparse loading, pause/restart, source changes, finite
floor fuel, lighting/camera, presentation and saved settings. Capture matched
inputs/scene ages/cameras where appearance could change. Record and inspect actual
pixels; unsupported or blocked runs remain unverified.

The progress clip must show the staged canonical version, with source fingerprint,
path, scene/settings and exercised controls recorded alongside it. Label any old
baseline comparison explicitly. Save the resulting video to Library for chat.
No prior recording is described as newly consolidated output.

The follow-up selects the stable final owner batch described above. Any further
owner movement must be captured and reviewed separately. Deployment remains
outside this source-publication scope; the new PR remains subject to parent
review and the pending actual browser checks.
