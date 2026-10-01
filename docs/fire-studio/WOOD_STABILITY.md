# Wood combustion stability — rc.19

**Status: accepted for the scoped Wood bonfire crash fix; package and public delivery verified.** Seven current native cases pass host, binding, finite-state, and measured CFL checks: 1,860 simulation frames plus three held views across NVIDIA RTX 4060 Laptop and Intel UHD Vulkan adapters. Sampled normal and Sparse log flames stay rooted after the starter before a limited patch burns down. The accelerated stress quenches and the tree control stays cold; neither proves persistent fire or tree propagation. Earlier candidates remain rejected. [Proof manifest](RC19_WOOD_STABILITY_PROOF.json)

## Reproduced failure

The Wood bonfire (`burning-logs`) failed in the actual production adaptive timestep loop on an NVIDIA RTX 4060 Laptop GPU, Vulkan driver 610.62. At recorded frame index 85, time 1.4333 s, the velocity reduction reached 9.2052 m/s and measured CFL 3.273, exceeding the 1.5 limit. Frame index 86 reached 871.8008 m/s; the next frame was rejected by the production 12-substep guard. These indices are zero based. [Native report](../../work/adaptive-volume-qa/feedback-logs-180-lag0-discrete/native-feedback/report.json)

The first unsafe capture identifies thermal positive feedback: normalized gas heat was 501 and maximum wood temperature was 186,089 K. There were no broken bonds or detached wood nodes. Stored velocity stages were 3.0573 m/s after prediction, 11.3405 before pressure projection, and 9.2032 after projection. The force-stage increase preceded projection. [First unsafe state](../../work/adaptive-volume-qa/feedback-logs-180-lag0-discrete/native-feedback/unsafe-state-85.json)

Wood vapor supplied sensible enthalpy, but the gas shader added it directly to intensive temperature. Added vapor mass carried no corresponding heat capacity. Hot gas reheated the wood, which released hotter vapor, amplifying the error. The fixed three-substep fixture masked this failure; it did not verify the production feedback loop.

## Sensible energy correction and finite ignition

The shared dense and pooled gas path now mixes the incoming vapor before storing its fuel:

```text
capacity = 1 + oldFuel
newHeat = (oldHeat × capacity + incomingEnthalpy)
          / (capacity + incomingFuel)
```

The equation conserves sensible energy under the existing mixture-capacity model. It preserves the source mass, oxygen model, material clock, forces, and timestep selection. The same normalization is already used by floor fuel. Seven mixing CPU gates cover units, convex temperature bounds, dense fuel, packet partition, a closed wood/gas feedback loop at 1/60 versus 1/180 s with 12× wood time, and matching dense/pooled shader integration. Four additional gates cover the finite starter. [Mixing and starter tests](../../tools/fire-studio/wood-gas-mixing.test.mjs)

The mixed-only 600-frame native run completed without an unsafe CFL capture: maximum speed 3.3049 m/s, maximum measured CFL 1.1751. **This candidate fails the flame gate.** The separate 180-frame field capture peaks at normalized gas heat 0.2499, below Volume ignition onset 0.35. Properly mixed vapor cannot replace an external igniter. [600-frame report](../../work/adaptive-volume-qa/rc19-logs-feedback-lag0-600/native-feedback/report.json), [field report](../../work/adaptive-volume-qa/rc19-mixed-only-logs-180-fields/native-feedback/report.json)

A compact external starter now supplies authored ignition heat without adding fuel or oxygen. It expires after 1.2 real seconds for logs, or 2.5 seconds for trees; 12× wood time does not multiply its heat. V2 increased its rated power to 120 kW, or 160 kW total across three all-ignition sites. Free-space energy budgets are 144/192/300 kJ; solid and domain clipping reduce actual delivery. V3 aligned the solid starter with the gas starter at local `[-.45, -.45, .15]`, replacing the below-floor location. The starter is finite; subsequent combustion remains the transported gas reaction.

| Candidate | Native numerical result | Decision |
| --- | --- | --- |
| V1, 40 kW gas starter | 180 frames; CFL 0.3531 | Rejected: weak lasting flame |
| V2, increased finite power | 180 frames; CFL 1.1323 | Rejected: weak lasting flame |
| V3, corrected solid placement | 180 frames; CFL 0.6341 | Rejected: weak flame and fuel accumulation |
| V4, conservative gas-volume source | 180 frames; CFL 1.9910 | Rejected: measured CFL exceeds 1.5 |
| V5b, hot-product sustain and finite timestep margin | Initial 180 pass; 600-frame CFL 1.5163 | Rejected: zero-lag predictor omitted upcoming interval |
| V5c, upcoming-interval prediction | Seven cases; 1,860 simulation frames and three held views pass | Accepted for the reproduced crash and sampled finite log ignition; limits below |

## Gas-volume continuity

