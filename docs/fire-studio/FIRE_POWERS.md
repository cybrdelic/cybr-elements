# Fire powers

> Retained design/development record. Historical case results and release numbers below
> describe their original captures, not this consolidated browser build. Bulk diagnostic
> reports and iteration archives remain in the private recovery backup. See
> [current known issues](../KNOWN_ISSUES.md) and [validation scope](../VALIDATION.md).

The rc.18 candidate exposes twenty-four shared abilities under **Source → Powers** and **Library → Powers** in Original, 3D Volume and Sparse volume. Switching simulations keeps the selected power, strength and aim. Each engine retains its own camera framing. Library search also recognizes movement groups such as Projectiles, Terrain, Directed and Sweeps. Native acceptance and public deployment are tracked separately below.

## Core powers

| Power | Live behavior |
| --- | --- |
| Radial blast | A floor-level wave injects outward momentum and burning gas. Irregular crests feed a rolling wake; released flame and soot keep evolving. |
| Fireball | A burning head follows a range-limited aimed arc, leaves a combustion wake and releases an impact plume. Its destination stays above the floor. |
| Fire rain | Nine staggered packets follow curved falling paths, leave transported wakes and redirect gas near impact. Move the rain field with the cursor; stopping it ends fresh packets. |
| Fire tornado | Two rotating, widening fuel strands and bounded circulation force drive a moving updraft. Source and circulation share the moving axis. Stopping it removes fresh fuel and imposed circulation. |
| Fire floor trail | Dragging deposits and ignites finite oil fuel on the floor. Existing patches burn down after the cursor leaves. |
| Combustion bomb | A visible small charge burns for 1.2 seconds, then releases a brief outward burst. The flame extinguishes into an evolving soot cloud. |

## Choreographed abilities

| Ability | Action identity |
| --- | --- |
| Flame dash | Floor charge → accelerating surge → braking flare and burning wake. |
| Flame whip | Curl → sweeping arc → tip crack/recoil → recovery. |
| Ember orbit | Three satellites gather and tighten → staggered fan release. |
| Heat seeker | Charge → weaving arc toward the cast aim → impact plume. |
| Phoenix dive | Paired wings open and climb → folded dive → ground fan. |
| Dragon breath | Short gather → overlapping directed pulses → lingering turbulent wake. |
| Solar lance | Concentrated tip charge → fast narrow release → terminal flare. |
| Flame wall | Floor seam → three panels rise at staggered times → panels stop feeding in sequence. |
| Inferno ring | Uneven barrier rises → rotating inward pulses → breakup. |
| Meteor strike | Floor cue → overhead burning body → accelerating curved fall → rolling impact. |
| Meteor barrage | Staggered falls on separate arcs → successive interacting plumes. |
| Eruption chain | Advancing floor warning → ordered zigzag geysers → decay. |
| Combustion mine | Quiet planted charge → finite wait → short blast and heavy soot. |
| Vortex burst | Inward draw → tight helical gather → outward momentum reversal. |
| Flame serpent | Traveling head weaves sideways and vertically → three delayed burning ribbons follow with local tangent momentum → impact and drifting wake. |
| Cinder scatter | Cluster charge → diverging packets → independent impact flares. |
| Fire cross | Paired outward arms grow from the center → delayed perpendicular arms → central flare and lingering wakes. |
| Flame crescent | Curved launch → hooked return → arc opens and fades. |

The shared [timing registry](../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-power-definitions.js) supplies windup, finite cast duration, sustained behavior, aim mode and bounded impulse-speed windows. Twenty abilities have finite sequences lasting 0.95–4.5 simulation seconds, with three to six named phases. Rain, tornado, floor trail and breath sustain until stopped. The source position, fuel release and momentum change through these phases; visible follow-through comes from transported gas. Native execution and sampled visual review are recorded separately below.

Flame wall begins its three rises 0.18 seconds apart and ends their fresh feed 0.20 seconds apart. Eruption chain moves a small floor warning between the future geyser positions, with releases at 0.28, 0.70 and 1.12 seconds. Meteor barrage uses three staggered trajectories; Cinder scatter releases five separate packets. These bounded actors feed the gas rather than rendering flame meshes.

## Controls

