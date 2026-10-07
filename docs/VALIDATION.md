# Validation of the consolidated tree

The baseline is a fresh, hash-verified canonical source capture at HEAD
`960470167ec18968a3b53ca2026286cc5310f4a5`, with current uncommitted owner changes.
All 1,446 selected files matched the live capture, and all 110 files changed
since the earlier checkpoint have separately verified rollback copies. The
capture was checked on 2026-10-07 at 00:03:51 UTC. Later live edits do not silently
replace this boundary.

## Completed local checks

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
27 controlled parcels, a 12³ grid, 12 steps at 1/120 s and seed 20261007. Its
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

The review branch uses this frozen capture. A later live-source check at 00:19
UTC found 49 changed paths: 45 cache-token updates and four other changes in
`fire-emitters.js`, `fire.js`, `original-shaders.js` and
`original-source-profile.test.mjs`. Those versions are preserved separately and
have not been overlaid. Select and verify the final owner boundary before merge;
do not describe this capture as including subsequent work. Deployment is outside
the consolidation scope.
