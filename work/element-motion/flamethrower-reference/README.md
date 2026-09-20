# Flamethrower reference study

This study adapts the existing CYBR / ELEMENTS 3-D reactive-flow work to the visual target shown in the supplied reference: a sustained horizontal flame jet in a dark test scene, with a very bright compact core, turbulent orange envelope, soot, a steel target plate and restrained warm spill onto the floor.

The flame is **not** a sprite sheet, billboard, generated image, frame-fit reconstruction or video warp. The Python solver evolves velocity, fuel, oxygen, temperature, soot and reaction rate on a 3-D grid. It uses semi-Lagrangian velocity transport, limited MacCormack scalar transport, FFT pressure projection, combustion-driven expansion, buoyancy and vorticity confinement. The target interaction is a VFX-grade Brinkman/deflection approximation coupled into the flow; this is still a graphics model, not a calibrated engineering combustion model.

## Render

From `work/element-motion/`:

```powershell
python flamethrower-reference/flamethrower_reference.py
```

Default production settings are 224 × 96 × 128 simulation cells, four substeps per 30 fps output frame and 1920 × 1080 H.264 output. The default movie is written to:

```text
outputs/cybrdelic-type/elements/motion/subelements/flamethrower-reference.mp4
```

For a quicker 720p look-development pass:

```powershell
python flamethrower-reference/flamethrower_reference.py --pilot --size 160 72 104 --seconds 2.5
```

The solver requires CUDA and FFmpeg. On an 8 GiB GPU, start with the pilot command before raising the grid. The production script refuses to overwrite an existing movie so that a completed render cannot be silently replaced by a later experiment.

## What changed relative to the existing combustion study

The source is now a pressurized cylindrical jet instead of a moving/bending source. The fuel-rich core and oxygen-rich shear layer create a compact luminous reaction region near the nozzle rather than a uniform yellow blob. Downstream vorticity confinement and deterministic shear forcing sustain Kelvin–Helmholtz roll-up. A target-localized body force decelerates the jet and sends hot gas around the plate rather than simply clipping the volume against a screen-space mask.

Rendering also changed. Temperature controls a blackbody-like red/orange/yellow/white progression, soot contributes extinction and low-intensity scattering, the simulated volume's transmittance is composited over an analytic dark studio scene, and the target/floor illumination is driven from the rendered flame radiance. A very small deterministic dither is added before 8-bit encoding to reduce dark-gradient banding without visible grain.

## Verification

A run writes `work/element-motion/flamethrower-reference/run/report.json`. Verify the completed movie with:

```powershell
python flamethrower-reference/verify_flamethrower.py \
  --report flamethrower-reference/run/report.json
```

The verifier checks resolution, duration, frame count, finite solver metrics, jet reach and target interaction. Those checks are structural; visual review of the previews remains required because a numerically valid flame can still be visually weak.
