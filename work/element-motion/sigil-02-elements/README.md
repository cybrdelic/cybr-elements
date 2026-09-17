# Cybrdelic 02 — four additional elements

The user explicitly approved `sigil-02-v2/fire-02.mp4` and requested the other
four elements. The approved fire and all original bending videos are immutable.
Only style 02 is in this delivery.

## Source and timing

`../sigil-02-v2/source.npz` contains the complete tapered artwork, negative
spaces, ignition arrival times and source tangent directions. This is the
source geometry, not an output-image mask. The common reveal runs from 0.3
to 3.9 seconds, the pose is held through 6.8 seconds, and release follows.
All four output videos are 1920 × 1080 at 30 fps. Water ends at 270 frames /
9 seconds, when the liquid has left the camera and the image is black. The
other three run for 294 frames / 9.8 seconds. The later unseen floor impact
was simulated but is outside the selected water edit; no image fade is used.

## Models and limits

- Water: existing native CPU APIC/FLIP solver, pressure projection, surface
  tension and native surface reconstruction. 153,455 material markers form a
  rounded 3D source volume. Initial momentum is supplied once. Gravity is
  deliberately reduced during the bending hold and restored at release.
  There are no letter-shaped collision walls or fitted output meshes. The
  accepted Cycles optical material and studio reflection lights are retained.
  Secondary spray uses the existing energy-gated subgrid closure, not a claim
  that every tiny droplet is resolved by the pressure grid.
- Earth: original layered clast meshes and shaders; mass-weighted contact
  impulses with spherical collision proxies, drag and gravity. Damped
  collection forces are authored bending controls and switch off at release.
  This is not a full non-spherical rigid-body contact solver. The third trial
  uses 670 clasts, including larger bodies that read more clearly than gravel.
- Air: existing pressure-projected 3D transport and directional volume
  optics. Thin layers of passive mist visualize the flow. The second trial
  lowers tracer supply and raises the constant concentration-loss rate; this
  modifies the transported scalar field, not composited image opacity.
- Lightning: a 3D branched conductor graph seeded across the full artwork,
  with current strength derived from subtree load, geodesic excitation,
  transient exposed strokes, exterior forks, and pressure-projected aerosol.
  This is an art-directed electrical visual model, not calibrated plasma.
  The initial contour-only point-charge trial was rejected as neon-like.
  The second trial had overly bright aerosol; the third retained the channel
  energy and reduced the approximate scattering contribution. A final timing
  fix gates the aerosol lighting to the channels that have actually become
  excited, eliminating the premature ghost of the unwritten portion. No
  ambient emission is assigned to unlit aerosol.

These are graphics simulations with deliberate bending controls. They are
not engineering simulations or claims of physically exact elemental magic.
No global image fades are used. Material movement and scalar evolution create
the releases. Corners remain black; moving material may cross the frame edge.

## Review and publication

`sigil_02_elements_finish.py` encodes earth/water, decodes every video frame,
checks dimensions, frame count and frame rate, makes reduced contact sheets,
and records black-corner and luminance measurements. Publication requires a
manually recorded visual review for every video and verifies approved fire's
SHA-256 before adding the other four files to the existing player.

The page has one video at a time, native playback controls, an element selector,
an artwork comparison, and per-element download links. `?element=water` (or
earth/air/lightning/fire) selects a specific video.

The late water reconstruction culled particles below the camera while the full
153,455-marker solver continued. Its sparse tail used mass-equivalent analytic
parcels when too few markers remained for a supported surface. The selected
film stops at frame269, when the image is black, before the later rebound.

Working trials are preserved for comparison. Final source paths are configured
in `../sigil_02_elements_finish.py`; do not publish an earlier rejected trial.
