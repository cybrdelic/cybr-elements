# Fuel and inspection controls

> Retained design/development record. Historical case results and release numbers below
> describe their original captures, not this consolidated browser build. Bulk diagnostic
> reports and iteration archives remain in the private recovery backup. See
> [current known issues](../KNOWN_ISSUES.md) and [validation scope](../VALIDATION.md).

Release candidate rc.12 adds neutral inspection lighting, visible CYBR artwork and finite floor fuel to the existing Fire Studio page. The controls work in Original and 3D volume.

## Use

| Control | Action |
| --- | --- |
| **Fully lit · neutral** | Select it under Lighting or in the Lighting library. Broad white lights and neutral fill reveal the room, source surfaces, cold fuel and smoke. |
| **Show sigil** | On a CYBR sigil source, show or hide the solid artwork beneath the flame. Its shape matches the existing CYBR artwork. In Volume, it follows the source pose. |
| **Drop fuel** | Select the tool, then click or drag on the floor inside the simulation area. Room is enabled so the placement surface is visible. |
| **Ignite fuel** | Apply a single heat pulse to existing deposits. The patch then releases fuel into normal combustion and burns down. |
| **Clear fuel** | Remove placed floor inventory and floor burn marks. The selected source, sigil visibility and existing gas/smoke remain in place. |
| **Restart** | Reset the simulation, surface state and placed fuel for a new run. |

Fuel is placed cold. It can stay unlit away from heat, or catch fire when nearby simulated flame heats it. Ignition consumes finite inventory; holding the cursor still does not create a permanent emitter. Dragging adds a continuous trail. Lighting and the Show sigil toggle do not ignite deposits.

Released fuel joins each engine's evolving chemistry and flow. Heat, combustion and soot come from that state, while consumed floor stock leaves char. Clear fuel does not remove gas already released into the scene, so flame and smoke can continue briefly afterward.

Airborne smoke gradually clears after combustion ends. Burning sources replenish it; Pause freezes its state. Floor and sigil char persist as material marks. Smoke-only sources keep floor stock unlit and do not consume it without combustion.

The visible sigil is solid artwork used to make the source readable. It is not a combustion obstacle, a physical structural model or an additional fuel reservoir. Engine-specific surface rendering remains different; the common controls do not make the two solvers identical.

## Short demonstration

1. Choose a source and **Fully lit · neutral**. Use Room and inspect the floor and source surfaces.
2. On a CYBR sigil, toggle **Show sigil** and inspect the front and an angled view.
3. Select **Drop fuel** and place a short trail on the floor. A cold patch remains unlit until heated.
4. Select **Ignite fuel** once. Watch the patch burn down, produce smoke and leave char.
5. Use **Clear fuel** to remove the deposits while the remaining gas drifts. Use **Restart** for a clean run, then repeat in the other engine.

## Recorded evidence

The compact release proof is in `RC12_FUEL_PROOF.json`. Development captures and raw reports stay under `work/`; they are not packaged runtime assets.

| Native check | Result and scope |
| --- | --- |
| Original cold stock | Actual assembled production shaders kept cold deposits unlit over 31 floor-update steps; cold deposition added no gas fuel, heat or soot. |
| Original finite ignition | With the normal source and brush disabled, the production gas reached maximum soot **0.03571** and reaction **1.94434** after a finite pulse. These are uncalibrated solver values. |
| Original stock accounting | Float32 surface inventory burned down with relative stock-plus-char residual **1.36 × 10⁻⁷**. This is surface bookkeeping, not a claim of calibrated whole-scene chemical mass conservation. |
| Volume combustion | Final Intel UHD and RTX 4060 replays executed 60 advancing frames plus three held views. Placed fuel produced soot with the normal source disabled. Intel's relative surface stock-plus-char residual was **8.17 × 10⁻⁹**; cold stock remained unlit. |
| Smoke lifetime | Production Volume WGSL gives identical stationary soot decay at 1, 2, 3 and 12 CFL substeps on Intel and RTX. Faint residue clears while fresh smoke remains. This is an isolated numerical gate, not a whole-plume motion test. |
| Volume sigil geometry | Actual production guide code executed **756 rays per adapter** with zero hit-classification disagreements at several angles. Held-state views were inspected for contour readability and edge thickness. |

Raw reproducibility reports include `work/fuel-ground-qa/original-smoke-proof/native-report.json`, `work/adaptive-volume-qa/rc12-fuel-smoke-{fire,pool}-final/`, the earlier `work/adaptive-volume-qa/rc12-fuel-release-cold/`, and `work/fuel-studio-qa/guide-summary.json` with `GUIDE-RESULTS.md`. Smoke lifetime reports are `work/fuel-studio-qa/smoke-lifecycle-{integrated,discrete}.json`.

The package runs 19 runtime fixture runners, including `fuel-ground.test.mjs`, `floor-fuel.test.mjs`, `sigil-guide.test.mjs`, `scene-light-presets.test.mjs`, `smoke-lifecycle.test.mjs` and `original-smoke.test.mjs`. They verify input/state/resource contracts separately from the native shader and image checks. Volume accumulates its existing soot decay over a fixed simulation cadence so small CFL steps cannot round away every loss; both engines clear negligible half-float residue. This adds no rendering pass or volume field.

Native checks were used because automatic approval review blocked browser automation in this session. They do not establish actual browser interaction, sustained frame pacing, mobile compatibility or offline film parity. Those remain demonstration acceptance gates in [current known issues](../KNOWN_ISSUES.md).
