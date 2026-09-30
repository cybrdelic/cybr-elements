# Volume performance gate

The September 30 rc.9 [performance update](VOLUME_SPEED.md) supersedes the latest cost measurements below: guarded donor caching and conservative shadow fetch rejection reduce native complete-scene median cost by 22.5%, with matching tested chemistry bytes and CFL steps. Live-browser parity remains unverified.

The rc.8 regression recovery supersedes the rc.6 wood-source and Original optical/noise changes described below. Its matched rendering evidence, measured native tail costs, corrected QA scope and interaction fixes are recorded in [REGRESSION_RECOVERY.md](REGRESSION_RECOVERY.md). No current live-browser performance gate has passed.

Historical measurements below describe their dated builds. The September 29 release review at the end records the latest retained changes and its narrower verification scope.

Status: **not passed**. The volume runtime does not yet match Original's rendered frame rate or realtime simulation speed on the browser-selected Intel UHD GPU.

## Contract

Compare completed frames, GPU stage timings, and simulated seconds per wall second. Keep the 128 cubed velocity grid, 256 cubed scalar grid, 1/60 simulation step, CFL substeps, pressure iteration count, soot/combustion, embers, lighting and ray steps unchanged. Compare at the same presentation resolution unless explicitly measuring the display-size change. Never count repeated presentation of an old frame as solver throughput.

## September 27 investigation

Both browser engines selected Intel UHD (WebGL reports ANGLE Intel UHD Direct3D11; WebGPU reports Intel gen-12lp). Original campfire measured 29.6–30.3 rendered FPS and approximately realtime simulation. Volume bonfire ranged around 13–19 FPS as GPU load changed, with roughly 0.25–0.32 simulated seconds per wall second. These are short captures, not an all-preset sustained guarantee.

The first volume trace attributed about 19 ms to velocity, 11 ms to pressure, 8 ms to scalar transport, 7 ms to lighting, and 5 ms to rendering. GPU readback and frame scheduling did not account for the main gap.

Retained local changes:

- Velocity advection uses 8x4x4 workgroups. Paired same-state tests initially reduced this individual kernel by about 9%; voxel output was identical. This is not a 9% whole-application speedup.
- The 4 cubed coarse pressure level performs its same 24 Jacobi iterations inside one workgroup. Boundary conditions, precision and iteration count remain unchanged. Floating-point evaluation can produce tiny differences that propagate through turbulent motion; this is not a claim of bit-identical full simulations.
- Original QA reports the actual WebGL renderer so adapter assumptions can be checked.

Rejected variants: component unrolling, source specialization, larger scalar workgroups, integer vorticity reads, and paired fine-pressure passes. They failed the performance gate or did not show a reliable gain.

## Evidence and reproduction

`work/volume-performance-qa/report.json` contains full-scene summaries and limitations. `kernel-report.json` records paired per-kernel GPU times and voxel comparison results. PNG captures and complete frame traces are beside them. The saved baseline WGSL is embedded in the test-only probe, outside the production package.

From the repository root, run `python work/volume-performance-qa/server.py`, then open `http://127.0.0.1:8785/probe.html`. The probe runs the real browser WebGPU device, alternates baseline and candidate kernels on fixed inputs, checks output differences on the GPU, and writes results through the local capture endpoint. It destroys its GPU device when finished.

Full application traces use `?simulation=volume&firePreset=bonfire&room=1&fuel=wood&smoke=0&fireLight=24&lighting=studio&angle=16&zoom=1.25&qa=NAME&stop=3`. Original uses `?simulation=legacy&preset=campfire&room=1&fuel=wood&qa=NAME&capture=3`.

## Remaining work

The dominant remaining work is dense 128 cubed velocity transport and pressure projection. The conservative multiscale transition and acceptance gates are detailed in `MULTISCALE_SOLVER.md`. Reducing resolution, stepping the simulation more slowly, or substituting native NVIDIA results for browser measurements does not pass this gate. Dedicated-GPU browser routing is also unverified; the application already requests the high-performance adapter.