V3 reached 91.0625 kg/m³ fuel concentration. Structured wood had bypassed the analytic emitter, leaving released vapor without a mass-source divergence term. V4 requests `divergence = deliveredMass / (referenceDensity × flowCellVolume × dt)`. Each 128³ anchor is consumed once; the 64³ path sums its eight anchors. Blocked retained mass contributes zero. The fine scalar normalization is excluded from this pressure source, avoiding duplicate volume. Existing scalar dilution uses that divergence for both soot and fuel. [Volume-source tests](../../tools/fire-studio/wood-volume-source.test.mjs)

Seven CPU gates verify requested source-volume integrals, blocked/open transitions, CFL partitions, support, and shared dense/adaptive kernels. This conserves the requested source integral; the existing transport and finite pressure solve remain numerical approximations. V4's first unsafe frame is index 17, time 0.3 s, CFL 1.6212. Its host loop completes, but numerical acceptance fails independently. [V4 report](../../work/adaptive-volume-qa/rc19-continuity-v4-logs-lag0-180/native-feedback/report.json)

## Ignition and sustained reaction

V5b preserves fresh-gas ignition onset at normalized heat 0.35 (720 K). Wood scenes use advected soot or oxygen deficit as a reduced hot-product memory, allowing already burning warm gas to react down to 0.15 (480 K). Cold products, missing fuel, or depleted oxygen cannot sustain reaction. This is an approximate scene-wide wood model, not radical/species chemistry or a per-cell proof of fuel origin. The ordinary nonwood reaction equation is unchanged.

Scalar combustion, thermal expansion, ray emission/skip, and both lighting gathers select the same scene reaction helper. The existing radiance weighting remains unchanged and suppresses emission at normalized heat ≤0.2; this is not a display-only brightness increase. A newly live object uniform was missing from coarse gather's bind group; V5b supplies exactly binding 13. The initial V5 startup failed before any frame and supplies no simulation evidence.

Structured wood also receives a finite predicted speed floor of 12 m/s while active: 1.7 s for logs, 3 s for trees, including 0.5 s after the starter window. It selects smaller timesteps without clipping velocity, resetting measured telemetry, or bypassing the 12-substep guard. Stop disables it; Relight/reset starts a fresh bounded window. Eight CPU gates cover reaction bounds, partitions, all helper routes, endpoints, and the actual production frame's gather binding/startup timesteps. [Combustion tests](../../tools/fire-studio/wood-combustion.test.mjs)

The initial V5b native run completed 180 frames with maximum speed 9.2664 m/s, maximum measured CFL 1.4456, and no unsafe state. Frame 179, after the 1.2 s starter, retains flame around the logs with room illumination and smoke. Earlier frame 59 has broad bright rolling lobes and a floor ring; flame softness remains a visual limitation. Its subsequent 600-frame run fails at index 295: speed grows from 4.2073 to 4.2645 m/s, producing CFL 1.5163 while the host still completes. Zero-lag telemetry described the completed interval, leaving no prediction for the upcoming one. [Initial V5b report](../../work/adaptive-volume-qa/rc19-sustain-v5b-logs-lag0-180/native-feedback/report.json), [rejected long run](../../work/adaptive-volume-qa/rc19-sustain-v5b-logs-lag0-600/native-feedback/report.json)

V5c reserves one upcoming interval plus mapped-frame lag in the existing speed predictor. This changes timestep selection for nonwood scenes too; their source/reaction/render equations remain unchanged. The predictor is a safety margin, not a mathematical bound on every possible future force. The guards remain active.

The V5c zero-lag run completes 600 frames, maximum measured CFL 1.3935, maximum speed 9.2664 m/s, without an unsafe state. Frames 239 and 359 retain flame around the central logs; frame 599 has smoke and small tongues over a mostly intact pile. End state: 654.87 K maximum wood temperature, 271.829 kg virgin wood from 283.085 kg initial stock, 3.728 kg char, and 0.05997 kg/s release; no fractures. This is finite ignition of a limited patch, not verified full-pile spread, structural breakup, or cinematic bonfire parity. [V5c 600-frame report](../../work/adaptive-volume-qa/rc19-sustain-v5c-logs-lag0-600/native-feedback/report.json)

The 360-frame stress run also passes with eight completed frames of readback delay and 24× wood time: maximum speed 15.4933 m/s, maximum CFL 1.3210, using two to five substeps. The finite patch quenches; final release is zero and maximum wood temperature 322.75 K. This verifies delayed numerical decisions and extinction, rather than persistent fire in the stress case. [Delayed stress report](../../work/adaptive-volume-qa/rc19-sustain-v5c-logs-lag8-wood24-360/native-feedback/report.json)

## Final controls

