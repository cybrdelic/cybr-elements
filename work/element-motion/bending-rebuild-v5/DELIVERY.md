# Bending v5 — controlled comparison

Player: http://127.0.0.1:8767/elements/motion/bending/

Five independent Previous / Trial selectors preserve each clip's playback position and update its download. Every original remains on disk. Source, inputs and original media are frozen in `baseline/`; its manifest contains 35 original-file SHA-256 values. The public player is updated only after all five candidate videos pass decoding checks.

| Element | Decision | Change | Remaining limitation |
| --- | --- | --- | --- |
| Earth | Trial selected | Sharper fracture faces, gentler small bump, varying roughness, adjusted light and less obscuring dust. Same 660 rigid-body birth states, colliders and camera. | A restrained surface improvement; the broad throw remains the approved version. |
| Fire | Original selected | A complete extinction/emission trial is available. Simulation step is unchanged. | Comparison showed too little gain to replace the original. |
| Air | Trial selected | Revised extinction and side illumination reveal wisps and overlapping curls. Simulation step is unchanged. | Still the same art-directed gas motion. |
| Water | Trial selected | Area-preserving nozzle variation and varying axial momentum; energy/support-loss criteria govern secondary breakup. Same native FLIP/APIC solver, perspective camera, optical material and light rig. | Still reads as a controlled jet. Some late spray clumping is visible. This is not a claim of photorealism or resolved atomization. |
| Lightning | Trial selected | Short moving 3D discharge regions, spatially advancing leaders and repeated strokes on established channels. | Guided Laplacian growth and approximate aerosol illumination, not plasma electrodynamics. |

The shared broad gesture, four-second duration, 30 fps delivery and pure black camera backdrop are retained. Water and lightning differ intentionally in local motion. Earth/fire/air dynamics were preserved.

## Evidence

- `earth-pilot-compare.jpg`, `earth-close-review.jpg`, `earth-sequence.jpg`
- `fire-pilot-compare.jpg`, `fire-sequence.jpg`
- `air-pilot-compare.jpg`, `air-sequence.jpg`
- `water-full-compare.jpg`, `water-peak-review.jpg`, `water-release-72.jpg`, `water-release-90.jpg`, `water-sequence.jpg`
- `lightning-pilot.jpg`, `lightning-full-compare.jpg`, `lightning-sequence.jpg`
- Per-element `*-validation.json`: complete 120-frame decode, metadata, SHA-256 and per-frame measurements.
- `water-simulation-validation.json`: 120 finite primary states; no failed pressure solves; maximum relative pressure residual 9.474e-6; no nominal source-volume imbalance; reconstructed volume error below 0.5%; spray volume error below 5.58e-8.
- `gas-source-verification.json`: unchanged fire/air simulation functions.
- `spray-invariants.json`: coherent parcels remain intact; energetic breakup conserves represented volume.
- `publication.json`: exact published video hashes and selected versions.
- `browser-validation.json`: five solo controls, all ten versions, preserved time/downloads, synchronized completion and no browser errors. A completed synchronized run now remains paused when changing a version.

The earth background check initially flagged frame 89 because a stone crosses the upper-right sample. Visual review confirmed the object, with black background remaining around it. Validation reports foreground crossings separately from background values.

One early lightning render failed during overlapping jobs. It was discarded. Rendering was serialized and its color buffers changed to float32; ffmpeg is limited to two threads. The failed log is retained as `lightning-full-failed.log`.

## Reproduce

Use Python 3.12 with the package versions in `environment.json`, Node with the existing native FLIP vendor source, and Blender 4.5 / Cycles OptiX. No new external dependencies were installed.

1. Gas: run `bending-fire-v5.py` or `bending-air-v5.py` with `--size 576 112 336 --fps 30 --substeps 6`. Their frame-45 review gates use `continue-fire` / `continue-air` files in this directory.
2. Earth: Blender background mode, `--factory-startup --python bending-earth-v5.py -- --full`.
3. Water: `node bending-water-v5.mjs --ungated`; then run `bending-mesh-v5.py --full` alongside Blender `--factory-startup --python bending-water-render-v5.py -- --full`. Meshing is bounded to five pending frames and processed meshes are removed. Start a fresh output directory or remove only reproducible frame intermediates before a full rerun; do not mix cold-start pilot frames with the full spray history.
4. Lightning: `python bending-lightning-v5.py --full`, after other heavy jobs finish.
5. Run `verify-water.py`, `encode-and-audit.py`, and `review-lightning.py`. Inspect the resulting images and actual player controls. `--audit-only` checks an existing video without re-encoding.
6. `selection.json` controls per-element defaults. `publish-v5.py` asserts complete validated files and unchanged originals before copying media and rebuilding the player.

Do not run the gas or Cycles renderers simultaneously. All outputs are locally reproducible and the baseline can be restored independently for each element.
