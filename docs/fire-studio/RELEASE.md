# Fire Studio release procedure

The deployable unit is the output of `tools/fire-studio/package.py`. Historical renderer trials are archived under `work/fire-studio-research-archive/`, outside the served source tree. Copy the validated package so authoring assets and development notes stay out of the release.

## Build and validate

Run the Node state/lifecycle/telemetry suites, startup/transition/reset/lighting/optical/sustained-scheduling regressions and query/resize gates, the Python package suite and `package.py --check` listed in the runtime README. Package validation runs those six runtime checks automatically against source, the completed build and directory verification. `FIRE_STUDIO_ROOT` can also select a directory for manual checks. They exercise JavaScript initialization, shared shell transitions, actual reset ordering, normal/tree lighting bindings, optical mask ping-pong and 10,000 display ticks with DOM/GPU fixtures; live browser/device acceptance remains separate. After all runtime changes are complete, create a fresh package with `python tools/fire-studio/package.py --out releases/fire-studio-RELEASE-NAME`. The name must be new; the builder does not overwrite previous artifacts.

The package records the exact shipped bytes and a content-derived build fingerprint. JavaScript imports, classic shader scripts, stylesheets and local runtime asset URLs use that fingerprint as their cache key. The artifact preserves the single-page entry and the old `pyro-gpu/` redirect. Tree binaries and source previews are validated before packaging; imported tree geometry remains a lazy source load.

Check the resulting `release.json`, ZIP and runtime directory together with `python tools/fire-studio/package.py --verify PATH-TO-DIRECTORY-OR-ZIP`. This confirms file hashes, transformed JavaScript syntax and that no unrecorded files are present. Never modify a packaged script after generating the manifest. Rebuild if any runtime or asset changes. `release.json` describes packaging verification and the open visual/performance gates; a successful build does not close those gates.

## Publish to GitHub Pages

The local checkout `../firesim-site` points to `https://github.com/cybrdelic/cybrdelic.github.io.git`. The public path is `/firesim/`. Inspect its branch, working tree and GitHub Pages configuration before publishing. Preserve unrelated site contents and copy only a validated package into the `firesim/` subtree. Do not copy test tools, screenshots or historical experiment folders.

Deploy the exact packaged bytes, including `release.json`, through the repository's configured Pages branch/workflow. Compare the published `release.json` and representative module/asset SHA-256 hashes against the package, then confirm that the HTML entry, stylesheets, both engine imports, source binaries, preview images and redirect alias return successful responses under `/firesim/`. Inspect a live presentation after deployment on the actual demonstration browser and GPU.

The package contains a large imported tree model. A first tree selection transfers its mesh and texture assets; ordinary fire does not need those assets to start. Keep tree experiments separate from the opening demo and disclose that their physical structural simulation is incomplete.

## Demonstration acceptance

| Concern | Acceptance evidence |
| --- | --- |
| Fire shape and internal detail | Original sigil, torch, campfire and dense fire have dark gaps, separated hot cores and evolving folds without a painted repeating texture. Compare a motion sequence with the approved offline reference at matched framing. |
| Smoke coupling | Smoke-only burst expands and rolls; burning smoke follows the gas flow through fuel shutoff and source dragging. Inspect it with neutral side/back lighting and at several angles. |
| Volume artifacts | Dense fire and oil bursts do not introduce crosshatching, tile boundaries, transient holes or transparent hollow cores. Inspect the full motion sequence, not one favorable still. |
| Fire illumination | Source-shaped fire illumination reaches gas and room receivers. Check off-center sources, multiple emitting regions, paused light changes and darkness after emission ends. |
| Sources and presets | Both engines expose matching source IDs and recover camera/fuel/light settings across engine switches, shared URLs and saved looks. Experimental geometry/effects retain visible status. |
| Objects | Inspect flame contact, finite fuel and char. Trees use the reviewed mesh; branch fracture/collapse and ember ignition are not presented as implemented. |
| Frame pacing | Record completed FPS, frame p95, simulation seconds per wall second, GPU stages and memory over sustained interaction, with the browser renderer/adapter named. Repeated presentation of an unchanged frame does not count as simulation throughput. |
| Device handling | Verify cold start, engine switch, restart, rapid preset selection, resize, background/foreground, back/forward restoration and recoverable device failure on the demonstration machine. |
| Mobile | Verify memory, interaction, adapter compatibility and sustained completed frames on physical mobile hardware before declaring support. Desktop native shader checks cannot close this gate. |
| Presentation | Open the intended shared URL, use Present, confirm responsive layout and keyboard recovery, and check that no development capture endpoint or experimental page opens during the planned demo. |

If a gate fails, record the failing scene, browser adapter, build fingerprint and a motion/performance capture in the development evidence. Keep the published documentation aligned with that evidence. Do not describe the candidate as having offline parity or guaranteed high FPS without a matching result.

## Copy and code audit

The AI Slop checker is a heuristic for filler, unfinished templates and repetition. Its source-tree scan also sees GLSL boilerplate and duplicated historical experiments; those are not proof of generated product copy. Review the flagged lines manually and scan the actual package after building. Input `placeholder` attributes are ordinary UI hints and should not be removed merely to reduce the score.

Keep demo descriptions concrete about the source, fuel, motion, lighting and test purpose. Product copy must not imply calibrated chemistry, physical tree collapse, mobile compatibility or measured realtime performance that the implementation and evidence do not establish. The source history stays in `development-history.md`; the release README describes current use and limits.
