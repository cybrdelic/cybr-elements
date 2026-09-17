# Water and lightning rebuild

Published into the existing `/elements/motion/bending/` player. Both default to the rebuilt clip and offer Previous/Rebuilt comparison at the same playback position. Earth, fire, and air hashes match their previous delivery.

## Water

Fresh 120-frame quadratic APIC/FLIP run, 234 × 156 × 40 grid, h 0.018, 48,352 primary particles. Rotating elliptical source, authored near-nozzle turning force and gravity ramp, surface tension, projected pressure. All 744 pressure solves converged; no capacity loss or nonfinite particles. Global surface volume error stayed below 0.60%; this is not proof of local mass conservation. The floor is below the camera.

Anisotropic reconstructed surfaces and separate volume-carrying droplets, black world including transmitted rays, area-light reflections, IOR 1.333. Cycles OptiX 64 samples at 2560 × 1440, reduced to 1920 × 1080. The late sheet enters the lower-right corner; remaining background is black. Small-scale droplet/sheet fidelity remains limited by simulation resolution.

## Lightning

Three connected stochastic dielectric-breakdown trees grown in a 420 × 144 Laplace field, then mapped into the existing shared movement corridor. Hierarchical radiance, faint leader activity, strong channel strokes and repeat strokes. CPU 2× supersampled optical render. This is a guided 2D graphics model, not a 3D plasma solver; potential relaxation during growth is approximate.

Reference: https://gamma-web.iacs.umd.edu/LIGHTNING/lightning.pdf

## Review and verification

Compared before/after frames at 0.7, 1.4, and 2 seconds, reviewed water evolution through 3.97 seconds, and reviewed adjacent lightning exposures. Rejected the initial nearly branchless lightning and the subsequent uniformly bright electrical tree. Final hierarchy emphasizes the main channel and larger forks. Water preview lighting and mesh smoothing were revised before full rendering.

Both MP4s fully decoded to 120 frames, 4 seconds, 30 fps, 1920 × 1080. Validation details: `validation.json`. All five clips loaded without browser errors. Previous/Rebuilt switches retained 1.3-second position and updated downloads. Solo water and lightning each paused the other clips. Group playback and switching versions during group playback resumed all five with <0.03-second observed drift. The page is pure black with no horizontal overflow; water/air stages align. Browser left on both rebuilt versions, paused at 1.3 seconds.

Sources are the adjacent `bending-water-v2.mjs`, `bending-mesh-v2.py`, `bending-water-render-v2.py`, and `bending-lightning-v2.py`. `publish.py` validates and copies the rebuilt assets while preserving previous clips.
