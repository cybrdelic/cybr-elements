# Fire Studio release procedure

The deployable unit is the output of `tools/fire-studio/package.py`. Historical renderer trials are archived under `work/fire-studio-research-archive/`, outside the served source tree. Copy the validated package so authoring assets and development notes stay out of the release.

## Build and validate

Run the Node state/lifecycle/telemetry suites, startup/transition/reset/lighting/optical/sustained-scheduling regressions and query/resize gates, the Python package suite and `package.py --check` listed in the runtime README. Package validation runs **39 runtime runners** automatically against source, the completed build and directory verification, including wood vapor mixing, gas-volume sources, combustion memory and telemetry regressions. `FIRE_STUDIO_ROOT` can also select a directory for manual checks. They exercise JavaScript initialization, shared shell transitions, actual reset ordering, normal/tree lighting bindings, optical mask ping-pong, finite fuel lifecycle and 10,000 display ticks with DOM/GPU fixtures; live browser/device acceptance remains separate. After all runtime changes are complete, create a fresh package with `python tools/fire-studio/package.py --out releases/fire-studio-RELEASE-NAME`. The name must be new; the builder does not overwrite previous artifacts.

The package records the exact shipped bytes and a content-derived build fingerprint. JavaScript imports, classic shader scripts, stylesheets and local runtime asset URLs use that fingerprint as their cache key. The artifact preserves the single-page entry and the old `pyro-gpu/` redirect. Tree binaries and source previews are validated before packaging; imported tree geometry remains a lazy source load.

Check the resulting `release.json`, ZIP and runtime directory together with `python tools/fire-studio/package.py --verify PATH-TO-DIRECTORY-OR-ZIP`. This confirms file hashes, transformed JavaScript syntax and that no unrecorded files are present. Never modify a packaged script after generating the manifest. Rebuild if any runtime or asset changes. `release.json` describes packaging verification and the open visual/performance gates; a successful build does not close those gates.

## rc.12 fuel and inspection gates

Usage and evidence scope are in [FUEL_AND_INSPECTION.md](FUEL_AND_INSPECTION.md). The release adds **Fully lit · neutral**, **Show sigil**, and finite floor fuel with **Drop fuel**, **Ignite fuel** and **Clear fuel** in both engines.

| Feature | Recorded gate |
| --- | --- |
| Fully lit | Catalog, existing select/library, persistence, clamps and neutral bindings pass; native captures were inspected for room and source readability. |
| Show sigil | Native contour tests execute 756 rays per GPU with zero hit disagreements on Intel UHD and RTX 4060; held-state angles were visually inspected. The artwork is a visible surface, not a fluid obstacle. |
| Cold and ignited fuel | Cold inventory stays unlit. Original's production gas reacts after a finite pulse with its normal source disabled. Volume's final Intel/RTX production-command replay also produces soot from placed fuel with the source disabled. |
| Smoke clearance | Native Volume lifetime is independent of CFL subdivisions; Original clears negligible stored soot. Source replenishment and Pause remain distinct from dissipation. |
| Inventory and clearing | Surface stock/char accounting, independent clearing, restart and fixed resource lifetimes pass. Clearing fuel leaves existing gas and smoke evolving. |

The compact native proof is recorded in `RC12_FUEL_PROOF.json`. These gates cover native shader/state paths. Browser automation was blocked by automatic approval review in this session; actual browser interaction, sustained frame pacing and mobile acceptance remain separate.

## rc.13 Sparse mode gates

[SPARSE_MODE.md](SPARSE_MODE.md) describes the third same-page selection, **Sparse volume · experimental**. It enables pooled chemistry while retaining global Volume flow and pressure, full voxel spacing, reference lighting and the shared source/control library. Fully lit, Show sigil and finite floor fuel remain available. URLs and saved looks retain the selected mode.

The pool adds **96 MiB** to **384 MiB** of retained dense chemistry backing. Capacity or safety fallback continues in dense storage and remains there until Restart. This is an experimental storage route; it is not established as faster, lossless during atlas transport or supported on mobile.

