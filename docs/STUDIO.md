# Physical studio look-development

The original seven films are historical outputs. This renderer addresses the
visual faults exposed by the CPU rebuild: suppressed blue water lighting,
underlit ice, stretched stone side-face UVs, rigid-fragment lava, flat gas
integration, and sustained bloom-heavy electrical outlines.

## Reproduce

Use Python **3.11**, Blender **4.5.3** (the pinned `bpy` wheel is supported),
Node.js 22, and FFmpeg. The source inputs are restored from the existing asset
release with their recorded SHA-256 hashes.

```sh
python -m pip install bpy==4.5.3 numpy==1.26.4 scipy Pillow scikit-image numba
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu

# One native hero frame; every pixel is newly rendered.
python scripts/studio_pipeline.py --kind ice --quality hero --output work/studio/ice-hero

# A two-second motion review, sampled from the native 30fps timeline.
python scripts/studio_pipeline.py --kind water --quality review --output work/studio/water-review

# Every original frame, 720p, 128 Cycles samples. This is substantially slower.
python scripts/studio_pipeline.py --kind water --quality production --output work/studio/water-production

python -m unittest discover -s scripts -p 'test_studio_lava.py' -v
```

All seven element names are supported. `--frames 90:150:2` explicitly renders
native frame IDs 90, 92, ..., 148; these are a **15fps review**, not a completed
30fps production film. A complete water film requires frames 0–239; gas requires
0–293, and the other studies require 0–299. Never replace a full film with a
sparse review. Output directories must be fresh, and the reports distinguish
complete native timelines from selected studies.

## Changes and preserved state

| Element | Rendering/geometry change | Preserved or newly solved state |
| --- | --- | --- |
| Water | Neutral reflection cards at full power, restrained absorption, closer perspective, visible contact/shadow, shorter shutter | Original 138,022-parcel APIC/FLIP solve; native surface and volume-carrying drops |
| Ice | Clear 1.31-IOR dielectric, heterogeneous entrained-air scattering, rougher fracture surfaces, neutral transmission lighting | Original fracture geometry, authored assembly, native Bullet release |
| Earth | Three-dimensional rest coordinates on side faces, local physical relief, larger composition and contact lighting | Original scanned textures, fracture geometry, authored lift, Bullet collisions; studio entrance is forward-authored |
| Fire | Native density, temperature and reaction VDB grids; temperature-driven emission, corrected single density sampling, perspective path tracing, gas shadows and ground illumination | Original reaction/transport/projection solver executed on CPU; source SDF is resampled for the selected grid |
| Air | Native density VDB, perspective scattering, external light transport and self-shadowing | Original incompressible gas transport and forcing, executed on CPU |
| Lava | Continuous viscous free surface, cooling crust optics, different camera for a real ground-flow study | New conservative 2.5-D Bingham thin film on the retained source field; advected enthalpy, surface radiation/convection, cooling-dependent viscosity |
| Lightning | Depth in channels, bounded short pulses, quiet intervals, neutral cores, restricted halation, pulse-gated tracer haze | Retained branching trees and incompressible atmospheric solve; discharge timing and ionization radiance remain authored |

`studio_scene.py` owns shared lighting and optical material setup.
`render_studio.py` builds the retained material/solid scenes and renders selected
native states. `prepare_studio_gas.py` exports the actual fire/air fields.
`studio_lava.py` owns the separate finite-volume flow model. The water renderer
accepts `--studio`; its old saturated-blue attenuation override is removed in
both modes.

The stage is a continuous photographic sweep rather than a visibly terminating
plane. Gas optical detail is a three-dimensional procedural modulation within
the solved density, with zero extinction retained outside it; it is not extra
resolved turbulence. The temperature/reaction fields drive fire emission.

Selected water reviews reconstruct particle states in ascending selection order.
Their surface hysteresis history differs from a complete reconstruction; they
retain the same solved particles and are labeled sparse reviews. For a complete
production run, reconstruct and render every state in order.

## Scope and evidence

The lava model transports volume and specific enthalpy with the same upwind
face fluxes. Closed boundaries and donor limiting conserve volume without
discarding overshoot. An implicit radiative surface boundary stays between
ambient and bulk temperature. The tests exercise volume and heat-loss ledgers,
positive transport, viscosity response, yield arrest and latent-heat inversion.
The surface skin is a lumped boundary model; the energy ledger covers the
column's enthalpy and ambient losses. Crust fissures and fine relief are optical
look-development detail, **not resolved fracture mechanics**. The camera film
uses a documented 6× physical-time rate for lava.

These are nominal graphics models. The pipeline does not claim calibrated lava
rheology, 3-D solidification/fracture, freezing, photometric combustion, or plasma
physics. Numerical regression checks establish their named properties. Successful
decoding does not establish aesthetic quality or photorealism; review real frames
and motion before selecting a production revision.

The `Physical studio reviews` workflow produces 21 independent review shards,
covering all seven elements with input/source/image hashes. They use fresh
geometry and solved state, retain native frame numbering and store actual
rendered 960×540 PNG images at 48 Cycles samples plus one 1280×720 hero per
element at 64 samples. Water reviews cover
frames 165–223 to include fluid release; earth covers 140–198 to include complete
assembly. The other studies cover 90–148. All are two-second, 15fps reviews.
No older film pixels, image generation, or screen-space
glyph compositing enters this path.

Download and extract the workflow shards into one directory. Encode the actual
frames without interpolating motion or changing their native elapsed time:

```sh
python scripts/assemble_studio_reviews.py --inputs work/downloaded-studio-shards --output work/studio-downloads
```

The assembler verifies the image hashes, common renderer revision, uniform
frame spacing and dimensions before encoding. It fully decodes each resulting
MP4 and exports the seven PNG heroes, a contact sheet, provenance, and a ZIP.
An additional local water review covering 135–163 can be supplied as a second
input to show the intact lettering before the workflow's 165–223 release study.
