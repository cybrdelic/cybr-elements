# Production adaptive feedback QA

The fixed recorder remains the default. `--native-feedback` instead starts a
persistent offscreen native WebGPU worker and lets the actual `PyroSolver.frame`
choose its substeps. The existing production `collectTelemetry` and
`collectPoolTelemetry` methods receive bytes mapped from their production
readback buffers. No speed or sample-frame values are substituted.

```powershell
node tools/fire-studio/record-volume-runtime.mjs feedback-logs-lag0 --preset burning-logs --simulation volume --frames 180 --capture-every 30 --camera-angles none --native-feedback --readback-lag 0
```

Repeat with unique names and `--readback-lag 4` / `--readback-lag 8` to hold
collector completion for that many completed frames. Pending slots remain
occupied, so the solver's existing three-slot availability controls sampling.
This is a completed-frame delay rather than a fake replacement max-speed curve.

`--native-profile` adds native submission timestamps. `--adapter integrated`
is the default; `--adapter discrete` requests the high-performance adapter.
`--python` selects the Python executable. The worker uses the existing local
wgpu / NumPy / Pillow dependencies. `replay-volume-runtime.py --stream` is its
JSON-lines protocol entry point; standalone fixed replay remains supported.
`--native-field-summaries` forwards `--field-summaries` to the worker and checks
reduced gas/wood fields at regular snapshots, including finite values and hottest
occupied donor coordinates. It saves no NPY/NPZ arrays; full `--save-fields`
remains a separate explicit replayer option.

Each recording stores:

- `commands.json`: actual resources, uploaded bytes, commands, host/shader hashes.
- `feedback-batch-N.json`: incremental exact resource/command batches.
- `host-feedback.json`: production substep decisions, telemetry age, pending
  slots, native delivery schedule, and the exact production guard on failure.
- `native-feedback/report.json`: hardware, actual reduced velocity/CFL,
  optional GPU timings, small rendered images and mapped-readback hashes.
- `native-feedback/unsafe-state-N.json`: the first measured CFL violation's
  actual gas, wood, flux and velocity-slot reductions. Fixed replay stops before
  advancing this state. Feedback replay records it and follows the exact
  production safety guards.
- `native-feedback/readback-N.bin`: actual 16/32-byte GPU readback bytes.
- `native-stream.log`: bounded control output is kept separate from native logs.

No full chemistry or wood field dumps are saved in stream mode by default.
On the first unsafe frame, the worker reads the actual fields for small
summaries: finite values, hottest occupied donor coordinates, conservative
flux mass/energy/normalization and ledger totals, gas peaks, and velocity-slot
peaks. These arrays are reduced in memory and discarded rather than saved.
Production invalid-velocity and 12-substep guards decide host failure. Native
measured CFL remains evidence; the fixed fixture's additional CFL acceptance
check does not replace a production guard in feedback mode.
The report separates `productionHostPass` from `numericalPass`: the latter
requires no measured CFL violation. A numerical rejection fails the CLI result
while preserving the actual host guard/error and its full requested timeline.

The native worker completes each submitted batch before the next host frame;
this checks adaptive numerical decisions and delayed telemetry, not browser RAF
pacing, concurrent UI behavior, browser GPU timing, or mobile performance.
Run only one physical native GPU process at a time.

CPU protocol/production-collector checks (no GPU):

```powershell
node tools/fire-studio/native-feedback.test.mjs
node tools/fire-studio/native-stream-control.test.mjs
python -m py_compile tools/fire-studio/replay-volume-runtime.py
python tools/fire-studio/native_wood_fault_test.py
```