| Gate | rc.13 status |
| --- | --- |
| Selection and shared state | 150 CPU tests pass, including all three choices, counterpart sources, presentation continuity, library routing, canonical URLs, saved/imported looks, recovery and valid tools. The three new mode runners are included in package validation. |
| Chemistry and imagery | Four native 60-frame replays pass shader, CFL and finite-field checks; pooled snapshots have no stale mappings. Lit sigil/floor fuel captures and alternate views were inspected. Atlas-filtering quality equivalence and sustained motion remain open. |
| Complete-frame cost | Matched native frames 6–29 have mixed costs: sparse is slower on Intel and faster in this single RTX trial. No sustained browser speedup is established; details and scope are in `RC13_SPARSE_PROOF.json`. |
| Capacity and devices | This sigil/fuel case switches to dense at frame 32 on Intel and 30 on RTX and remains dense. Existing migration/reset/disposal fixtures pass. Browser frame pacing and physical mobile memory/device acceptance remain open. |

## rc.14 wood gates

[WOOD_RESEARCH.md](WOOD_RESEARCH.md) records 19 primary sources, the implemented reductions and the material/geometry provenance. [RC14_WOOD_PROOF.json](RC14_WOOD_PROOF.json) records the native checks and matched cost comparison.

| Gate | rc.14 status |
| --- | --- |
| Shared material | Logs, timber house, native-contour wooden sigil, reviewed CYBR tree and dropped wood use finite stock, moisture, char, surface/core heat and persistent damage in both engines. Original remains a projected material solve; Volume uses 64³ material cells. |
| Geometry and fracture | All 1,588,926 reviewed tree triangles remain, with 88,760 new cap triangles. Reduced beam failure accounts for remaining subtree mass, bending, axial and shear loads. Detached pieces fall with coherent poses and exposed grain. Controlled pre-charred and cut-joint fixtures verify breakup; they are not natural-burn predictions. |
| Native execution | Original passes 17 gates with 48 compiled production programs. Final Volume recordings pass cold-tree, sustained post-ignition wood release, sigil, house, cut-piece and Intel sparse/floor bindings, with finite material/pose fields and valid recorded CFL. Representative frames and held views were inspected. |
| Cost and lifecycle | Stable structure buffers and cached groups avoid per-step allocation. Fine-brick source support and remaining-mass aggregation replace expensive scans. Matched RTX cold-tree completed GPU work rises from 17.209 to 22.213 ms with the added physics and material, at fixed 768×432 and three gas substeps. This is native offscreen work, not browser FPS. |
| Remaining scope | No specimen-fitted phase-field/FEM fracture, elastic flex, redundant-joint mechanics, fragment-to-fragment collisions, conservative firebrand ignition or mobile/browser pacing certification. The material clock defaults to 12×; rigid bodies and gas remain at real time. |

## rc.15 powers and startup repair

[Power controls and implementation](FIRE_POWERS.md) cover six shared source IDs in Original, Volume and experimental Sparse. Powers feed transported gas and the existing combustion/soot/light paths. Source animation is evaluated live; no prerecorded flames are loaded. Resolution and normal/wood reaction coefficients remain unchanged. Finite casts capture their aim and strength; continuous controls remain live. Floor trails use finite floor fuel and break a stroke when the pointer leaves the floor.

The reported rc.14 startup failure was real: screen derivatives in wood helpers were called beneath varying fragment branches. Native Naga compilation did not catch Tint's uniformity rejection. rc.15 makes WGSL wood helpers derivative-free, captures ray derivatives at fragment entry, moves mesh derivatives and implicit texture sampling before discard, and uses analytic ray-hit footprints. No derivative diagnostic is suppressed. Strict Tint also exposed a separate Sparse allocator collective-exit error; explicit workgroup-uniform decisions now surround its barriers while retaining sticky fallback and page migration.

| Gate | rc.15 status |
| --- | --- |
| CPU behavior | 237 tests pass; 35 runtime runners execute against source, package and deployed directory. State, saved looks, source pairing, cast/reset ordering, finite inventory and uniformity checks are included. |
| Strict WGSL | Official Dawn `webgpu@0.6.1`, null backend: 145 unique modules / 172 generated variants, zero errors or warnings. A deliberately divergent derivative fixture is rejected. This is compiler validation with no browser or GPU submissions. |
| Original native | 13 gates pass; 11 startup cases compile/link 61 unique production GLSL programs. All six powers evolve finite fuel, heat, reaction and soot in the actual gas programs. |
| Volume native | Final power, Sparse and wood renderer frames are recorded in [RC15_POWERS_PROOF.json](RC15_POWERS_PROOF.json). Their native command replay checks actual pipeline bindings, finite fields and measured CFL. Held views and representative temporal frames are reviewed. |
| Performance scope | Powers add bounded source/force evaluation to existing kernels and 16 bytes to simulation uniforms; they add no simulation pass or per-frame GPU resource allocation. Completed native GPU costs are recorded with their fixed substep and output settings. Browser FPS, RAF pacing and mobile acceptance remain unverified. |

