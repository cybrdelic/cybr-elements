# Flamethrower reference study

This study adapts the existing CYBR / ELEMENTS 3-D reactive-flow work to the visual target shown in the supplied reference: a sustained horizontal flame jet in a dark test scene, with a very bright compact core, turbulent orange envelope, soot, a steel target plate and restrained warm spill onto the floor.

The flame is **not** a sprite sheet, billboard, generated image, frame-fit reconstruction or video warp. The Python solver evolves velocity, fuel, oxygen, temperature, soot and reaction rate on a 3-D grid. It uses semi-Lagrangian velocity transport, limited MacCormack scalar transport, FFT pressure projection, combustion-driven expansion, buoyancy and vorticity confinement. The target interaction is a VFX-grade Brinkman/deflection approximation coupled into the flow; this is still a graphics model, not a calibrated engineering combustion model.

## Render

From `work/element-motion/`:

```powershell
python flamethrower-reference/flamethrower_reference.py
```

Default production settings are now 384 × 112 × 192 simulation cells, five substeps per 30 fps output frame and 1920 × 1080 H.264 output. The default movie is written to:

```text
outputs/cybrdelic-type/elements/motion/subelements/flamethrower-reference.mp4
```

For a quicker 720p look-development pass:

```powershell
python flamethrower-reference/flamethrower_reference.py --pilot --size 160 72 104 --seconds 2.5
```

The solver requires CUDA and FFmpeg. On an 8 GiB GPU, start with the pilot command before raising the grid. The production script refuses to overwrite an existing movie so that a completed render cannot be silently replaced by a later experiment.

## What changed relative to the existing combustion study

The source is now a pressurized cylindrical jet instead of a moving/bending source. The fuel-rich core and annular ignition layer create a compact luminous reaction region near the nozzle. Downstream structure comes primarily from inlet shear plus the same resolved vorticity-confinement family as the accepted sigil fire. A target-localized body force decelerates the jet and sends hot gas around the plate rather than simply clipping the rendered image.

The September 20 revision deliberately removes the separate flamethrower material approximation. Chemistry/cooling, temperature-to-hue, reaction emission, soot extinction/scattering, viscosity, vorticity confinement, optical glow and tone mapping are brought back into parity with `sigil_02_fire_v2.py`. The scene is composited behind that volume response rather than replacing it. The intent is that changing the source geometry from a sigil sheet to a nozzle does **not** downgrade the fire material.

## Verification

A run writes `work/element-motion/flamethrower-reference/run/report.json`. Verify the completed movie with:

```powershell
python flamethrower-reference/verify_flamethrower.py \
  --report flamethrower-reference/run/report.json
```

The verifier checks resolution, duration, frame count, finite solver metrics, jet reach and target interaction. Those checks are structural; visual review of the previews remains required because a numerically valid flame can still be visually weak.
