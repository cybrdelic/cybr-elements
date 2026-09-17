# Cohesive lava study

The hot interior is now a separate closed mesh beneath a thick, perforated crust. A CPU XPBD model supplies membrane deformation, irreversible weld failure, flexion, gravity, viscous drag and unilateral foundation contact. The input foundation rises kinematically; this is not two-way fluid/solid coupling. The prior rough-basalt detail is transferred onto that deformation. Large tears follow the mechanics; small vents remain authored from the earlier surface.

The first geometry studies were rejected before path tracing because the crust stayed intact or became a featureless blanket. The first shaded close-up also failed: dropping whole triangles made sawtooth openings, and the lighting produced pink reflected pools. Small vents now use continuous scalar-contour clipping and relaxed boundary curves. The exposed core uses natural enthalpy-column cooling from four motion snapshots and an approximate lateral boundary layer; the older perimeter keeps its temperature cap. The earlier images have not been overwritten.

CPU checks confirm finite state, irreversible failure and zero measured foundation penetration before detail dressing. Crust self-contact, fully coupled fluid forces and final-quality motion are not validated. These limitations and remaining procedural-looking morphology prevent a claim of production or world-class acceptance.

References: [XPBD](https://matthias-research.github.io/pages/publications/XPBD.pdf), [lava inflation](https://www.nps.gov/subjects/volcanoes/basaltic-lava-flows.htm), and [Mitsuba materials](https://mitsuba.readthedocs.io/en/stable/src/generated/plugins_bsdfs.html).

---

# Lava rough-basalt refinement

The published material still keeps the original rough baseline available through the Earlier pass button. The baseline image and geometry are unchanged. The final candidate has been directly inspected, including the larger still; it is an improvement in form and sampling, not an assertion of world-class realism or a finished simulation.

The first controlled render kept the old geometry and corrected the distribution of light samples. This exposed substantial real crust detail under the old spectral noise. Subsequent CPU studies retained that surface and added uneven thicker lobes, deeper existing openings driven by surface stretch, varied matte/glassy basalt, and vesicle bump relief. No decorative glowing strokes, background environment, GPU work, other elements, sigil edits, or video batch were added.

The original particle cache was not resimulated. The macro shape changes are authored, globally volume-preserving deformations, and the crust exposure is a VFX approximation. Coupled crust fracture, motion and cooling remain unresolved; some repeated small structures are still visible. Those need a mechanics change, not more samples of this still.

Verification: finite geometry, volume agreement, CPU-only render receipts, direct image review, exact black top/bottom image regions, original baseline checksum, and unchanged 01/02 sigil cache checksums. The final render's exact resolution, sample count, resource use and input hash are recorded in active-candidate.json and the bounded process logs.

Reproduce the surface with lava_refine_surface.py. For the final render, use the environment settings in active-candidate.json with lava_refine_render.py through bounded.py. Keep CUDA_VISIBLE_DEVICES=-1. The renderer uses Mitsuba scalar_rgb and explicitly CPU OIDN.

Material implementation reference: https://mitsuba.readthedocs.io/en/stable/src/generated/plugins_bsdfs.html

---

# Lava-only CPU rebuild

This is a material prototype, not production acceptance and not a finished sigil film.

## Active baseline: earlier rough pass restored

The user explicitly judged the smooth pass significantly worse than the earlier particle-like version. The matching earlier commentary described the first lava-only render as a “granular puddle” at 2026-09-14T10:49:54Z. The exact saved image `renders/hero-0059-640-24spp.png` is restored as the visible baseline, with source and geometry in `iterations/01/`. See `active-baseline.json` for checksums and provenance. No simulation or render was performed for the restoration.

The smooth/no-lines image is rejected. Preserve the earlier render's dense structure, local contrast, scattered hot exposure and sense of depth. Do not replace these qualities with a smooth surface merely because numerical noise metrics improve. Technical corrections must be evaluated against this visual baseline. This is a preferred starting point, not a claim that the earlier simulation is finished or photorealistic.

## Superseded experiment: unwanted lines

The user rejected the lines. All periodic displacement grooves, Voronoi crack seeds, the central glowing slash, noise-selected holes and random surface-age patches were removed. Skin exposure now follows a filtered deformation field; the bulk shape stays intact.

A separate matched render identified a major lighting issue: 47 emitters had equal default sampling weight, leaving only 1/47 of direct-light samples for the key light. Tiny temperature-bin emitters dominated the sampling budget. Weighting emitter selection by luminance times area raises the key's probability to 0.99207 without increasing its radiance. The fine white noise and the denoiser's squiggly artifacts largely disappear at the same 16 samples per pixel. `renders/sampling-review.json` records a matched cold-surface patch comparison. The current image is `renders/clean-light-detail-0029-640-16spp.png`.

This correction fixes unwanted linework and a sampling fault. It does not establish world-class morphology or coupled fracture. The surface is now deliberately simpler and smoother; convincing crust breakup is still unfinished. Earlier visual review notes below describe the rejected versions.

## Scope and compute

Only lava was changed. No GPU simulation, GPU rendering, GPU denoising, or video batch was launched. CPU work is restricted to two logical processors and bounded child processes. The original sigils and existing element films are unchanged.

## Changes retained

- A fresh reduced viscous-fluid cache supplies the bulk shape and transported material coordinates: 15,272 particles, position-based incompressibility, temperature-dependent implicit viscosity, contact with a plane.
- A separate 64-layer, 38.4 mm thermal column model accounts for radiation, convection, conduction, latent heat, and a hot interior. It applies no artificial cooling sink. Initial crust age is authored material history (80–630 seconds), separate from the short simulated shot time. The original bulk cache still includes its documented additional surface heat sink; this is not an entirely natural-cooling coupled simulation.
- Surface geometry follows material coordinates. Compression and stretch modulate the relief. The primary tear and weaker regions are authored fields, not a solved fracture network. They do not apply contact forces back to the fluid.
- Mitsuba 3.9.1 traces the scene in scalar RGB on the CPU. Source radiance comes from numerical integration of a Planck spectrum against CIE functions. The background is black and there is no environment map or composited smoke.
- OIDN is explicitly configured for the CPU. The old shading-normal AOV was nearly constant in this setup; the corrected geometric-normal pass spans the visible orientations. Bump removal did not resolve the principal visual defects and was not retained as a solution.
- Render samples are checkpointed in groups of eight, including HDR, AOVs and actual sample count. An interrupted longer render can now retain completed samples. The budget wrapper propagates failed jobs as nonzero exits.

## Visual review

The first five broad form/skin variants were not accepted. The first flattened too much; subsequent versions read as a split rock or a uniformly corrugated slab. The primary opening was too straight and uniform. Studio illumination overwhelmed the internal radiance and emphasized sparkling highlights.

A subsequent thermal/lighting investigation removed the thin-column artificial quench from the surface model, then increased column depth for older insulating crust. The intermediate natural-cooling image had an unconvincing broad red gradient and was rejected. The deeper model gives distinct cooler crust and hotter openings. The visible shape still does not establish correct moving crust folding or rupture.

The final close view is available as a **material study only**. It must not be described as world class or promoted into a finished film based on finite-state checks, volume correction, sample count, or renderer choice.

## Unresolved work

The broad shape remains too slab-like. Folds still show a patterned organization, and the exposed regions look shaped rather than emerging from a coupled fracture/contact model. Rendering more pixels does not resolve those defects. No motion sequence or sigil integration has passed visual review.

Reference: the [USGS photograph on the NPS Lava Flow Forms page](https://www.nps.gov/articles/000/lava-flow-forms.htm). The photograph is a reference only, not a texture pasted into the render. The [1999 Animating Lava Flows paper](https://graphicsinterface.org/wp-content/uploads/gi1999-26.pdf) distinguishes simulated bulk from procedural surface dressing; this implementation must retain that distinction too.