The previous wood report remains historical evidence of its reductions and tests; it did not certify browser startup. The new strict compiler gate specifically covers the failure reported by the user. Native screenshots and field probes are development evidence, excluded from the public runtime package.

## rc.16 saved-look cast ordering

The first cast now receives a saved look's strength and aim before source reset or runtime creation. A remounted runtime receives `initialPowers`; the same-engine source switch applies those settings before `fire()`. Finite floor trails also receive the correct first deposit strength. Subsequent edits still apply to the next finite cast.

All **241 CPU tests** pass, including four new shell tests for saved first casts, domain remounts, simulation remounts and counterpart mode switches. Original also checks actual first submitted aim/strength uniforms and the initial floor-fuel packet. This correction changes host state ordering, not generated shader equations, simulation resolution, GPU passes or source geometry. [RC16_STATE_PROOF.json](RC16_STATE_PROOF.json) records the final state tests, package checks and compiler-module identity with rc.15. The native field and frame evidence above remains applicable to the identical shaders.

## rc.17 Sparse startup compatibility and diagnostics

The reported `Invalid ShaderModule chemistry-pool-topology` is a secondary error: Sparse initialization consumed a module without first reading its compiler errors. rc.17 now captures module diagnostics and creation validation scopes before pipeline creation, retains line/column details and the failing label, and cleans up allocated resources on rejection. Compiler-info rejection, creation errors, backend pipeline failure and clean retry are covered by CPU tests.

Topology barriers now execute for every lane, with allocation phases gated after capacity preflight. The shader has no collective early exits or `workgroupUniformLoad` calls. Deterministic allocation, generation counters, migration commands and sticky dense fallback remain. Neither chemistry, source equations, resolution nor simulation passes change.

[RC17_SPARSE_STARTUP_PROOF.json](RC17_SPARSE_STARTUP_PROOF.json) records **243 CPU tests**, **210 strict Tint modules / 322 generated variants**, **160 native Direct3D pipeline creations** across DXC/FXC and Intel/RTX adapters, and **64 allocator comparisons with all five buffers byte-identical** to rc.16. A 60-frame production Sparse command replay plus three held views passes on the integrated GPU with finite fields and valid measured CFL.

The original rc.16 shader also passed native pipeline creation here. The affected browser's first compiler message remains unavailable, so this evidence does not establish its exact root cause or certify live-browser startup. The compatibility change removes the collective-exit requirement; the diagnostic change ensures the primary failure is visible if startup still fails. Shared links to the new content fingerprint load the new module graph. Browser FPS and mobile acceptance remain open.

## rc.18 ability choreography candidate

[Fire powers](FIRE_POWERS.md) now describes **24 shared abilities** in Original, Volume and experimental Sparse. Twenty have finite action/recovery sequences; four sustain until stopped. Four finite cast slots retain independent clocks and aim, while sustained powers use one source. Charging, release, dragging, pause, source shutoff, same-page mode changes and saved looks use the existing studio controls.

The first full 24-ability native Original pass executed successfully but was **rejected visually**: several cues and traveling sources were too dim, and some silhouettes merged in the default view. The shipping V5b source has faster bounded ignition, resolved fuel gaps and rotational momentum, broader fireball support, warped impacts, tip-derived whip momentum, a wider vertically weaving serpent, outward cross arms and a tilted returning crescent. The shared crescent axis corrects a rotated source that previously crossed Original's shallow depth. Source bounds and finite-window speed protection follow these changes. Final native execution and sampled imagery are verified/reviewed with explicit visual limitations.

