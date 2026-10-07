# Sparse volume

> Retained design/development record. Historical case results and release numbers below
> describe their original captures, not this consolidated browser build. Bulk diagnostic
> reports and iteration archives remain in the private recovery backup. See
> [current known issues](../KNOWN_ISSUES.md) and [validation scope](../VALIDATION.md).

Candidate rc.13 adds **Sparse volume · experimental** beside Original and 3D volume in the same Simulation select. It uses the Volume engine and source catalog, with a fixed brick atlas for heat, fuel, soot and oxygen depletion. It is an experimental storage option with open performance and quality gates.

## Use

Choose Sparse volume, then select a source from the existing picker or library. Lighting, camera, smoke inspection, color, embers, Room and Show sigil use the same controls as standard 3D volume. Fully lit reveals source surfaces, cold smoke and floor fuel. Drop fuel, Ignite fuel and Clear fuel retain their finite-inventory behavior.

Shared URLs and saved looks retain the selected mode with its source, lighting and camera settings. Placed fuel and evolving gas are transient simulation state; they are not serialized into a saved look. Restart resets the simulation and sparse allocator.

A shared inspection URL uses `?simulation=sparse&firePreset=sigil-cybr&room=1&lighting=fully-lit&guide=1`. Older `simulation=volume&bricks=1` links remain accepted and are rewritten to the canonical sparse mode.

## What changes

| Component | Sparse selection |
| --- | --- |
| Flow and pressure | Global 128³ MAC velocity and the existing multilevel pressure solve. No coarse/fine flow or pressure-work experiment is enabled by this selection. |
| Chemistry | The existing 256³ voxel spacing, stored in fixed 16³ atlas pages. Active 8³ bricks still determine transport and reaction work. |
| Rendering | The current volume, source and room rendering. Pool-aware consumers read the same evolving chemistry with checked page ownership. |
| Lighting | Reference lighting remains selected. This mode does not enable the separate lighting-work or receiver experiments. |
| Capacity | The current field migrates to dense storage if allocation or a safety preflight fails. Dense mode stays active until Restart. |

The global flow includes surrounding air outside visible smoke. Sparse chemistry storage does not make the pressure solve or the entire scene sparse. Voxel spacing, ray detail and reaction coefficients are unchanged.

## Memory and acceptance

The pool retains **384 MiB** of dense chemistry backing for fallback and adds a **96 MiB** atlas. Chemistry storage therefore totals **480 MiB**, before page tables, velocity, pressure, lighting, source geometry and other resources. It does not establish lower memory use or mobile support.

Earlier native pool trials were slower than the dense reference on matched RTX host-command replays. Atlas filtering also differed from dense hardware filtering and exceeded a provisional moving-scene temperature gate. Dense fallback was bit-identical in those fixtures; atlas transport was not. The historical results and rejected trials remain in [ADAPTIVE_SOLVER.md](ADAPTIVE_SOLVER.md).

## rc.13 checks

The 150 CPU tests pass, including the actual shell's three-mode transitions, saved/imported looks, canonical links, explicit library filters, camera continuity, recovery, tool state and the app's authoritative solver configuration. The package runs three new mode runners with the existing 19 runtime runners.

Four short native command replays compare dense and sparse configurations on Intel UHD and RTX 4060 Laptop at 768×432, with the lit CYBR sigil, floor fuel and ignition. Each covers 60 simulation frames (one simulated second) and three additional camera views. All shaders, CFL checks and finite field checks pass; pooled snapshots contain no stale mappings. In this scene, sparse reaches dense fallback at frame 32 on Intel and frame 30 on RTX, then remains dense. This limits its usefulness for larger fires with the current pool.

| GPU | Dense median GPU cost | Sparse median GPU cost |
| --- | ---: | ---: |
| Intel UHD | 24.09 ms | 34.70 ms |
| RTX 4060 Laptop | 11.49 ms | 5.29 ms |

These are one-run native timestamps over matched frames 6–29, while chemistry is still sparse. The costs include submitted compute and drawing work; readback, presentation, browser scheduling and repeated sustained performance are not certified. Mixed costs and early fallback do not establish a general speedup. The compact evidence and exact recording/report hashes are in `RC13_SPARSE_PROOF.json`.

Lossless atlas transport, offline parity and motion quality remain open. Native checks and CPU fixtures do not certify physical mobile compatibility or the demonstration browser. See [current known issues](../KNOWN_ISSUES.md) for the remaining gates and [FUEL_AND_INSPECTION.md](FUEL_AND_INSPECTION.md) for the shared inspection controls.
