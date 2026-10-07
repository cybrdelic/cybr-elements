# Fire Studio browser check

Runs a real, separate Chrome session and serves the local Fire Studio files itself. No Codex browser connection or existing local server is needed. Chrome must already be installed.

```powershell
npm --prefix tools/fire-browser ci
npm --prefix tools/fire-browser run check
```

Run the commands below from `tools/fire-browser/` after installing. Coordinate
an available GPU/browser slot before starting. Test both engines and sparse mode:

```powershell
npm run check -- --matrix --seconds=15
```

Or select a scene:

```powershell
npm run check -- --simulation=volume --preset=bonfire --seconds=30
```

Record matching clips across all three solvers:

```powershell
npm run check -- --solvers=original,volume,sparse --presets=torch,sooty-plume --video --seconds=12
python pack-videos.py PATH_TO_CAPTURE_DIRECTORY --all-solvers
```

The packer creates individual MP4s, a combined video per solver, a gallery and a ZIP. Videos preserve wall-clock playback; a solver that advances slowly remains slow in the capture.

Options use `--name=value`. `--channel=msedge` uses installed Edge. `--url=http://...` tests an existing server. `--cdp=http://127.0.0.1:9222` connects to an already enabled debugging endpoint; it creates and closes only its own pages. `--headless` is for startup checks; it is not representative of the demo's GPU performance.

Reports, 1280×720 page screenshots and a separate canvas screenshot go under `cybr-elements/output/playwright/fire-browser/<timestamp>/`. The runner exits nonzero for startup failures, page errors, stalled simulation metrics, software rendering or a deadline failure. Read `report.json` for the results. It does not claim visual quality passes automatically.

Measurements distinguish browser RAF cadence, GL draw calls, sampled Original GPU submission time, CPU long tasks and the application's own benchmark. Unsupported GPU timers are reported as missing, never zero. Original GPU timers sample one submission every 30 submissions and poll results asynchronously. Instrumentation has overhead, so use the report for diagnosis rather than claiming exact production FPS. WebGPU GPU timing comes from the application's own measurement when available.

Normal browser GPU selection is preserved: no software renderer, security bypass or GPU blocklist override is forced. A valid run can still use an integrated GPU; the reported renderer identifies that choice.

`npm test` checks report calculations and static-server path isolation.

For comparisons at the same simulation age, add `--age=2`. The runner pauses
at that solver age, saves a separate `-age.png`, then resumes measurement.
This prevents a slow solver from being mistaken for a different preset.

`--query=solver=adaptive&lightWork=1` enables an experimental candidate. Quote
that whole argument in PowerShell. `--switches=fireball,torch` checks switching
source families in the existing Scene UI.


To inspect startup rather than a warmed-up plume, use `--from-ignition --video`.
The runner clicks Restart immediately before recording and marks the report
`recordingOrigin: ignition`. This cannot be combined with `--age`.
Without this option, recorded clips begin after warmup and must not be described
as showing the initial state. A restart recording can miss the first submitted
frame; use a small `--age=.15` capture to inspect early gas separately.


Live checks preserve normal frame scheduling and scene age. The app's
180-frame benchmark resets the solver, so it is now requested explicitly with
`--benchmark`; it is not automatically triggered by a non-video run. For live
stall detection, the volume app exposes its actual submitted simulation clock
separately from the throttled metric text.

Runner-owned scenarios use separate browser contexts to release GPU ownership between cases. Each test page is activated, and actual visibility, fuel and color are recorded. Existing CDP contexts are not closed.
