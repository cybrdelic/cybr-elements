# CYBRDELIC Fire Studio


## Experimental Original snapshot — 2026-10-07

The default Original engine includes the tested upper-boundary and source-age
follow-up `5ce5a7f80e52e99fb20db751aa6ed9d9e17f2034`. The former 7.8-second
boundary rejection was corrected in a bounded Sigil check advancing through
8.4333 seconds. Native Stop disabled both sources; Restart reset the origin
and restored the first-step age/clock to 1/30 second. Acceptance safeguards,
transport, rendering and heat budgets remain unchanged.

This remains experimental. Sustained ignition is unproved: bounded native
planes had zero sampled soot and temperature below the fresh ignition threshold.
Physical advancement was about 0.26–0.51 native seconds per wall second with
private observers; long sessions, mobile behavior, Fireball and Sooty are not
certified by these checks. Thermal/source delivery, refined flow and performance
remain known limits. No thermal tuning accompanies publication.

The previous v5 Original remains selectable through `?runtime=v5`. The v6
candidate and archive-backed Site v6 are preserved independently; saved Site v5
also remains available for whole-site rollback. Volume and Sparse retain their
existing implementations. See [experimental snapshot validation](https://github.com/cybrdelic/cybr-elements/blob/codex/fire-experimental-current-20261007/docs/EXPERIMENTAL_ORIGINAL.md) for scope
and checks.

Interactive fire and smoke, finite sources, lighting and camera controls. The GPU evolves and renders gas live. This is the current Fire workspace in CYBR ELEMENTS; the future multi-element Element Studio remains a roadmap.

## Run locally

From the repository root:

```sh
python -m http.server 8776 --bind 127.0.0.1 --directory outputs/cybrdelic-type
```

Open http://127.0.0.1:8776/elements/motion/bending/sigils/02/fire-live/. Original uses WebGL 2. Volume and experimental Sparse use WebGPU. Localhost or HTTPS is required.

## Use

- **Scene:** choose Original, **3D volume · experimental** or **Sparse volume · experimental**, then a source, fuel and color. The two Volume modes share their source catalog. Click to place fire and drag to move its source. Stop fuel ends an emitter. On a solid object, Stop ignition removes the starter; hot material can keep burning. Restart replenishes the source.
- **Powers:** Source or Library → Powers contains 24 abilities, including fireballs, whips, meteors, walls and a flame serpent. Click to cast finite powers. Fireball, Heat seeker, Solar lance and Cinder scatter support hold to charge, drag to aim and release to cast. **Cast** or **B** runs the complete sequence. Four finite casts keep separate clocks and destinations. Rain, tornado, floor trail and breath are the four sustained powers; drag to move their active source and Stop power ends fresh fuel. Released gas keeps evolving. Floor trails consume finite deposited oil.
- **Power aim:** strength, heading and elevation apply to the next finite cast; directional floor attacks use heading. Sustained power settings remain live. Pause or Space freezes charge, source motion and recovery. Saved looks and shared links retain the selected ability, strength and aim across simulations.
- **Camera:** scroll to zoom; Shift-drag or right-drag pans. The controls also provide an angle slider and camera reset. Touch interaction and keyboard controls are described beside the scene.
- **Library:** choose a complete demo scene, an individual source, a lighting rig, an inspection test or a saved look. Tests use temporary lighting and camera settings.
- **Lighting:** adjust external light sources and approximate room bounce while the fire remains visible. Fire itself illuminates the gas, room and source props.
- **Fully lit:** choose **Fully lit · neutral** in Lighting or the library to inspect the room, source surfaces and cold smoke with broad white lights.
- **Show sigil:** on a CYBR sigil source, show or hide the artwork overlay. The wooden CYBR source has its own solid, combustible geometry; hiding the overlay does not remove that wood.
- **Wood time:** set material ageing from 1× to 24×; the default is 12×. Drying, pyrolysis and damage accelerate while fluid flow and falling pieces keep real time. Stop ignition ends the starter; it does not instantly cool hot wood. Restart restores the material.
- **Drop fuel:** in either engine, select this tool and click or drag on the floor inside the simulation area. It enables Room and places finite, unlit patches. Nearby flame can ignite them; **Ignite fuel** applies one ignition pulse. **Clear fuel** removes the patches and floor burn marks while existing gas and smoke continue. **Restart** resets the simulation and placed fuel.
- **Smoke clearance:** after fuel stops, leave the simulation playing so smoke can rise, spread and gradually clear. A burning source continually replenishes smoke. Pause freezes it; char and floor burn marks remain until cleared or restarted. Smoke-only sources keep placed fuel unlit; choose a fire source to ignite it.
- **Present:** hide editing controls for a demo. Escape returns to the workspace.

The [fuel and inspection guide](../../../../../../../../docs/fire-studio/FUEL_AND_INSPECTION.md) describes these controls and their verification scope.

Sources carry stable IDs across both engines. Each engine implements them using its own flow and source model. Prototype object and burst studies are identified as experiments; the Include experiments control exposes them in the Source picker. Saved looks use local browser storage and version 1 JSON import/export.

Sparse volume keeps the same lighting, camera, smoke, Show sigil and floor-fuel controls. Shared URLs and saved looks retain the selected mode. Placed fuel and evolving gas are transient simulation state, not saved-look contents. If sparse storage reaches its capacity or safety limit, chemistry continues in dense storage until Restart.

A sparse inspection entry is `?simulation=sparse&firePreset=sigil-cybr&room=1&lighting=fully-lit&guide=1`. Older `simulation=volume&bricks=1` links select the same mode and are rewritten to the canonical sparse URL.

Repeatable entries include `?scene=demo-sigil&present=1`, `?scene=demo-campfire`, `?scene=demo-torch`, `?scene=demo-ring`, `?scene=demo-bonfire` and `?scene=demo-smoke`. The last two select 3D volume. The older `pyro-gpu/` URL redirects into this same page and preserves its query settings.

## Graphics requirements and scope

Original requires WebGL 2, floating point render targets and linear filtering of float textures. Both Volume modes require a working WebGPU adapter with sufficient texture and buffer limits. Sparse volume retains the **384 MiB** dense chemistry backing and adds a **96 MiB** chemistry atlas; other GPU resources add to that total. This is not a mobile memory reduction. The page provides recovery controls when the selected engine cannot start. A WebGPU API being present does not establish that its adapter can submit frames.

Both engines transport heat, fuel and soot in evolving flow. Flame emission and extinction share their state with fire illumination. Original uses an atlas volume with a coarse pressure solve; 3D volume uses a dense MAC velocity field, multilevel pressure projection and a separate chemistry grid. These are visual combustion models with accelerated, uncalibrated coefficients. Creative colors are art direction.

Volume's optional precise receiver lighting computes incident illumination only where soot can receive it. Every positive-soot interpolation footprint remains covered, while camera and shadow support keep their existing full halo. The light texture, ray samples and lighting formulas are unchanged; inactive light texels are cleared on every lighting refresh. This is a lighting optimization, not a reduction in simulation detail.

The tree, logs, timber house and wooden CYBR sigil share finite virgin wood, moisture, char, surface/core heat, grain-dependent conduction and structural damage. The reviewed CYBR tree retains every original triangle. Weakened beam partitions detach under bending, axial and shear loads; capped faces expose continuous rest-space grain. Original uses a projected material inventory; Volume uses a 64³ material proxy. This reduced beam model does not resolve arbitrary fracture, redundant joints, buckling or fragment-to-fragment contact. Dropped wood uses the same chemistry as a finite floor patch, without rigid lumber pieces. Wood time accelerates drying, conversion and damage separately from gas and falling pieces. Volume embers are one-way flow tracers; they do not subtract wood mass or ignite new fuel. External illumination and room bounce are approximations, not converged path tracing or calibrated global illumination.

## Code map

| Module | Responsibility |
| --- | --- |
| `studio.js`, `studio-location.js`, `simulation-modes.js` | Same-page mode/preset transitions, shared state and URLs |
| `studio-ui.js`, `studio.css` | Workspace, presentation and recovery controls |
| `runtime-loader.js`, `runtime-scope.js` | Lazy engine loading and animation/listener cleanup |
| `demo-presets.js`, `source-picker.js`, `preset-pairs.js` | Demo collection and shared source selection |
| `look-storage.js`, `inspection-state.js` | Saved looks and temporary inspection settings |
| `scene-lights.js`, `pyro-gpu/library.js` | Lighting catalog and library actions |
| `fire.js` | Original WebGL lifecycle, stepping and interaction |
| `original-shaders.js` | Pure Original shader assembly; shared gas chemistry and optics |
| `reduced-chemistry.js`, `shader-language.js` | Gas units and finite-dose helpers compiled for both engines |
| `fire-power-definitions.js`, `fire-abilities.js`, `fire-powers.js`, `fire-ability-motions.js` | Shared 24-ability timing, four-cast pool, bounded fuel/momentum and source support |
| `pyro-gpu/app.js`, `solver.js` | Volume controls, GPU scheduling and diagnostics |
| `pyro-gpu/shaders.js`, `renderer.js` | Volume transport, combustion and volume/room rendering |
| `pyro-gpu/lighting-work.js` | Optional precise incident-light receiver support and generic work queue |
| `pyro-gpu/adaptive-flow.js` | Optional global coarse/local fine flow and sticky dense fallback |
| `pyro-gpu/adaptive-pressure.js` | Optional exact fine smoothing work lists; pressure remains global |
| `pyro-gpu/brick-pool.js`, `pooled-coupling.js` | Optional fixed chemistry pool, generation-safe sampling, migration and shared consumers |
| `pyro-gpu/objects.js`, `forest-mesh.js` | Surface fuel and imported tree geometry |
| `wood-thermo.js`, `wood-material.js` | Shared finite material chemistry and rest-space wood appearance |
| `wood-state-gl.js`, `wood-structure-gl.js`, `wood-structure.js` | Material inventory, beam loading, failure and rigid fragment poses |
| `pyro-gpu/wood-flux.js`, `wood-collision.js` | Finite exterior fuel transfer and moving fragment collision support |
| `fuel-ground.js`, `ground-fuel-gl.js`, `pyro-gpu/floor-fuel.js` | Shared floor input, finite inventory, ignition, char and floor material |
| `pyro-gpu/sigil-guide.js` | Visible CYBR artwork using the native source contour |

## Source and flame ownership

Power definitions and choreography choose where and when fuel and momentum enter the gas. They do not select another optical model. Original uses one emission/extinction model for ordinary sources and powers, shared with its room lighting. Volume retains its own volumetric renderer; this is not a claim that both renderer implementations are identical.

`original-shaders.js` owns shader assembly and receives geometry/material inputs explicitly. The WebGL runtime owns GPU resources and interaction. Native shader probes call that factory through `assemble_sources()` rather than extracting template literals from runtime text.

Ordinary and power injection still differ in how their releases are authored: a stationary burner has continuous nozzle feed, while a cast supplies a finite moving dose. Shared finite-dose heat, oxygen displacement and momentum definitions live in `reduced-chemistry.js`. The older duplicate fireball trajectory, power-only optical selector, and unused direction/strength/origin uniforms have been removed.

## Experiments and known issues

Sparse retains dense backing and has no established general speed or quality advantage. Optional adaptive flow, pooled chemistry, pressure work lists and precise receivers remain experiments. Standard Volume uses the current cached pressure-source path; experimental coarse/fine flow can fall back to the dense reference. Historical native timings do not measure this consolidated browser build.

Thermal/source behavior, reaction-front facets, smooth or overbright power heads, smoke-heavy performance and mobile acceptance remain limits. See [known issues](../../../../../../../../docs/KNOWN_ISSUES.md) and [validation](../../../../../../../../docs/VALIDATION.md). CPU fixtures do not certify live motion or sustained frame rate.
