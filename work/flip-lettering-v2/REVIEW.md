# Water 01 revision: hold and spray

Target: premature fall and visually uniform beads. Scope: flip-lettering-v2 only; existing media and original FLIP library retained.

Timing: draw 0–0.6 physical s, hold through 1.25 s, release holding acceleration over 0.15 s, gravity then continues through 2 s. Quarter-speed playback: 8 seconds total, 2.6-second hold after drawing, 0.6-second release transition. Holding is an explicit art-directed external force, not unsupported levitation presented as unforced physics.

Emitter: depth collision speeds 1.3 to 0.32 m/s, tangent speed 0.20 to 0.08 m/s; remove the ballistic upward launch that previously made gravity timing inconsistent.

Spray: primary isolated-droplet volume partitioned into 24 fragments per tracked cluster with a truncated Pareto distribution (alpha 1.5, max/min raw radius 10), normalized by sum of cubed radii to preserve parent volume. Center-preserving seeded offsets spread over tracked age. This is art-directed subgrid representation, not an additional resolved FLIP solve; primary body remains disjoint from its droplet representation. Secondary radius-at-birth distribution is truncated Pareto alpha 1.7. No per-frame radius resampling.

Visual loop: first hold pilot showed overly clustered microdroplets. Retained size hierarchy, added time-dependent dispersion to thin the clustering; inspect sequentially reconstructed hold and release frames before final export. Two focused iterations.

Checks: original FLIP state convergence and finite values, complete 192 physical states, per-frame breakup volume error, actual radius quantiles, complete render sequence and ffprobe. 1080p remains unchanged. No claim of an exact global Pareto fit after mixing parent volumes.
