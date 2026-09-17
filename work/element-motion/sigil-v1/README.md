# Cybrdelic elemental sigils

Scope: original study06 wordmarks 01 and 02, each in earth, fire, water,
air and lightning. This is an art-directed branding sequence. The lettering
is a control input, not a claim that unconstrained matter spells a word.

Timing: source starts at 0.3 s, completes at 3.2 s, holds through 6.2 s,
then releases. Deliveries are 300 frames, 30 fps, 1920 x 1080, black camera.

## Models

- Fire: three-dimensional advected fuel, oxidizer, temperature and soot;
  projected velocity, limited MacCormack scalar transport. Glyph-shaped fuel
  supply and an authored oxidizer boundary preserve the counterspaces. The
  boundary and supply release at 6.2 s; combustion and transport continue.
- Air: the same projected gas transport, with an illuminated passive tracer.
  Authored tracer dissipation around the letter openings preserves the hold.
- Water: the existing native FLIP/APIC solver, capillarity and pressure
  projection, free front/back surfaces, an invisible glyph-shaped side guide
  during assembly and hold, then release to gravity. Surface reconstruction
  and spray use the existing v5 pipeline. The side guide is an art control.
- Earth: 320 immutable, closed fragments per mark. A critically damped
  assembly guide sets their pose; Bullet handles gravity and contacts after
  the release. Geometry is registered to the exact approved silhouette.
- Lightning: persistent guided filament paths, transformed connected trees
  from the v5 point-charge growth solver, nonuniform repeated return strokes,
  and a diffusing/recombining corona. This is a graphics model, not a
  calibrated plasma simulation. No white wordmark is composited over it.

## Verification

`sigil_audit.py` checks complete frame count, full video decode, dimensions,
frame rate and representative corner pixels, and builds a reduced timeline
for visual inspection. `visual-decisions.json` records inspected choices.
Geometry topology checks are in `earth-geometry-validation.json`.
Per-material numerical reports sit beside the preview frames. The original
bending-video hashes are recorded in `existing-video-hashes.json`.

## Storage

Native water states and reconstructed meshes are consumed through a bounded
pipeline and removed after the next stage writes its result. Final frames,
videos, solver reports and sources remain. Old, unrelated water PNG caches
were losslessly repacked only after every decoded pixel matched; see
`lossless-frame-archives/RESTORE.md` to reconstruct those exact pixels.

The old bending videos and original sigil artwork are preserved.
