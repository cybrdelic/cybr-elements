# Cybrdelic 02 — coherent element revisions

The user's acceptance reference is the clean, broad silhouette in the approved
fire and retained air/smoke films. The older water, earth and lightning `r2`
films are retained as rejected comparisons. These revisions use the same full
02 artwork, preserve its stroke widths and cutouts, and hold until about 5.8s.

## Actual methods

- **Water:** native APIC/FLIP pressure projection and surface tension, a single
  evenly sampled rounded source volume, and an authored bending potential
  outside that volume. The source finishes near 2s. The force releases from
  5.8 to 6.65s while gravity ramps in. Reconstructed resolved liquid surfaces
  are rendered with Cycles transmission, IOR 1.333, studio refraction lighting,
  velocity motion blur and a black camera background. Under-resolved isolated
  markers stay in the mass accounting but are not rendered as analytic spheres
  or multiplied into a decorative particle cloud. The hold is guided, not
  unaided free water. Source and numerical evidence: `../sigil-02-water-hold`.
  Fine optical normals use an eight-mode analytic capillary-wave spectrum
  below the grid scale; this detail does not deform the resolved silhouette
  or feed back into the bulk solve.
- **Earth:** 174 interlocking fracture pieces cover the complete approved
  silhouette. Assembly and the hold are authored rigid motion. Bullet gravity
  and contact take over at release. A CC0 Poly Haven rock_09 photogrammetry
  material supplies the surface maps. This is not an emergent fracture or
  granular constitutive simulation.
- **Lightning:** six changing families of 1,000 fine channel streamlines are
  guided within the actual glyph domain. Temporal discharge response, corona
  and an approximate advected aerosol glow preserve the energized silhouette
  while channels change. This is an authored electrical visualization, not a
  calibrated plasma or atmospheric lightning solver.

Water and earth use CPU Cycles pilot frames before GPU final renders.
Lightning's pilots and final render are CPU based. Full frame decoding,
contact-sheet inspection, timing and black-background checks are recorded by
`sigil_02_coherent_finish.py`. Agent visual review is not user acceptance.

Final intended media: 1920×1080, 30 fps, 10 seconds each, new `-r3` filenames.
The player keeps every older movie and compares r3 against r2. Fire and air
must remain byte-identical to the approved/retained files.
