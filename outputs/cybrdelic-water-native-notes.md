# CYBRDELIC water / native renderer rebuild

Both sources are the full approved Study 06 silhouettes: 01 Fluid sigil and 02 Cut blackletter. No substitute font or centerline tube is used.

The original offline FLIP III.1 numerical solver, quality profile, reconstruction and Three.js water shader match the user’s local source by SHA-256. A new scene adapter supplies the source geometry, camera, and simple backdrop. The offline project itself is unchanged.

Water receives ballistic launch position and velocity only at birth. There are no home-position springs, continuing letter guides, animated vertex targets, repeated silhouette replenishment, or opacity-based logo disappearance. Slow motion around formation provides a brief display interval; gravity then brings the liquid into the basin, where it splashes and settles. The ending intentionally retains the physical water rather than deleting it on screen.

The first two source tests—vertical replenishment and shallow-surface replenishment—were rejected after visual review. The retained shot uses one-time emission, 48,085 / 50,400 particles, 2.5 cm simulation cells and the reference reconstruction spacing of 0.43 cells. Only empty reconstruction space is cropped; voxel spacing is preserved.

Primary isolated droplets are rendered once through the original renderer. No artificial fragment groups or decorative secondary spray cloud is added. The renderer uses its original screen-space dielectric optics, which are an approximation and can still look glass-like in a still image.

Each video contains 192 distinct simulated states at native 3840 × 2160, 24 fps, eight seconds. Playback varies smoothly in speed around formation; it is not real-time playback. See the verification JSON for physical durations, state checks, source hashes and export hashes.

The current versions are integrated into the existing Elements gallery, with links to the replayable Three.js scene and the approved artwork. Earlier files and the font package are preserved.