- Select the **Fire** interaction tool. Click to run a finite sequence; drag to move sustained rain, tornado, breath or trail placement. Floor powers require a floor point inside the simulation area, and selecting them makes the room visible.
- **Cast power**, **Launch fireball** or **Charge bomb** repeats the selected effect at its current origin. **B** also casts. Recasting adds to the existing gas. Up to four finite casts retain separate clocks and destinations; further casts reuse the oldest source slot. Sustained powers use one active source. Switching to a sustained source ends earlier fresh injection while released gas keeps evolving.
- **Power strength** ranges from 25% to 200%. Projectile and aimed abilities expose **Heading** and **Elevation**. Directional floor attacks also expose **Heading**: rotate the wall, dash, chained eruptions, crossing sweeps, phoenix dive or meteor approach. Floor attacks hide Elevation. Fireball, Heat seeker, Solar lance and Cinder scatter are chargeable: hold, drag to aim and release to cast; the Cast button runs their complete sequence. Finite powers capture settings, including source heading, at launch, so changing them affects the next cast. Continuous powers follow updated strength and direction. The UI shows phase progress, held charge and the active cast count.
- **Pause** or **Space** freezes simulation time, including the bomb fuse and source animation. Casting resumes the simulation.
- **Stop power / Stop casting** ends fresh injection or placement. Existing gas, soot and deposited burning fuel continue evolving. **Clear fuel** removes floor inventory; **Restart** resets the scene.
- Shift/right-drag pans and the wheel zooms. Shared links and saved looks retain strength and aim alongside lighting and camera settings.

## Implementation and limits

[fire-powers.js](../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-powers.js) supplies shared analytic support, source motion and momentum in WGSL and GLSL. These sources feed each engine's existing GPU gas, combustion, soot and lighting paths. They use no prerecorded flames or animation frames and do not lower the simulation or rendering resolution.

Fresh power fuel adds heat through a bounded relaxation toward `1.8 × preheat`, preserving any hotter transported gas. V3 uses a faster relaxation gain of 48 so thin traveling sources can ignite during their short contact with fresh gas. Injection lowers the available oxygen fraction, and combustion consumes fuel in the surrounding flow to produce heat and soot. The pilot ceiling remains fixed. Resolved fuel pockets and rotational momentum enter the gas source; they are transported through the solver. These scales are authored controls rather than a calibrated combustion model.

Natural Powers color in Original uses a temperature-driven, three-band blackbody approximation consistent with the Volume renderer. Original's room lighting uses that same power spectrum. The normal gas presets retain their existing spectrum, and explicit color controls remain available. This improves color consistency without implying the engines have identical temperature fields or spectral rendering.

Volume source work uses conservative per-brick support tests: an expanding annulus for radial fire, moving head/wake bounds, capsules for ribbons and wall sheets, nine moving rain-packet bounds, a bent tornado column and separate fuse/burst bounds. Rain evaluates four adjacent lanes at each gas sample. Empty source regions skip source evaluation; retained gas follows the existing advection and pressure paths. Voxel size and global flow remain unchanged.

Original uses its layered flow representation; Volume uses its full 3D flow. Sparse uses Volume's pooled chemistry with global flow and pressure, and may fall back to dense storage. Matching source IDs do not imply identical images across engines.

Original's late cooling reaction fronts can still show facets from its coarse depth representation, including the phoenix follow-through. Higher sample counts, alternate reconstruction filters and reaction/timestep experiments did not provide an accepted visual/cost correction and were reverted. This remains a presentation limit. The targeted Volume review accepts the compact serpent body and softer flame core as current limits; it does not establish offline visual parity.

Cast destinations keep the authored travel range and each engine's simulation bounds together. Impact and jet sources reserve horizontal and upper space for their flare, including fan spread and the serpent's raised impact center. If the range sphere cannot reach the requested inset, the controller reduces only the reservation. An inset larger than half a narrow domain collapses to its midpoint, so it cannot guarantee full radial containment. Moving ground paths shorten to the available destination distance. Origins placed near an edge, expanding impact gas and transported wakes can still leave the bounded scene. Fireball motion and tornado circulation are authored controls rather than rigid-body or weather simulations. Heat seeker follows its fixed cast destination; Combustion mine uses a timed 1.8-second armed phase. Rain supplies gas packets, and floor trails spend the existing finite fuel inventory. A stationary trail cursor does not continuously refill a patch.

The expanded registry separates source injection from cast recovery. Its finite windows include windup and follow-through, so a cast can remain visible after fresh injection stops. Released gas continues evolving after the cast window. The six-source native proof predates these longer action windows and the expanded cast controller.