| Gate | rc.18 candidate status |
| --- | --- |
| CPU | Final shipping suite: 295/295, including the crescent-rotation regression and retained Original implementation. Targeted controller/lifecycle/catalog/state checks also pass 23/23. |
| Strict compiler | Exact recorded Volume/Sparse coverage: 211 unique Tint modules / 1,655 variants, zero errors/warnings; the divergent derivative control is rejected. Dawn null backend performs no physical GPU work. |
| Original native | 24 ability, four held-charge and two overlap cases pass: 30 cases, 264 captures. Startup compile/link passes 29 cases / 696 program instances / 61 unique programs. Eleven source hashes and decoded RGB capture checksums match. |
| Volume and Sparse native | 27 final scenarios plus four live-angle probes pass numeric gates: 5,878 simulation frames, 62 finite-field snapshots, maximum measured CFL 0.9671304208260997. With six supplemental V5b probes: 37/37 scenarios, 6,754 native frames, 74 snapshots. Sparse barrage becomes sticky dense at frame 48; its peak held views are dense. |
| Visual identity | Sampled motion/control imagery is reviewed with uneven fidelity. Original retains faint cues/whip recovery, merged packets, rectangular wall edges and coarse-depth cooling contours. Volume retains pale smooth cores, thin jets, compact serpent and small crescent. No cinematic/offline equivalence is established. |
| Cost | The 27 full-sequence warm GPU medians range 27.864064–58.966528 ms on RTX 4060/Vulkan in the fixed 128³/256³, max-speed 24, six-substep fixture. Whole-submission timestamps and actual storage modes are recorded; no paired speedup, browser FPS or mobile result is established. |
| Package and deployment | Final directory and ZIP pass verification: 155 files, build `7dfac6909b1f2622`. Public delivery matches all 155 runtime files plus `release.json`, with HTTP 200 and exact hashes. Site commit / completed Pages build: `7ec5442fad209245fdc48f96c0e5b43cf9f15117`. |
| Browser and mobile | Live browser startup, interaction and sustained frame pacing remain unverified. Physical mobile acceptance is separate from native validation and public byte delivery. |

