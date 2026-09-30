# Multiscale volume solver design and acceptance gates

The current integrated architecture, defaults and native evidence are described in [ADAPTIVE_SOLVER.md](ADAPTIVE_SOLVER.md). Volume's default flow, pressure and chemistry remain dense; precise incident-light receivers are opt-in pending a stable complete-frame cost gate. Coarse/fine flow, a direct chemistry pool and fine pressure work lists are integrated as independent development options, with replacement gates still open.

This document preserves the earlier multiscale prototypes and their design constraints. Their measurements do **not** establish Original frame-rate parity, browser performance or mobile support.

## Current release decision

The precise receiver path retains the 64³ light texture, 4³ workgroups, shadow samples and lighting formulas. It covers every positive-soot interpolation footprint, preserves the full camera/shadow halo and clears inactive output on every refresh. Across 34 held-field views, pixels and required illumination matched exactly. Replays of actual solver host commands also matched chemistry and image hashes on Intel UHD and RTX 4060. Measured total lighting cost, including support generation, fell 8.7–14.2% on Intel and 6.7–8.3% on RTX. This is a stage improvement, not a whole-solver or browser FPS claim. Held production lighting also improves at 0.4 and 2 seconds, but complete-frame profiles vary strongly in unchanged kernels. The receiver path stays opt-in until a stable complete-frame gate passes.

Flow-only, pool-only and combined candidates were all slower than the matched dense path in the RTX 60-frame host-command replays. Those recordings cover one simulated second and do not replace the earlier minute-long sustained tests. The exact pressure work-list candidate also regressed complete V-cycle cost despite its isolated smoothing saving. Flow, pool, pressure work lists and the generic light queue therefore remain disabled by default.

The current pool uses fixed 16³ pages and retains dense chemistry for lossless capacity fallback; it adds memory in this integration. Its generation and migration checks do not close the atlas filtering, motion, capacity or mobile memory gates. See the adaptive report for current evidence and unresolved tests.

## Historical measurements

- The scalar brick dispatcher uses 8³ bricks. A settled bonfire occupied 4,973 of 32,768 scalar bricks (15.2%). This is enough sparsity to justify a physical scalar pool.
- The velocity field was nonzero in every sampled 129³ cell after two seconds; 95.87% exceeded 0.01 world units per second. Visible smoke occupancy cannot safely determine where global pressure and air motion are computed.
- Three dense RGBA16F 256³ scalar textures reserve 384 MiB before velocity, pressure, lighting, mesh, and presentation resources. A mobile memory gate requires changing the physical storage, not just indirect dispatch.
- On the browser-selected Intel UHD GPU, the previous complete volume trace spent roughly 19 ms in velocity, 11 ms in pressure, 8 ms in scalar transport, 7 ms in lighting, and 5 ms in rendering. The render-size change addresses only the final stage.
- A six-second oil burst occupied 10,595 scalar bricks. An 8,000-slot atlas would overflow. At an 8³ fine-velocity tile size, one-brick halo and velocity residual threshold 0.05, 99.7% of fine tiles were needed. This invalidates the assumption that fine tiles always save work during a sustained explosion. The proxy is optimistic: it compares the dense result to a decimated field, not a fully coupled coarse/fine solve.

## Solver transition

1. Keep a coarse **global** MAC field and pressure solve. It must receive the integral of every fine-grid face flux crossing a tile boundary. Coarse pressure gives distant air a physically connected response to hot plumes.
2. Allocate fine velocity/pressure tiles around heat, soot, source momentum, moving solids, and the CFL travel halo. Fine velocity is a residual added to prolongated global velocity. At each interface, restrict fine flux to coarse faces, project the global field, and use its boundary pressure as the fine solve's boundary condition. Track mass flux and divergence at interfaces each step.
3. Replace dense scalar textures with a page table and a compact 8³ or 16³ tile pool. Each tile needs a one-cell sampling halo so the existing trilinear volume renderer and advection can read across tile edges. Old, predictor, and corrected fields need distinct generation-safe page tables or slots during a substep. An exhausted pool must grow or fall back to dense storage before an injection; silently dropping a tile is unacceptable.
4. Run light gathering and volume rendering against the same virtual scalar sampler. Validate single-tile, tile-boundary, and high-opacity rays before switching production. Lighting and flames must use identical chemical state and fire-light clusters, including while source dragging and presets change.
5. Size the presentation target to actual physical display pixels, capped at the authored 1280 × 720 ceiling. This is independent of solver resolution and can be retained while the solver transition is built.

## Historical prototype result and revised routing

`work/multiscale-qa/multiscale-transfer.js` provides area-averaged MAC restriction and a matching prolongation. Native Intel and RTX checks found at most 0.000977 face-flux round-trip error (RGBA16F precision). A coarse pressure projection lowered the analytic interior mean absolute divergence from 0.0833 to 0.00298, but the open boundary and the missing fine residual projection fail the conservation gate. This prototype was not promoted. The newer opt-in flow implementation and its routing are documented separately in the adaptive report.

`pyro-gpu/sparse-field.js` and `work/multiscale-qa/sparse-pages.js` implement a virtual 8³-brick sampler, one-voxel halos and overflow detection. The optional sparse renderer shaders compile and have been exercised against **packed dense state**. On the native Intel UHD GPU at 768 × 432, paired lighting/render wall times were 14.33 → 9.33 ms for bonfire, 14.98 → 10.62 ms for CYBR sigil, and 14.45 → 9.64 ms for an early oil burst. Packing the dense state into the atlas separately cost 5.41, 5.47 and 6.09 ms respectively, so this prototype is not a whole-frame speedup. It does not advect and react chemistry directly in the atlas. The newer direct pool is a separate opt-in implementation, not a promotion of this packing trial.