## Authored combustion profiles

All twenty-four abilities have separate combustion and flow profiles. These are bounded artistic controls, not calibrated material constants. Grid spacing, volume sampling and the shared comparison lighting remain fixed. The original six tuned profiles are retained:

| Power | Preheat scale | Fuel dose | Soot yield | Turbulence | Buoyant lift |
| --- | ---: | ---: | ---: | ---: | ---: |
| Radial blast | 0.72 | 0.65 | 0.32 | 1.20 | 0.55 |
| Fireball | 0.72 | 0.70 | 0.45 | 0.90 | 0.35 |
| Fire rain | 0.72 | 0.60 | 0.95 | 0.85 | 0.35 |
| Fire tornado | 0.65 | 0.62 | 0.55 | 1.25 | 0.70 |
| Floor trail | 0.68 | 0.55 | 1.10 | 0.95 | 0.65 |
| Combustion bomb | 0.75 | 0.85 | 1.30 | 1.10 | 0.85 |

Radial fire uses cleaner fuel and moderate lift to preserve its low outward wave. Fireball and rain have lower lift so their directed motion remains readable. Tornado relies on circulation and turbulence, with modest expansion rather than a continuously inflated column. Bomb uses a heavier soot profile and more expansion after its fuse. Trail release comes from its finite floor inventory; its source-dose and preheat controls do not manufacture extra fuel.

The radial origin is 0.18 scene units above the floor, with a 0.12 minimum placement height. This replaces the previous raised source without changing simulation resolution. The refinement follows a bounded three-iteration visual review; the preserved baseline and decision ledger are in `work/powers-quality-review/VISUAL_LOOP.md`.

## Wood startup correction

The reported Volume startup error came from quad derivatives hidden inside wood helpers called from varying hit/material branches. Mesh cap and leaf discard could also precede derivative-dependent sampling.

Shared WGSL wood helpers are now pure. Mesh derivatives and implicit samples execute before varying branches or discard. Conditional ray hits receive analytic perspective footprints derived from ray differentials captured at fragment entry. Original keeps its GLSL material API. No derivative diagnostic is disabled.

## Verification status

The final shipping CPU suite passes **295/295 tests** in `work/powers-rc18-shipping-suite.log`, including the tilted-crescent regression and the retained Original implementation. The targeted controller/lifecycle/catalog/state runs also pass **23/23**. Exact recorded Volume/Sparse shader coverage passes strict Tint with **211 unique modules / 1,655 variants**, zero errors or warnings, in `work/dawn-qa/tint-powers-rc18-shipping-exact/report.json`. The deliberately divergent derivative control is rejected. These compiler checks use the Dawn null backend with no physical GPU work. Catalog/state gates check all twenty-four identities, cross-engine links, finite phase windows, late impulse guards and matching WGSL/GLSL expansion timing; none establishes rendered motion quality.

The read-only math audit at `work/powers-quality-review/expanded-motion-audit.json` records production hashes and corrected counterexamples for mine/vortex burst support, a steep lance cue, seeker endpoint continuity, crescent domain reach and a long aimed flight. It also proves the connected wall sheets fit their padded capsule and reviews all twenty-four source lifetimes. These checks found actual omitted fuel and a pre-telemetry guard gap, then verified the corrected equations/controller behavior. The source audit remains separate from native rendered-frame review.

`work/powers-quality-review/impact-controller-audit.json` checks all default destinations against both engine domains and records conservative bounds for the enlarged orbit packets, delayed serpent ribbons and widening tornado feed. Targeted controller regressions cover eight headings, low/level/steep elevation, corner pointer aims, held release, continuous updates and atomic rejection of impossible launches. Clamping reuses constructor-owned scratch buffers and preserves the four-slot uniform layout. These CPU checks do not establish visual acceptance or frame pacing.

V5b widens the three serpent ribbons and adds vertical weaving, grows the cross outward from its center, and thickens the returning crescent. The crescent's former Heading −25° depth failure is corrected by one tilted blade axis shared by its center, endpoints, velocity derivative and support. The source-domain sweep checks 72 default headings and 301 shape times in both domains without a side-wall fuel counterexample. The near-unit tilt preserves blade length and its speed bound; its lower edge can touch the floor. Source support and declared speed guards remain conservative. Six targeted Volume scenarios supply supplemental live-angle evidence for the exact shipping shaders.