[RC18_POWERS_PROOF.json](RC18_POWERS_PROOF.json) records completed CPU/compiler/source-math/native execution, sampled visual review, package verification and public byte delivery, separating the rejected pass from the shipping implementation. Final report/runtime/package hashes are recorded, with visual limits retained. [Public Fire Studio](https://cybrdelic.github.io/firesim/) delivers the verified build; `work/sparse-startup-qa/public-rc18.json` records 204,586,772 exact HTTP bytes including the manifest, and the site index proof matches 156/156 blobs. Native execution, sampled visual review, package verification, public delivery, live browser demo and mobile readiness have independent status. Actual browser pacing and physical mobile checks remain unverified. The earlier six-power captures do not certify the expanded cast controller or these revised source equations.

## rc.19 wood velocity stability

[Wood stability](WOOD_STABILITY.md) and [the compact proof](RC19_WOOD_STABILITY_PROOF.json) record the reported `burning-logs` failure, rejected candidates and final acceptance separately. Actual native mapped velocity bytes now exercise production adaptive timesteps, rather than fixing the recorder at a high velocity budget.

Released wood vapor carries both sensible energy and heat capacity. Its delivered mass also supplies a volume source to the global pressure solve, allowing vapor to displace air. A finite gas igniter starts the cold material; reduced hot-product ignition memory permits established wood combustion to sustain and subsequently quench. This uses transported soot and oxygen deficit as a mixture-state proxy, not radical/species chemistry or per-cell fuel provenance. Timestep prediction reserves the upcoming interval in addition to telemetry delay, with a finite structured-wood startup margin. Velocity and temperature are not capped to hide the reported instability; the existing invalid-state and substep guards remain.

All 128³ flow and 256³ gas voxels remain. The correction adds no simulation pass or GPU allocation. The native worker serially completes submissions before driving the next production frame, so its finite-field, CFL and binding checks do not establish live browser pacing or mobile performance. A locally ignited cold wood pile can burn down toward smolder while retaining unignited stock; evidence must distinguish that from complete consumption or sustained full involvement.

| Gate | rc.19 result |
| --- | --- |
| CPU and packaging | 39 runtime runners pass source validation; 9 package unit tests pass. Targeted native-feedback, telemetry and wood checks are recorded in the proof. |
| Strict compiler | 211 unique WGSL modules / 515 generated and recorded variants pass official Dawn/Tint null-backend validation with no errors or warnings, including wood mechanics and actual dense/Sparse/tree commands. The divergent derivative fixture is rejected. |
| Actual adaptive feedback | Seven final native cases pass: 1,860 simulation frames plus three held views. Maximum measured CFL is 1.393519 against the 1.5 limit. Normal logs run 600 frames; delayed 24× wood runs 360. |
| Modes and hardware | RTX 4060 and Intel UHD/Vulkan bonfires pass. Sparse's pooled stage has no stale mappings and later uses its existing sticky dense fallback. Ordinary Bonfire and nonwood Torch controls pass. The cold tree checks bindings and finite state; it does not establish successful tree ignition. |
| Sampled appearance | Normal logs retain rooted flames after the finite starter ends, then approach weaker flaming/smolder. Held Sparse views and the Intel capture retain rooted flame and room illumination. The delayed 24× stress extinguishes; it is a numerical and quenching gate, not persistent-fire evidence. |
| Performance and fidelity | Resolution and render integration remain unchanged. Recorded native costs depend on smoke coverage and hardware; these runs establish no paired speedup, browser FPS, mobile support or cinematic/offline parity. |

## Publish to GitHub Pages

The local checkout `../firesim-site` points to `https://github.com/cybrdelic/cybrdelic.github.io.git`. The public path is `/firesim/`. Inspect its branch, working tree and GitHub Pages configuration before publishing. Preserve unrelated site contents and copy only a validated package into the `firesim/` subtree. Do not copy test tools, screenshots or historical experiment folders.

Deploy the exact packaged bytes, including `release.json`, through the repository's configured Pages branch/workflow. Compare the published `release.json` and representative module/asset SHA-256 hashes against the package, then confirm that the HTML entry, stylesheets, both engine imports, source binaries, preview images and redirect alias return successful responses under `/firesim/`. Inspect a live presentation after deployment on the actual demonstration browser and GPU.

The package contains a large imported tree model. A first tree selection transfers its mesh and texture assets; ordinary fire does not need those assets to start. Keep tree experiments separate from the opening demo and describe their structure as a reduced beam/rigid-fragment model.

## Demonstration acceptance

| Concern | Acceptance evidence |
| --- | --- |
| Fire shape and internal detail | Original sigil, torch, campfire and dense fire have dark gaps, separated hot cores and evolving folds without a painted repeating texture. Compare a motion sequence with the approved offline reference at matched framing. |
| Smoke coupling | Smoke-only burst expands and rolls; burning smoke follows the gas flow through fuel shutoff and source dragging. Inspect it with neutral side/back lighting and at several angles. |
| Volume artifacts | Dense fire and oil bursts do not introduce crosshatching, tile boundaries, transient holes or transparent hollow cores. Inspect the full motion sequence, not one favorable still. |
| Fire illumination | Source-shaped fire illumination reaches gas and room receivers. Check off-center sources, multiple emitting regions, paused light changes and darkness after emission ends. |
| Inspection and fuel | Use Fully lit to read cold patches and source surfaces. Toggle Show sigil at front and grazing angles. Drop unlit fuel, ignite it once, inspect burn-down/char, clear only the deposits, then Restart. Repeat in both engines. |
| Sources and presets | Both engines expose matching source IDs and recover camera/fuel/light settings across engine switches, shared URLs and saved looks. Experimental geometry/effects retain visible status. |
| Sparse mode | Select Sparse volume on the same page, verify its shared sources/inspection/fuel controls, and compare fields and motion with standard 3D volume. Record actual storage mode and any fallback alongside cost and memory. |
| Objects | Inspect cold stock, ignition contact, char, cracks, finite burn-down and detached capped geometry. Trees use the reviewed mesh. Distinguish reduced beam breakup from specimen-validated fracture; ember ignition is not implemented. |
| Frame pacing | Record completed FPS, frame p95, simulation seconds per wall second, GPU stages and memory over sustained interaction, with the browser renderer/adapter named. Repeated presentation of an unchanged frame does not count as simulation throughput. |
| Device handling | Verify cold start, engine switch, restart, rapid preset selection, resize, background/foreground, back/forward restoration and recoverable device failure on the demonstration machine. |
| Mobile | Verify memory, interaction, adapter compatibility and sustained completed frames on physical mobile hardware before declaring support. Desktop native shader checks cannot close this gate. |
| Presentation | Open the intended shared URL, use Present, confirm responsive layout and keyboard recovery, and check that no development capture endpoint or experimental page opens during the planned demo. |

If a gate fails, record the failing scene, browser adapter, build fingerprint and a motion/performance capture in the development evidence. Keep the published documentation aligned with that evidence. Do not describe the candidate as having offline parity or guaranteed high FPS without a matching result.

## Copy and code audit

The AI Slop checker is a heuristic for filler, unfinished templates and repetition. Its source-tree scan also sees GLSL boilerplate and duplicated historical experiments; those are not proof of generated product copy. Review the flagged lines manually and scan the actual package after building. Input `placeholder` attributes are ordinary UI hints and should not be removed merely to reduce the score.

Keep demo descriptions concrete about the source, fuel, motion, lighting and test purpose. Product copy must not imply specimen-calibrated chemistry or collapse, mobile compatibility or measured realtime performance that the implementation and evidence do not establish. The source history stays in `development-history.md`; the release README describes current use and limits.
