# Rejected CPU material pass

The current images fail the visual brief. No new output is approved for the site or a video batch.

Mitsuba 3.9.1 is installed and renders using scalar_spectral on two CPU threads. This is renderer infrastructure, not proof that the materials are photorealistic.

## Visible failures

- Lava remains a smooth strand with a dark covering. It lacks broad flow masses, varied folds and convincing exposed interior.
- Ice remains smooth transparent tubing. The vapor layer previously overwhelmed its solid structure.
- The separate lava skin coupon is still a rectangular, cloth-like sheet over an orange slab. It is rejected too.

## What is actually implemented

Ice has a reduced thermal particle-grid solve, latent heat, phase-dependent density, a stiff bond network activated by freezing, and a separate projected humid-air/condensation solve. Lava has reduced thermal viscous flow, a local depth-resolved cooling layer, and a separate implicit membrane experiment. These have explicit limitations in their reports. Most of the other requested material families have not been rebuilt in Mitsuba.

## Why this is not sufficient

Numerical checks established only finite states, energy bookkeeping, closed surface reconstruction and isolated constitutive responses. They did not establish correct material morphology or production-quality coupled dynamics. The source stream remains too uniform. The lava skin does not return contact forces to its bulk. The ice network does not resolve continuum crack propagation or separate the external surface along cracks.

## Next quality evidence

Compare a small sample directly with real material reference. Judge coherent volume, surface hierarchy, thickness, deformation and exposed internal structure before color or emission. The selected lava reference is the USGS photograph on the [NPS Lava Flow Forms page](https://www.nps.gov/articles/000/lava-flow-forms.htm). An implicit membrane alone does not reproduce that flow.

The full-trail renderer is held locally until that visual evidence exists. This is a quality condition, not a request for user permission. The GPU and movie queues remain disabled for this work. Accepted fire, smoke and water outputs and the original sigils remain untouched.