## September 27 display and solver experiments

The volume canvas now targets physical display pixels up to 1280 × 720, preserving 16:9 and the unchanged simulation grid. The 711 CSS-pixel view used in the local app selects 768 × 432 at DPR 1; a 390 CSS-pixel view at DPR 2 selects 896 × 504. QA links retain 1280 × 720 for comparable captures. An integrated-GPU native offscreen run changed the bonfire's median completed wall time from 85.99 to 71.72 ms at those two sizes; the oil burst changed from 77.05 to 68.65 ms. These are native Vulkan measurements, not browser FPS claims. At the common 960 × 540 review size, frame mean absolute RGB differences were 0.50/255 for bonfire and 0.39/255 for oil burst; both pairs were visually inspected. The physical simulation and lighting code were unchanged.

Exact shader arithmetic cleanups produced byte-identical review frames but no repeatable speedup, so they were reverted. Plume-masked vorticity, a fused scalar predictor, a shared MAC trace, and fewer fine pressure smooths each failed a quality or performance gate and were reverted. The browser's WebGPU adapter subsequently became unavailable in this in-app session, so the new canvas resize path still needs a live browser run after the session recovers. The app reports an actionable startup error instead of relying on `navigator.gpu` presence alone.

## September 28 room lighting profile

An integrated Intel UHD native WebGPU kernel profile identified velocity correction as the largest single simulation kernel, followed by the room lighting pass. The latter traces shadowed light over five wall/floor surfaces. Its direct and bounce targets now use 64 × 64 texels per surface instead of 128 × 128. The render path samples the new atlas dimensions, while the 128³ velocity grid, 256³ scalar grid, pressure solve, flame lighting, and ray steps remain unchanged. The room atlas writes one quarter as many texels.

Same-state, alternating before/after native Vulkan captures at 768 × 432 showed these median lighting GPU timestamp reductions: bonfire 234,107 → 149,449 ticks (36%), oil burst 252,279 → 165,993 (34%), burning house 172,010 → 105,378 (39%). The paired lighting plus render wall times were 14.57 → 10.21 ms, 15.55 → 11.06 ms, and 11.96 → 8.59 ms respectively. These wall times cover **only the lighting and render passes**, not a complete application frame. GPU timestamp ticks are useful for paired ratios on this adapter, not portable milliseconds.

The direct, oblique, and smoke inspection images differ by 0.20–0.59 mean RGB levels out of 255 across those three sources. Bonfire and house pairs were visually reviewed. A 32 × 32 trial saved more time but visibly broadened the house's room shadows, so it was rejected. Exact velocity workgroup variants yielded only 1–1.5% single-kernel gains and were reverted. The tree shader family compiled and rendered with the 64 × 64 target on Intel UHD. The paired captures, timing records, and native kernel profile are in `work/burning-sources-qa/room64-*-integrated-768-compare-room` and `work/burning-sources-qa/room64-bonfire-integrated-768-kernel-profile`.

The same 128 → 64 bonfire pair on native RTX 4060 at 1280 × 720 reduced lighting timestamps 1,785,856 → 1,243,136 ticks (30%) and paired lighting plus render wall time 2.90 → 2.38 ms. This is a second adapter check, not evidence of browser GPU routing or full-frame FPS. Its captures and timings are in `work/burning-sources-qa/room64-bonfire-compare-room`.

The multiscale/sparse follow-up is recorded in `MULTISCALE_SOLVER.md`. A six-second oil burst outgrew the trial 8,000-brick atlas and required nearly all fine velocity tiles. Direct compact sparse scalar transport ran 1.53× slower than dense on Intel UHD and 1.36× slower on RTX 4060 in paired same-state kernel tests. Those prototypes remain outside the live solver and outside the release package; no full-frame speedup is claimed. The in-app browser currently reports no available WebGPU adapter, so browser FPS and motion quality could not be revalidated in this session.

