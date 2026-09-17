# CYBRDELIC / directed water 01

The previous version lost the wordmark during its hold, had dense bead-like spray, and dropped the entire mass. This rebuild changes the source, guide, reconstruction settings, lighting, camera, and exit.

- One gated moving source follows the approved 01 route. Original pen-up sections are respected. Source timing is weighted by path curvature; guide-space occupancy limits prevent repeated passes from continually inflating the same region.
- Young liquid has more initial momentum before the guide settles it into the strokes. The hold uses explicit soft external forces and a small moving depth perturbation; it is art-directed waterbending, not unsupported levitation claimed as unforced physics.
- Original CYBR FLIP III.1 numerical solver is retained. Offline reconstruction uses 1.08h support, sigma 0.6 and four smoothing passes for a calmer main surface. No fixed 24-fragment particle groups remain.
- Primary droplets retain the reconstruction's disjoint representation. Secondary spray is sparse, generated only at fast, locally stretching surface regions, with persistent motion, bounded Pareto radii and finite lifetimes. It is a one-way passive model, not resolved air or two-way spray coupling.
- A continuous studio backdrop, restrained reflection flags, and softer lights replace the black/blue floor presentation. Camera moves from a closer opening into the full mark, then follows the departure slightly. There is no text or outline overlay.
- Release proceeds from the right edge toward the left. Released liquid stretches off-screen rather than colliding with unreleased letters or dropping to the floor together.

Three one-second no-spray samples (formation, hold, release) were rendered at native 1080p and reviewed before the full shot. A spray-enabled check used the same views. Earlier tests exposed washed-out lighting and an exit that bunched the water; those were corrected before production.

240 distinct states at 1/96 physical second; 24 fps playback gives ten seconds. All simulated states passed finite-state and pressure checks with no solid violations. Final media metadata and checksum are in the verification JSON. Cycles 48 samples with GPU denoising; original Three.js raster optics are not used.

Scope: the 01 water shot. Existing fire, 02, air, earth and prior water exports are preserved.
