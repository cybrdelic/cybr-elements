# Bending remake — 2026-09-16

Five 4-second, 1920 × 1080, 30 fps videos on black. All use the original
`shared-trail.json` source gesture and fixed camera. Material motion after
emission differs: gas circulation, liquid inertia, rigid debris, or discharge.

Delivery: `outputs/cybrdelic-type/elements/motion/bending/` from the workspace root.

## Reproduce

From the workspace root, using Python with PyTorch CUDA, NumPy, Pillow, OpenCV,
and FFmpeg on PATH; Blender 4.5 is at the path configured in `render_all.py`:

```powershell
python work/element-motion/bending-rebuild/render_all.py
python work/element-motion/bending-lightning.py
python work/element-motion/bending-rebuild/validate.py
python work/element-motion/bending-rebuild/serve.py
```

The GPU queue runs one job at a time. Fire and air are resimulated at
576 × 112 × 336 and streamed directly to H.264. Earth and water retain JPEG
frames for restartable rendering. Existing JPEGs are skipped by full renders;
use a new frame directory after any material or geometry change.

The water pass deliberately reuses the accepted native FLIP surface cache in
`outputs/cybrdelic-type/elements/motion/water/cache/material/`. It is a render
upgrade, not a claim of new fluid dynamics. Earth uses Bullet with authored
source motion and reduced gravity during the bending beat. The dust layer is
the previous shared-path gas volume. Lightning is an art-directed branching
channel model, not a full electric-field or plasma solver.

## Review

`baseline.jpg` shows the earlier accepted material studies. `delivery-review.jpg`
shows the final encoded clips at three common times. `validation.json` records
all 120 decoded frames per video, timing, black-corner checks, checksums, and
frame brightness. The checks establish file integrity; visual review is still
required and is not replaced by those measurements.

Pilot review retained the original fire and air motion, corrected pale earth
shading, and increased lightning channel irregularity. No lava experiments or
earlier public clips were overwritten.