## Presentation stall fix

The volume runtime previously awaited `mapAsync()` for both simulation statistics and timestamp queries after **every** submitted frame. A slow browser mapping delayed the next `requestAnimationFrame` even when the GPU had already accepted the presentation work. The runtime now uses three telemetry readback slots, consumes diagnostics asynchronously, and limits unfinished GPU submissions to two. Statistics slots become reusable as soon as their small readback completes, even if the corresponding timestamp map is still pending. A delayed or out-of-order readback cannot overwrite the CFL speed after a reset; stale diagnostics trigger a conservative speed bound. The benchmark drains the GPU queue before reporting throughput. Unit tests exercise delayed mappings and verify that frame submission continues until the two-frame GPU limit, then resumes when a fence completes.

This removes an avoidable CPU/GPU synchronization point. It does not shorten expensive fluid, pressure, or lighting kernels, so a genuinely GPU-bound frame can still exceed the display budget. The in-app browser WebGPU adapter was unavailable during this fix; live visual pacing and browser FPS remain unverified.

The app now waits for the first GPU presentation before showing Ready and reports a submitted-frame timeout in the scene and GPU diagnostics. In this in-app-browser session, one attempt accepted a device but failed to finish a frame within eight seconds; a subsequent reload reported no available adapter. That behavior is a browser GPU-session failure in addition to the code's former readback stall. It is not evidence that the new scheduling reaches a target FPS on a healthy browser.

On reload, the in-app browser reports “WebGPU but has no available adapter in this session,” so a complete browser FPS and simulation-to-wall comparison is still required. This optimization does not establish parity with Original or a 60 FPS pass on mobile hardware.

## September 28 follow-up: intermittent frame pacing

The first asynchronous-readback change still let the interactive animation callback await a GPU completion fence whenever two frames were queued. That can miss display ticks in a repeating pattern even while controls should remain responsive. The interactive loop now checks queue capacity and returns promptly on a full queue; benchmark and reset paths still wait for actual completion. The status reports how many display ticks were queue-limited per 30 submitted frames so GPU saturation is visible rather than disguised as a JavaScript freeze.

The earlier stale-statistics rule also jumped an ordinary source to a 12-unit/s CFL bound after four late readbacks. On the saved Intel UHD bonfire trace, roughly 6-unit/s flow uses two substeps while the 12-unit fallback uses three. Those saved frames had median wall times of 67.3 ms at two steps versus 95.3 ms at three steps (the groups are from different simulation times, so this is diagnostic evidence rather than a paired speedup). The bound now grows with telemetry age for the first eight late frames; bursts retain the 12-unit startup bound, and a longer readback failure still uses the conservative fallback. No fluid, lighting, resolution, or render-pass settings changed. Live browser pacing remains unverified because browser automation refused access to the local tab in this session.

Replaying one-, two-, four-, and eight-frame delayed statistics against the saved 120-frame Intel bonfire, 240-frame RTX bonfire, and 360-frame RTX oil-burst speed traces found no frame where the revised bound chose fewer substeps than the recorded velocity required. This is a trace-based safety check, not a proof for every source or an in-browser FPS measurement.

## Bonfire height and Original counterparts

The continuous 3D bonfire was sending hot fuel to the top of the room by five seconds. A paired native offscreen study used the same 128³ velocity grid, 256³ scalar grid, 768 × 432 output, room lighting, and five seconds of continuous fuel. The retained preset reduces its source jet and buoyant lift while retaining a 1.15 fuel feed. In the five-second front view, the first-percentile warm-flame pixel moved from y=26 to y=176 on RTX and y=52 to y=147 on Intel UHD. Flames remain visible below the separate smoke plume in front and angled views. Median completed native frame times changed from 14.33 to 7.25 ms on RTX and 68.55 to 36.49 ms on Intel UHD; p95 changed from 20.92 to 15.92 ms and 90.47 to 78.45 ms respectively. These are native offscreen measurements, not browser FPS. Baseline and retained captures, traces, and two rejected intermediate tunings are in `work/burning-sources-qa/height-*`.

