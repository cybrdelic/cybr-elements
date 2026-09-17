# CYBRDELIC material motion review

Status: **none of these tests is approved for a full sigil render. The requested finished intros remain incomplete.**

The existing site and approved Study 06 sigils 01/02 are preserved. The new review page is `/elements/motion/`; it is linked from the existing elements gallery. No replacement typography or logo silhouette was introduced.

| Element | Kept | Remaining visible failure |
|---|---|---|
| Fire | 3D advected combustion, forward injected momentum, resolved wake shear, finite fuel and natural reaction/cooling | Bright leading tip is still too smooth; no convincing full-word persistence test yet |
| Water | Original FLIP solver and original offline renderer; finer 0.024 m grid, finite opposing jets, earlier collision and continuous sheet, no added spray | Granular/high-contrast surface, especially during breakup; basin test does not establish an airborne sigil hold |
| Air | 3D pulsed jet, emergent rolling tracer wake, free transport after source shuts off | Compact smoky puff, insufficient sweeping motion and depth presentation for the intended brand treatment |
| Earth | Volumetric convex fracture bodies, Bullet contacts, corrected initial floor penetration, realistic mass from volume, breakable fixed bonds, freely released impactor | Most of the mass remains bonded; fracture hierarchy is too weak. Neutral clay render is not a finished stone look |

## Experiments rejected

- Smooth initial fire and air tubes: failed before full wordmark work.
- Earth bonds failing before impact: rejected; actual geometry extended 0.0268 m below the floor. Corrected initial placement and checked pair distances before collision.
- Overstrong earth bonds: held together through impact. The latest lower bond strength still releases too little material.
- Water surface-normal smoothing: visually unconvincing; not used in the final test video. Native reconstruction retained.

## Evidence and checks

- Four short MP4 motion tests; intended-speed, physical-speed and half-speed controls.
- Initial and latest representative frames are available under each test on the page.
- Water 96 states, 1.2 physical seconds shown across 4 seconds at 24 fps. The physical-speed control is 3.333x. Do not mistake slowed playback for natural speed.
- Fire and air 120 frames at 30 fps, 320 x 64 x 192 simulation grid, about 985 MiB reported GPU allocation. Finite fields and projection diagnostics are logged locally.
- Earth 120 frames at 30 fps; 65 volumetric pieces and 298 bonds. Pre-impact pair-distance changes peak around 8 mm; visible startup fracture was removed. Final review uses Eevee neutral shading; pilot comparisons used Cycles.
- Full water metadata and pressure checks are recorded in `simulation-checks.json`. Video integrity and browser checks are recorded separately after encoding.

## Next work, before either complete sigil

Fire needs a source/front treatment that loses the luminous tube appearance while retaining momentum. Water needs a controlled reconstruction/lighting comparison against the user's original reference at matched scale, plus a single supported bend that releases freely. Air needs a larger translating vortex with sparse tracer and a camera that exposes its depth. Earth needs hierarchical cohesive clusters with contact-local fracture, verified against a pre-impact stability test.

Only after those pass should a difficult fragment of each approved sigil be tested. The full-word hold, zoom-out and natural exit remain unvalidated. The current exports must not be described as the fixed intros.
