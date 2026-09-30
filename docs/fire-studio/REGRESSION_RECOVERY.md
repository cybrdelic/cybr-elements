# Fire Studio regression recovery — September 29, 2026

This recovery corrects regressions found after rc.6/rc.7. It does not establish offline image parity, movie-quality explosions or sustained browser performance.

## Rendering changes recovered

Original's darker thermal spectrum reduced hot-core contrast. Six regular wood pockets, extra filtered velocity forcing, reduced wood soot yield/lifetime and much stronger reaction extinction also changed its source and flame appearance. Restore the earlier thermal spectrum, three-pocket wood bed, noise sampling, soot transport/lifetime and thin reaction extinction. Keep the shared source catalog, appearance controls, startup fix and existing solver safety improvements.

The 3D wood source had also become six regularly lobed emitters with weaker feed and expansion. Matched bonfire/hearth sequences confirmed rounded separated ignition lobes and a squat plume. Restore the established continuous feed, velocity, expansion and conservative source activation bounds. Keep the current bonfire height correction, pressure/workgroup improvements, query handling and tree resize fixes.

Normal Original scenes now compile without the object surface marcher. Object domains retain it. A 90-frame alternating native comparison produced identical pixels, but timing distributions overlap; no reliable speedup is claimed.

## Interaction corrections

- Matched engine switches retain fuel, color, smoke inspection, room and fire illumination.
- A source remount no longer restores another source's camera or color.
- Scene and lighting edits remain locked through the full source transition while runtime capability states remain intact.
- Volume source changes return their reset completion. Requests during an active frame or benchmark wait for the queued reset, including while the view is hidden.
- Geometry preparation precedes surface reset. Controls wait for the first source frame and GPU drain; preparation, reset and rendering failures propagate to recovery.
- Disposal drains active reset work and settles queued requests before destroying the device. Use Original selects the matching source.

## Evidence

The final native Original sigil/campfire sequences use 640 × 360 × 32 cells, actual transport/pressure/combustion/optical shaders, exact production noise, and actual smoke gather/prefix shadow passes. Each completes six simulated seconds with no GL errors. Representative sheets were inspected directly. They show restored thermal highlights, connected irregular wood flame and advected, self-shadowed soot. They use an unlit frontal inspection projection rather than the actual room. Timing varies substantially with machine load; these captures establish neither browser FPS nor default camera framing.

Earlier Original QA omitted source uniforms, texture rebindings after capture, correct sigil vorticity coverage and smoke shadow execution. Those omissions are corrected and recorded in the new fixture reports. Earlier captures and timing summaries must not be treated as full runtime proof.

Volume comparisons use the same current bonfire parameters, 128³ velocity and 256³ scalars, 768 × 432 output, and native RTX 4060/Vulkan. Restored-source median simulation time is 4.332 ms versus 4.340 ms for the regressed source. The fuller flow requires additional CFL substeps later: p95 increases from 5.188 to 12.583 ms. It remains below the prior shader baseline's 16.453 ms p95 in this trial. This is a native workload comparison, not a guarantee of equal browser frame pacing. Hearth shows the same source regression/recovery and retains an unrealistic rounded startup cap.

The 64 room atlas is retained after alternating same-state 64/128 receiver comparisons. Focused floor crops differ by about 0.10 RGB levels of 255 on average; p99 is 1. Median paired lighting time is 1.072 versus 1.348 ms. This narrow check does not certify every object or spotlight shadow.

Durable evidence:

- `work/fire-recovery-original/final-sigil-flow-full-seq/` and `final-campfire-shadow-full-seq/`
- `work/fire-recovery-original/original-pruning-abba.json`
- `work/volume-recovery-qa/RESULTS.md` and its matched motion/receiver sheets
- `work/fire-release-audit/recovery-node-tests.log`

59 Node tests, six package tests and native compilation of Original simulation, props, room lighting and both normal/object room renderers pass. Startup, shared-shell transitions and actual Volume reset functions also execute against completed packages and deployment copies using DOM/GPU fixtures. They do not substitute for live-browser visual or performance acceptance.

## Open gates

Rounded early Volume ignition, movie/offline visual parity, actual demonstration-browser frame pacing, extreme object/lighting scenes and mobile hardware remain open. The Volume engine remains experimental. The public release must retain these limits and its acceptance gates.
