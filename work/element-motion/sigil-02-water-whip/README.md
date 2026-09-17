Water 02 revision 6

Replaces r5's uniform arch with a rounded ground crescent, hooked lift, forward
bank, accelerating cast and trailing unfurl into the approved 02 geometry.

One 6-second CPU preview was simulated, rendered and reviewed before the full
1920 x 1080, 30 fps, 13-second production pass. All 390 frames were simulated
from the new initial state and rendered; no previous-shot frames were spliced in.
The final MP4 was decoded in full and its representative frames inspected.

The path is directed through bounded external acceleration goals. Native CPU
APIC/FLIP handles transport, pressure, free surface and floor response. Cycles
OptiX renders the production pass. This is authored bending, not spontaneous
letter formation. Optical capillary normals and unresolved wall damping retain
the previous pipeline. Fine unresolved markers stay in the solver but are not
rendered as a bead cloud.

Validation: 138,022 primary parcels retained throughout; all pressure solves
converged; no nonfinite values, solid violations, capacity rejection or source
balance error. Maximum encoded mesh volume error: 0.198 percent. Maximum
unresolved hold fraction: 0.295 percent; final unresolved fraction: 3.376 percent.
At the end 120,173 particle centers are within the floor-contact band.

The turn retains a bright reflection and the unfurl briefly passes through an
S silhouette. The right-side residual motion resolves into the original mark by
7 seconds. The agent judged the intro improved; user acceptance is pending.

The full run streamed and consumed intermediate particle/mesh caches to limit
storage. Keep the completed revision immutable. Run future experiments in a
new revision directory; the runner refuses to overwrite an existing simulation.

Entry points: sigil_02_whip_prepare.py, sigil_02_whip_pipeline.py,
sigil_02_whip_run.py, sigil_02_whip_review.py, sigil_02_whip_publish.py in the
parent directory. Force fields and optics derive from sigil-02-bending-ground.
