# Navier–Stokes finite-time blowup tracer

This experiment visualizes the **leading inner-core scaling** from OpenAI's 2026
finite-time blowup construction using the real CYBR ELEMENTS reconstruction
pipeline and CYBR LIGHT spectral renderer.

It is deliberately not presented as a numerical reimplementation of the full
166-page proof. The proof constructs an axisymmetric background, annular
oscillatory pulses, higher-order corrections, and a smooth compactly supported
force. This experiment instead builds an explicit divergence-free surrogate
similarity core with the same leading asymptotic exponents, fills it with a
visible tracer, reconstructs that tracer using CYBR ELEMENTS' existing
particle-kernel `SurfaceBuilder`, then renders the resulting meshes with
CYBR LIGHT.

## What is taken from the paper

Writing `tau = 1 - t`, the paper states for the inner core

- radial length: `l_r ~ tau^(1/2)`
- axial length: `l_z ~ tau^(1/2-h)`, with `0 < h < 1/100`
- azimuthal/axial speed: `|u_theta|, |u_z| ~ tau^(-1/2-h)`
- radial speed: `|u_r| = O(tau^(-1/2))`
- kinetic-energy scale: `tau^(1/2-3h)`

Thus the characteristic velocity diverges while the core energy tends to zero
for the allowed `h`. The core contracts radially faster than axially and
becomes increasingly slender.

Primary source:

- OpenAI, *Finite Time Blowup for Navier–Stokes* (2026):
  https://cdn.openai.com/pdf/32d9f210-8b73-45e0-91bc-82a30aef8a9a/navier-stokes.pdf
- OpenAI overview:
  https://openai.com/index/navier-stokes-solution/

## What CYBR ELEMENTS does

`generate_surface.mjs` uses an axisymmetric streamfunction for the poloidal
part, so its radial/axial velocity is analytically divergence-free. An
axisymmetric swirl is then added; because the swirl has no theta dependence,
it adds no divergence. The velocity scales are chosen to match the leading
powers above.

The visible boundary is a **tracer isosurface**, not a theorem-level fluid/free
surface. A small helical modulation exists only to make the inward-spiralling
structure visible. Surface extraction comes from the repository's actual
`work/flip-lettering/vendor/src/surface.js::SurfaceBuilder`; this is not a
canned mesh.

Generate ten similarity snapshots:

```sh
node work/navier-stokes-blowup/generate_surface.mjs \
  --out rendered/navier-stokes-blowup \
  --frames 10 \
  --tau-max 0.28 \
  --tau-min 0.008 \
  --h 0.009
```

Outputs:

- `config.json`: exponents and disclosure
- `metrics.json`: per-frame scale, velocity, energy, particle and mesh metrics
- `surfaces/*.obj`: reconstructed tracer geometry
- `manifest.json`: completion record

## CYBR LIGHT handoff

The paired branch in `cybrdelic/cybr-light` contains
`tools/navier_stokes_blowup.py`. With both repositories checked out as
siblings:

```sh
cd ../cybr-light
python tools/navier_stokes_blowup.py \
  --input ../cybr-elements/rendered/navier-stokes-blowup \
  --out rendered/navier-stokes-blowup \
  --mode tracking \
  --width 720 --height 720 \
  --spp 96 --bands 12 --threads 8 \
  --fps 5 --encode
```

The renderer uses CYBR LIGHT's native spectral path tracer and its deterministic
AOV/variance-guided presentation denoiser. Raw PFM/PNG radiance is retained.
No generative image model is used.

## Interpretation

The animation should be read as a visualization of the singularity's
**asymptotic geometry and scaling**, not as a claim that a literal blob of water
develops a sharp tip. The theorem concerns a smooth incompressible velocity
field whose speed becomes unbounded in a shrinking region while total kinetic
energy stays bounded.