`work/multiscale-qa/sparse-plan.js` sizes three generation-safe chemistry fields from measured occupancy. With 35% headroom and a 60% dense-memory threshold, a two-second bonfire (2,569 active bricks) qualifies for a 160³ atlas per field: 93.75 MiB for all three instead of 384 MiB. The six-second oil burst requires a 250³ atlas per field: 357.6 MiB for all three, so it stays dense. This policy is a planning gate, not connected to the live solver. It must not be used to switch live storage until migration, asynchronous high-water monitoring and overflow recovery preserve every cell.

The earlier direct sparse scalar prototype was tested as a separate old/predictor/corrected generation. The halo writer preserved the same reaction code but took 251,017 GPU ticks against 101,268 for the paired dense Intel step. A compact atlas without halos reduced this to 151,876 against 99,021 on Intel and 1,052,672 against 773,120 on RTX 4060. Its one-step maximum scalar difference was 0.00488 on Intel and 0.00739 on RTX, with mean differences below 0.000004. These are native, same-state scalar-kernel comparisons, not full-simulation quality or frame-rate evidence. That direct sparse path **fails the performance gate** and remains a QA prototype. The six-second burst also fails the original 8,000-slot capacity assumption.

These results require capacity-aware routing rather than one sparse policy. Continued fire may benefit from another sparse representation; prolonged blasts need a dense path or a different solver. Both still need globally connected pressure. These historical direct sparse kernels and the unprojected coarse/fine transfer were rejected. The newer integrated candidates retain independent opt-in gates and dense fallback. Only replace the default after complete browser frames beat the existing dense solver on the target GPU, including p95 frame time, without visual regression.

## Current modules and development switches

The options share the existing page, presets and interaction controls. Add them to `fire-live/?simulation=volume`; no separate application is required.

| Module | Responsibility | Query switch |
| --- | --- | --- |
| `pyro-gpu/adaptive-flow.js` | Global 64³ flow, local 128³ overrides, refinement classification and sticky dense fallback | `solver=adaptive` |
| `pyro-gpu/brick-pool.js` | Fixed 16³ pages, stable slots, generations, direct chemistry and lossless dense migration | `bricks=1` |
| `pyro-gpu/pooled-coupling.js` | Current logical chemistry reads shared by buoyancy, objects, embers, lighting and rendering | Enabled with the pool |
| `pyro-gpu/adaptive-pressure.js` | Exact fine smoothing work lists inside the unchanged global hierarchy | `pressureWork=1` |
| `pyro-gpu/lighting-work.js` | Optional precise receiver support and compact incident-light queue | `receivers=1` selects precise receivers; `lightWork=1` selects the experimental queue instead |
| `pyro-gpu/solver.js`, `renderer.js` | Resource lifetimes, dispatch and consumer integration | Existing Volume entry |

`solver=adaptive`, `bricks=1`, `pressureWork=1`, `lightWork=1` and `receivers=1` are independent and display an experimental-solver label. These options preserve grid spacing, ray detail and reaction coefficients.

Run the source and recording fixtures from the repository root:

```powershell
node tools/fire-studio/adaptive-flow.test.mjs
node tools/fire-studio/adaptive-pressure.test.mjs
node tools/fire-studio/brick-pool.test.mjs
node tools/fire-studio/pooled-coupling.test.mjs
node tools/fire-studio/lighting-work.test.mjs
node tools/fire-studio/adaptive-runtime.test.mjs
node tools/fire-studio/adaptive-lifecycle.test.mjs
node tools/fire-studio/volume-lighting.test.mjs
node tools/fire-studio/volume-optical-mask.test.mjs
node tools/fire-studio/volume-longrun.test.mjs
```

These fixtures test JavaScript contracts and recording order; native shader, field and pixel comparisons remain separate. Current evidence is under `work/adaptive-volume-qa/`, including `lighting/receiver-results.json`, actual-host `dense-runtime/` and `receivers-runtime/`, matched `paired-{dense,flow,pool,combined}-60/`, pressure results and pool results. The [adaptive report](ADAPTIVE_SOLVER.md) tracks the full acceptance status. No desktop native result closes a browser or mobile gate.

## Gates before replacing the production path

| Gate | Required evidence |
| --- | --- |
| Conservation | Fine/coarse interface flux balance, smoke/fuel mass, and divergence against the current solver for still and moving sources. |
| Visual quality | Smoke-only burst, bonfire, CYBR sigil, oil burst, burning object, and multi-source scenes at several angles, including soot, fire illumination, and room shadows. Inspect motion sequences, not only still frames. |
| Capacity | Active-brick high-water mark and overflow behavior for explosions and source dragging, including a constrained mobile adapter. |
| Performance | Completed FPS, p95 frame time, simulation seconds per wall second, GPU stage times, and memory on actual browser GPUs. Run warm and cold starts on integrated desktop and mobile devices. |
| Compatibility | Device-loss recovery, canvas resize, capture/export, restart, all controls/presets, and fallback to Original. |

Rejected experiments are preserved as QA artifacts, not production changes. Masking vorticity to visible bricks altered the long-term flow and was slower on the integrated GPU. Recomputing the MacCormack scalar predictor removed one 128 MiB texture but slowed the RTX run and visibly changed fire. Sharing one midpoint velocity trace among MAC faces also changed motion and did not improve the integrated run. Reducing fine pressure smoothing raised divergence. These are not substitutes for the conservative multiscale transition above.
