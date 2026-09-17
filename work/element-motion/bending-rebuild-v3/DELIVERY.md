# Water / lightning revision 3

Published to the existing bending player. Rebuilt selects v3; Previous selects v2, the clips criticized in this turn. Previous deliverable MP4s remain intact. Earth, fire and air hashes are unchanged.

## What was wrong

- Water rendered coarse isolated simulation markers as similarly sized drops. No exposure motion blur made them look like frozen beads. Injected transverse strain also fragmented the sheet excessively.
- Lightning grew in a straight strip and was subsequently deformed around the trajectory. This imposed a curved-wire structure, regardless of the electrical growth model. There was no surrounding participating medium.

## Kept changes

- Fresh 96,288-particle APIC/FLIP water solve, h 0.015 versus 0.018, thicker resolved nozzle and lower transverse strain.
- Persistent sparse/bulk classification and broad-support anisotropic reconstruction. Corrected the isovalue solver's upper bound: the old hard bound was invalid with the larger kernel and inflated surfaces in an intermediate pilot. Final surface-volume error stayed below 0.381%.
- Single detached markers now represent 24 smaller lognormal fragments with volume-normalized radii; connected clusters remain larger drops. Persistent fragments inherit momentum, receive bounded capillary-scale dispersion, and integrate gravity and radius-dependent quadratic drag. This is an explicitly authored subgrid breakup closure, not directly resolved atomization.
- Analytical Cycles droplet spheres and velocity-driven motion blur with a 0.65-frame shutter. 96 samples at 2560 × 1440, delivered at 1920 × 1080.
- Lightning trees grow in the actual scene coordinates using successive guide electrodes. Thin aerosol advects through a 200 × 112 × 40 velocity field with buoyancy and FFT projection. Approximate channel illumination reveals that medium during and briefly after strokes.

## Rejected / corrected

- First world-space lightning pilot short-circuited the gesture and lost branching. Replaced with successive guide electrodes.
- Denser water and motion blur alone did not remove the bead appearance. An ablation hiding detached droplets identified their contribution; subgrid fragments replaced their coarse sphere representation.
- The inflated-surface pilot was stopped after its volume check failed. Those intermediate renders are not published.

## Evidence

- Baselines: `../bending-rebuild-v2/water-v2.mp4`, `../bending-rebuild-v2/lightning-v2.mp4`.
- Direct comparisons: `water-sequence-compare.jpg`, `lightning-final-compare.jpg`.
- Temporal review: `water-late-sequence.jpg`, `water-end-review.jpg`, lightning pilot sheets and individual exposure frames.
- Both final MP4s fully decoded: 120 frames, 4 seconds, 30 fps, 1080p. Black-background median corner checks: zero. See `validation.json`.
- All 953 water pressure solves converged. Fragment volume error below 1.7e-8 relative. Birth center-of-mass and momentum tests passed; small fragments lost forward speed faster. See `spray-invariants.json`.
- Final water rendering took approximately 396 seconds with streaming cache consumption. Lightning CPU render including aerosol took approximately 135 seconds. The primary water run's elapsed time includes a long preview gate.
- Browser: all five clips load at 1080p with no media errors. Previous/Rebuilt changes both sources and download links while preserving 2.4-second position. Group playback starts all five with observed drift below 0.013 seconds. Left on v3 at 1.245 seconds, black background, individual controls available.

## Remaining limits

The water's large sheet still has strong studio-light specular highlights. Spray size statistics are a subgrid closure and are not validated against measured atomization data. The haze is deliberately faint and soft; it is an authored aerosol, not combustion smoke created by clean lightning. Electrical growth remains a guided 2D graphics model, not full 3D plasma dynamics. These results should not be described as calibrated physical realism.

Electrical rendering reference: https://gamma-web.iacs.umd.edu/LIGHTNING/lightning.pdf

The preceding v2 reconstruction's generated `.mesh.gz` files were removed to free 316 MiB after confirming its previous videos, native particle states, reconstruction source, statistics, and rendered review frames were retained. They can be regenerated; no previous deliverable videos were removed.
