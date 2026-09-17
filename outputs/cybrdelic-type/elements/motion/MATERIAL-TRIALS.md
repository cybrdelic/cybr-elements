# Material trials

These are optional experiments beside the accepted versions, not automatic replacements. The shared source path, duration, framing, independent playback and synchronized controls are retained.

## Fire

480 x 96 x 288 simulation cells, up from 320 x 64 x 192; six substeps. Temperature-driven color, reaction-driven emission and reduced bloom. The first trial was too dim and was superseded by a brighter second trial. The source choreography is unchanged, but finer simulation cells change small-scale flow. The smooth leading tip is not completely eliminated.

## Water

Uses exactly the accepted particle-position and velocity cache. Reconstruction spacing is 0.32 cell instead of 0.43; PCA support is 1.08 instead of 0.99 cell; modest field smoothing and three mesh smoothing passes. Surface volume is checked against particle-derived volume. Broader studio reflection cards and slightly stronger thickness-dependent absorption improve visibility. The material remains dark against black, and no claim of temporally perfect normals is made. No added droplet or foam layer.

## Air

The same solver resolution, source and dynamics are retained. Changes affect density-to-opacity mapping, directional scattering, self-shadowing and bloom. The first trial was too dark; the second restores illumination while retaining more transparent low-density regions. Air is still visualized by a tracer, so a smoke-like appearance remains possible.

## Earth

Render-only chipped edges, fracture-face tessellation and small displacements; finer bump relief and mineral color variation. Base collision meshes are retained, preserving rigid-body motion. The accepted dust layer is retained. Changes are subtle at the full composition scale; these are not scanned rock assets or a complete geological fracture model.

## Review

Use Original and Trial on each card at a fixed time. Switching preserves the selected clip’s playhead and pauses playback. Both individual video controls and Play all remain available. Original exports are preserved.
