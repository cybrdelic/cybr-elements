# Elemental sigils

52 silent 1080p/30fps films: the 26 materials in the dynamics gallery, on both
unchanged approved CYBRDELIC ligatures. The source artwork is read from the same
`brand-fire-01.npz` and `brand-fire-02.npz` files used by the earlier fire intros.

The source writes over approximately 6.83 seconds. The camera moves from a close
tracking view to the full mark between 5.55 and 7.45 seconds. Bending support or
gas supply remains active until 11 seconds; the 15-second films then show release.
Camera backgrounds remain black, and there is no white typography overlay.

## Methods and limits

- Surfaces reuse the material recipes in the dynamics renderer. Their new source
  geometry follows the original silhouette and arrival field. Supported damped
  motion and gravity provide a common retargeting rig. This is not a new FLIP or
  MPM bake for every font.
- Glass, ice and crystal use independently moving source fragments at release.
  The fracture geometry is authored; there is no new stress-fracture solve.
- Plants use the same scanned foliage on connected source contours. Healing uses
  the plant repair interpretation already present in the material studies.
- Gas uses the existing 3D gas-line transport, fuel reaction, reservoir release
  and cooling solver. Blue fire, combustion, steam and smoke use separate optical
  responses. Steam is an effective scattering visualization, not a new multiphase
  water condensation solve. Combustion includes an authored luminosity accent.
- Flight uses fine exposed wake tracers. The trial that rendered it as a generic
  gas cloud was rejected.
- Sound and pressure solve a damped planar wave equation in an authored sigil
  waveguide, then release outward. They and heat use amplified optical diagnostics.
- Energy, spirit, projection and electrical discharges remain authored VFX.

The earlier material realism limitations still apply. This task retargets those
materials onto the original brand marks; it does not certify them as photoreal.

## Verification and reproduction

`prepare.py` records source hashes and builds the sigil geometry. `pilot.py`
requires freshly rendered frames. `render.py` journals completed frames against
a configuration hash, allowing an interrupted render to resume safely. Exactly
settled geometry may reuse a rendered hold frame; it is not motion interpolation.

`batch.py` bounds the number of renderers and reduces concurrency under memory
pressure. `encode.py` checks all 450 source frames, black corners, visible content,
and the resulting video dimensions, frame count and duration. `review.py` decodes
the actual MP4s for visual inspection. `publish.py` requires reviews bound to the
current video hashes and publishes a separate gallery without replacing originals.

The Blender render jobs use `render.py --kind MATERIAL --variant 01|02` after
Blender's `--` separator. `--frames 90,240,360` selects a preview; `--resume` reuses
only completed frames with the same configuration. `gas.py` and `acoustics.py`
run with workspace Python and take `--variant 01|02`.
