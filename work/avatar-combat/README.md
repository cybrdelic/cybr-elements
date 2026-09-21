# CYBR ELEMENTS — Avatar Combat Bridge

Trajectory-driven elemental assets for the `cybr-scenes/scenes/mythic-elemental-combat` sequence.

This bridge does not replace the existing high-resolution CYBR ELEMENTS sigil solvers. It exposes the same core ideas—advected scalar fields, reconstructed moving surfaces, rigid fragments, and branching electrical channels—to an arbitrary animated actor trajectory so the character and effects share one world-space coordinate system.

## Inputs

`trajectory.json` is emitted by the Blender animation bake in CYBR SCENES. Every frame contains:

- root, left/right hand, axe head and axe tail world positions
- move name and normalized move phase
- frame/time metadata

`element_cues.json` defines the active element windows.

## Outputs

- `fire/density_####.cgrid`: scalar density fields accepted directly by CYBR LIGHT's native volume grid path.
- `fire/core_####.json`: hot-core samples for emissive lighting/geometry.
- `air/density_####.cgrid`: storm wake density.
- `frost/frame_####.obj`: moving ice shards.
- `water/frame_####.obj`: swept liquid ribbons/droplets.
- `earth/frame_####.obj`: impact/fracture chunks.
- `lightning/frame_####.json`: deterministic branching discharge segments.
- `manifest.json`: complete frame-to-asset mapping and bounds.

The cgrid writer intentionally matches CYBR LIGHT's native dense-grid contract: three little-endian int32 dimensions followed by X-fastest float32 density samples.

## Run

```bash
python work/avatar-combat/render_avatar_elements.py \
  --trajectory ../cybr-scenes/scenes/mythic-elemental-combat/build/trajectory.json \
  --cues ../cybr-scenes/scenes/mythic-elemental-combat/build/element_cues.json \
  --out ../cybr-scenes/scenes/mythic-elemental-combat/build/elements
```

Use `--grid 80` or higher for denser fields. The default is intentionally moderate so a CPU-only validation pass is practical. The production CYBR ELEMENTS solvers remain the higher-fidelity path for final fire/water hero shots.