The first full 24-ability Original native replay at `work/original-powers-visual/abilities24-final2-native/` executed production commands successfully but was rejected visually for dim cues/travel and merged silhouettes. The shipping V5b source includes faster bounded ignition, source pockets/spin, broader fireball support, warped impact fronts, tip-derived whip momentum, clearer body motion and the corrected crescent axis. Final Original replay passes 24 abilities, four held-charge cases and two overlap cases: 30 cases and 264 captures. Its startup compiler passes 29 cases, 696 program instances and 61 unique programs. All eleven recorded source hashes match the frozen runtime. RC18_POWERS_PROOF.json (`RC18_POWERS_PROOF.json`, archived locally) preserves the rejected pass and the final reviewed implementation separately.

`work/powers-qa/rc18-shipping-volume-recordings.json` records 27 frozen CPU command traces covering all 24 abilities plus interaction scenarios: 5,532 simulated frames and stable recorded resource pools. These traces supplied the strict compiler coverage. Their generation performs no physical GPU work; recording counts are not native acceptance or realtime performance measurements.

Final Volume/Sparse native replay passes all 27 scenarios plus four live-angle probes: 5,878 simulation frames, 5,971 frames including held views, and 62 finite-field snapshots. Maximum measured CFL is 0.9671304208260997 in the fixed fixture. `work/powers-qa/rc18-shipping-volume-numeric-proof.json` and `rc18-shipping-live-angle-numeric-proof.json` record execution, field checks, actual storage and completed GPU costs. The sparse barrage migrates once to dense backing at frame 48; its peak held views validate continuity after fallback, not sustained pooled chemistry.

The six supplemental exact-source V5b probes bring the combined numeric inventory to **37/37 scenarios, 6,754 native frames and 74 field snapshots** in `work/powers-qa/rc18-shipping-complete-native-numeric-proof.json`. The 27 full-sequence warm GPU medians range from **27.864064 to 58.966528 ms** on the RTX 4060 Laptop GPU, Vulkan driver 610.62, at fixed 128³ flow / 256³ chemistry, max-speed fixture 24 and six substeps. These are whole-submission native timestamps with the first twelve frames excluded, recorded in `rc18-shipping-native-cost-summary.json`; changing sources and older pass-instrumented traces are not a paired speedup benchmark.

Both engines' sampled motion and control imagery were reviewed with limitations. Original retains faint cues/whip recovery, merged orbit/scatter packets, rectangular wall feed edges and coarse-depth cooling contours. Volume retains smooth pale cores, thin directed ribbons, recognizable rain lanes, a compact serpent body and a small crescent. Twenty-five Volume lifecycle cases are readable with limits, one serpent case is partially readable, and the Sparse case is readable after dense fallback. These reviews pass feature/control integration with uneven visual fidelity; they do not establish cinematic or offline equivalence. The exact decisions are linked in the RC18 proof.

Historical six-power Original evidence under `work/original-powers-visual/v3-final-shapes/` and Volume recordings under `work/adaptive-volume-qa/powers-final-*` predate the expanded choreography. They remain development comparisons. Current native cost comparisons must use matching cameras, output size, timestep, substeps and timing instrumentation, and exclude held-angle frames. Per-pass profiles remain diagnostic evidence when their extra timestamps differ from the baseline fixture.

The RC18 proof records completed CPU, compiler, source-math and native evidence with exact runtime/report hashes. The final package `releases/fire-studio-0.1.0-rc.18-final/` and its ZIP pass verification: 155 files, build `7dfac6909b1f2622`. All packaged directory files also match their manifest hashes independently. [Public Fire Studio](https://cybrdelic.github.io/firesim/) now delivers that build: all 155 runtime files and `release.json` return HTTP 200 with exact package hashes. Site commit `7ec5442fad209245fdc48f96c0e5b43cf9f15117` is the completed Pages build. `work/sparse-startup-qa/public-rc18.json` records 204,586,772 verified HTTP bytes including the manifest. Native execution, sampled visual review, packaged bytes and public byte delivery have separate status fields. Live browser startup/interaction/frame pacing and physical mobile acceptance remain unverified until checked on those devices. The earlier six-source captures do not validate the expanded action, charge/release or overlapping-cast paths.

Native timestamps and synchronous replay times do not establish browser FPS or mobile performance. Compiler checks establish shader legality, not visual quality. See the [current validation scope](../VALIDATION.md) for conditions and remaining gates.
