# Fire powers

Six shared sources are available under **Source → Powers** and **Library → Powers** in Original, 3D Volume and Sparse volume. Switching simulations keeps the selected power, strength and aim. Each engine retains its own camera framing.

| Power | Live behavior |
| --- | --- |
| Radial blast | A finite expanding ring injects outward momentum and burning gas for 0.45 seconds. Released flame and soot keep evolving. |
| Fireball | A compact charge follows an aimed arc for up to 1.15 seconds, leaving combustion in the surrounding flow. Its source center is clamped above the floor. |
| Fire rain | Nine staggered falling packets feed the gas flow. Move the rain field with the cursor; stopping it ends fresh packets. |
| Fire tornado | A twisting fuel ribbon and a bounded circulation force drive a rising vortex. Stopping it removes the fresh fuel and imposed circulation. |
| Fire floor trail | Dragging deposits and ignites finite oil fuel on the floor. Existing patches burn down after the cursor leaves. |
| Combustion bomb | A small charge burns for 1.2 seconds, followed by a 0.35-second outward burst. It leaves an evolving flame and smoke cloud. |

## Controls

- Select the **Fire** interaction tool. Click to cast a finite power; drag to move rain, tornado or trail placement. Floor powers require a floor point inside the simulation area, and selecting them makes the room visible.
- **Cast power**, **Launch fireball** or **Charge bomb** repeats the selected effect at its current origin. **B** also casts. Recasting adds to the existing gas rather than clearing the scene.
- **Power strength** ranges from 25% to 200%. Fireball **Heading** and **Elevation** set its launch direction. Finite powers capture settings at launch, so changing them affects the next cast. Continuous powers follow updated strength.
- **Pause** or **Space** freezes simulation time, including the bomb fuse and source animation. Casting resumes the simulation.
- **Stop power / Stop casting** ends fresh injection or placement. Existing gas, soot and deposited burning fuel continue evolving. **Clear fuel** removes floor inventory; **Restart** resets the scene.
- Shift/right-drag pans and the wheel zooms. Shared links and saved looks retain strength and aim alongside lighting and camera settings.

## Implementation and limits

[fire-powers.js](../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-powers.js) supplies shared analytic support, source motion and momentum in WGSL and GLSL. These sources feed each engine's existing GPU gas, combustion, soot and lighting paths. They use no prerecorded flames or animation frames and do not lower the simulation or rendering resolution.

Original uses its layered flow representation; Volume uses its full 3D flow. Sparse uses Volume's pooled chemistry with global flow and pressure, and may fall back to dense storage. Matching source IDs do not imply identical images across engines.

The scene has a bounded simulation domain. Effects near its edges can leave that domain. Fireball motion and tornado circulation are authored supernatural controls rather than rigid-body or weather simulations. Rain supplies gas packets, not persistent liquid floor pools. Floor trails use the existing finite fuel inventory; remaining still does not continuously refill a patch.

## Wood startup correction

The reported Volume startup error came from quad derivatives hidden inside wood helpers called from varying hit/material branches. Mesh cap and leaf discard could also precede derivative-dependent sampling.

Shared WGSL wood helpers are now pure. Mesh derivatives and implicit samples execute before varying branches or discard. Conditional ray hits receive analytic perspective footprints derived from ray differentials captured at fragment entry. Original keeps its GLSL material API. No derivative diagnostic is disabled.

## Verification status

The release passes **237 CPU tests**, including source pairing, saved aim, conditional controls, queued casting, finite inventory, lifecycle and shader-uniformity checks. The packaged checks execute 35 runtime runners against the shipped files.

Official Dawn/Tint with its null backend accepts **145 unique WGSL modules / 172 generated variants**, with zero errors or warnings; a deliberately divergent derivative fixture is rejected. Native Original passes 13 gates and compiles 61 unique production GLSL programs. Final Volume frame, field and timing results are recorded in [RC15_POWERS_PROOF.json](RC15_POWERS_PROOF.json). These native and compiler checks do not establish browser FPS or mobile performance. See the [release report](RELEASE.md) for conditions and remaining gates.