At that checkpoint, Original had distinct bonfire and hearth wood beds while advanced objects and jets remained exclusive to Volume. The next section records the subsequent source-port work; these earlier measurements do not cover it.

## Original source catalog parity

Original now exposes the 43 shared 3D source IDs in its own runtime, in addition to its four Original-only sources. Shape, sigil, jet, smoke, and burst IDs drive distinct source geometry and fuel settings on the Original grid. Object IDs load the same 64³ distance-field assets, use their combustible material channels for surface feed, and render the object surface by distance-field ray marching. Heated gas increases their local release, and an overall finite decay limits fuel. This is a simpler surface model than Volume's persistent per-voxel fuel, moisture, char, crack, and damage state; the two solvers should not be presented as visually equivalent for object fires. A hidden OpenGL ES 3 context compiled the assembled Original simulation and rendering GLSL and their emitter/prop snippets. Catalog, routing, package, and JavaScript syntax checks passed. Browser appearance and frame pacing remain unverified because the local browser session was blocked for automation.

## September 29 release review

Original's empty-air simulation cells now skip chemistry and force work while the 640 × 360 × 32 grid remains intact. A native Intel UHD bonfire pair using the earlier surrogate noise basis measured 12.28 → 10.38 ms (15.5% lower median), with rendering essentially unchanged at 5.53 → 5.68 ms. A subsequent exact production-noise pair measured 26.39 → 24.22 ms (8.2% lower median) with substantial wall-time variance. The matching offscreen captures showed no obvious detail regression. These results measure native passes, not application or browser FPS, and do not establish a guaranteed speedup. The final sampler also enables mip filtering for the fine forcing lookup; generated mip levels were previously unused by its filter state. A candidate Volume soot mask was rejected after negligible gains; the dense production solver remains in use.

The retained Volume changes correct telemetry mapping order, fullscreen behavior and tree screen-target resizing. Timestamp resolution now covers only written queries, including zero-step paused views, rather than resolving an 80-slot range containing unused queries. The aligned staging/readback layout passed native Vulkan checks on RTX 4060 at 0, 1, 3 and 12 substeps. A query-only native probe had exposed device loss when resolving unwritten slots; this repair removes that path but does not certify browser stall recovery.

Volume wood beds now use six independently fed fuel pockets, bounded source evaluation and conservative source/brick intersections. The retained four-second RTX 4060 trial kept 128³ velocity, 256³ scalars and 768 × 432 output; simulation median changed from 5.133 to 4.545 ms, scalar transport from 0.958 to 0.499 ms, and lighting from 2.192 to 1.857 ms. Paired motion and ±35°/55° views show a lower plume with more distinct inner fronts. Early caps remain rounded. A slower first trial was rejected; these native costs are not browser FPS or a mobile guarantee.

Volume's benchmark measures GPU-completed frames; Original's new 180-frame measurement reports browser render-submission intervals and simulation speed without claiming GPU execution timing. Both stop when the scene is hidden. Original shared color, inspection-smoke and fire-illumination controls are connected to its rendering path; unlit black mode uses smoke inspection fill, and embers remain Volume-only. Source experiments now start hidden and library filtering respects the selected simulation. These control and scheduling changes do not establish performance parity or offline image parity.

Release candidate packaging has a separate content fingerprint, normalizes module/asset cache keys and validates its shipped dependency graph and binary assets. It carries open gates for current live-browser motion/performance, mobile hardware and matched Original/offline/Volume visual review. Browser automation cannot inspect the local page in this session, so native captures and state/lifecycle tests are the available evidence. The 3D volume engine remains experimental; sustained 60 FPS and mobile support are unverified.