| Current native case | Simulation frames | Maximum measured CFL | Scope |
| --- | ---: | ---: | --- |
| RTX Volume, zero map lag | 600 | 1.3935 | Rooted finite log patch, followed by smolder |
| RTX Volume, lag 8, wood time 24× | 360 | 1.3210 | Delayed numerical decisions and extinction |
| RTX Sparse, lag 4 | 180 + 3 held views | 1.0963 | Pooled startup, then sticky dense fallback |
| Intel UHD Volume, lag 4 | 180 | 1.1628 | Second GPU, finite state and sampled log flame |
| RTX ordinary Bonfire | 180 | 1.3289 | Separate structured-wood preset |
| RTX cybr tree | 180 | 0.2439 | Cold startup, bindings and finite state only |
| RTX Torch | 180 | 1.1077 | Nonwood reaction/render control |

Sparse frame 59 uses the actual brick pool. Its first dense status is frame 70, time 1.1833 s; frame 179 and the held angle views use the sticky dense fallback. The sampled pooled frame has soft rolling source lobes and a floor ring; the held −50° final view retains rooted tongues with smoke after ignition. This is not proof of a wholly sparse run. [Sparse report](../../work/adaptive-volume-qa/rc19-sustain-v5c-logs-sparse-lag4-180/native-feedback/report.json)

The Intel run ends with finite gas and wood, 673.20 K maximum wood temperature and 0.86693 kg/s release. Ordinary Bonfire also uses `object: logs`, so it is a structured-wood control. Torch has no wood and provides the ordinary nonwood control; its source, reaction, and render equations are unchanged by the correction. [Intel report](../../work/adaptive-volume-qa/rc19-sustain-v5c-logs-intel-lag4-180/native-feedback/report.json), [Bonfire report](../../work/adaptive-volume-qa/rc19-sustain-v5c-normal-bonfire-180/native-feedback/report.json), [Torch report](../../work/adaptive-volume-qa/rc19-sustain-v5c-torch-control-180/native-feedback/report.json)

The tree remains cold: maximum wood temperature 371.99 K, normalized gas heat 0.3240, and no final soot or gas fuel. Its 180-frame pass verifies the tree pipeline and finite state, not flame spread, crown ignition, or structural damage. [Tree report](../../work/adaptive-volume-qa/rc19-sustain-v5c-tree-180/native-feedback/report.json)

## Verification scope

Ten native-feedback CPU gates use the production collectors and CFL decisions, including delayed 16/32-byte mapped readbacks, occupied slots, monotonic sample frames, stale epochs, and both velocity guards. Fourteen telemetry gates include the observed upcoming-interval regression. Four decoder gates check diagnostic units. Two transport gates preserve final numerical-rejection acknowledgements and reject missing acknowledgements. These and the 26 mixing/starter/source/combustion gates total 56 independently checked CPU gates. Final strict Dawn null validation passed 211 unique modules / 515 source variants with zero errors or warnings, including the exact recorded wood mechanics shader. Every module hash in all seven native recordings matches that report; each recorded host hash matches the frozen solver and each aggregate shader fingerprint recomputes exactly. Compilation alone does not establish runtime correctness. [Feedback QA](../../tools/fire-studio/native-feedback-qa.md), [final strict report](../../work/dawn-qa/rc19-final-recorded-wood/report.json)

Native replay completes each GPU batch before the next host frame. Readback delays of 0, 4, and 8 completed frames test adaptive decisions without replacing measured speed. Numerical acceptance additionally requires no `firstUnsafeFrame`; host guard success alone is insufficient. The scoped crash/binding correction is accepted.

## Delivery

The rc.19 directory and ZIP both verify against build `46ff16af6f281449`: 155 runtime files, 204,570,403 runtime bytes, and a 90,858,233-byte archive. An independent directory check matches all 155 file hashes. The source correction is pushed as `9c33716d1fe29aec17c471be42daf03a3a3918f5` on `codex/fire-studio-release-rc6`. [Directory verification](../../work/powers-qa/rc19-final-directory-verify.log), [archive verification](../../work/powers-qa/rc19-final-zip-verify.log)

Site commit `b433b0bcaf33b02f85dd31434842b47a963ac6bf` is pushed to `master`; all 156 indexed runtime/manifest blobs match the package. Pages built that commit at 2026-10-01 12:39:16 UTC. Public verification returned HTTP 200 and exact package SHA-256 matches for all 155 runtime files and the manifest: 156/156, 204,596,819 served bytes. The published build is available at [Fire Studio](https://cybrdelic.github.io/firesim/). This verifies delivered bytes, not live browser behavior. [Site index proof](../../work/powers-qa/rc19-final-site-index-proof.json), [Pages build](../../work/powers-qa/rc19-pages-build.json), [public verification](../../work/powers-qa/public-rc19.json)

Native submission timings are GPU evidence for the recorded workload. They do not establish browser FPS, RAF pacing, concurrent UI behavior, or physical mobile performance. Those gates remain unverified.
