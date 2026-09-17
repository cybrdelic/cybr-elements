# CYBRDELIC / water 01 — FLIP reconstruction

Replaces the rejected coarse Mantaflow motion study with a newly simulated scene using the user's CYBR FLIP III.1 solver and DetailReconstruction. Reference sources were copied into work/flip-lettering/vendor and verified by SHA-256; originals are unchanged.

Scene design: paired narrow emitters follow the approved 01 trajectory over 0.6 physical seconds. Opposing depth velocities generate collisions and sheet breakup. Upward launch velocities vary with emission time so strokes briefly gather around the wordmark before falling under ordinary gravity. This emitter choreography is art direction, not a claim of spontaneous water lettering.

96 consecutive physical states at 1/96 second; 24 fps playback gives a four-second shot at one-quarter physical speed. Grid spacing 0.03 scene metres; original reconstruction spacing 0.43h, support 0.99h, sigma 0.34, two smoothing passes, disjoint volume-carrying primary droplets. Whitewater uses the reference's one-way secondary particle model. No stationary letter-shaped mesh or reveal mask.

Rendering: native 1920x1080 Cycles, 48 samples and GPU denoising. Uses physically transmissive water materials; does not reuse the reference Three.js raster optics. All 96 physical states finite and pressure-converged with no solid violations. Final media integrity is recorded in the accompanying verification JSON.

Scope: new 01 water shot. Existing 02, air, earth and fire exports are preserved.
