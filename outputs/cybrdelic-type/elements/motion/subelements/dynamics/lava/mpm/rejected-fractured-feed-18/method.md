# Lava simulation: CPU implementation and evidence

This directory contains a new three-dimensional simulation. It does not load
the old magma/lava/basalt stage meshes. It is under validation, not approved as
a complete production lava solver or a photorealistic final shot.

## Implemented

- Quadratic APIC particle/grid transfer; particles carry mass, enthalpy,
  deformation, elastic stress, thermal volume strain and tensile history.
- Implicit three-dimensional momentum solve. A Newtonian melt and a Maxwell
  crystal network act in parallel. The network becomes elastic above a nominal
  0.65 crystal-packing fraction. Below packing, a Krieger-Dougherty-style
  fluidity controls relaxation; solid basalt no longer uses melt viscosity.
  Temperature and latent heat come from one enthalpy law. This packing closure
  is an approximation, not a calibrated basalt composition model.
- Cell-averaged bulk response, with separate pressure degrees of freedom for
  separated material components. The nominal bulk and elastic moduli have not
  been reduced to make explicit timesteps affordable.
- Nonlinear implicit Fourier heat conduction, surface radiation, convection,
  and contact with a specified cold substrate. Viscous dissipation, including
  melt/crust interface drag, returns heat to the particles. The contact solver's
  generalized objective loss is recorded separately, not all converted to heat.
  There is no extra cooling sink or time-scale multiplier in the equations.
- Thermal contraction and an energy-regularized tensile damage law. Material
  connectivity is created as it solidifies; sufficiently failed bands lose
  connectivity. Grid supports are split locally across failed bands, so a crack
  can open while the solid remains connected beyond its crack tip. Pressure
  averaging follows these local fields. Partial-crack and free-body tests cover
  this change; fracture convergence is still unproved.
- A symmetric implicit viscous traction couples melt and crust. Momentum is
  equal/opposite and dissipated work returns to enthalpy. Its one-cell interface
  thickness is a numerical closure whose spatial convergence remains untested.
- Equal/opposite unilateral contact impulses solved inside the implicit
  material step using a nonnegative dual solve. Separation does not create an
  attractive contact impulse. Interfragment contact is currently frictionless;
  a validated Coulomb cone solve remains outstanding. The melt uses a no-slip
  substrate. Frozen clasts use unilateral finite particle-domain floor contact;
  their overlapping grid supports no longer pin them before physical contact.
  Solid-floor contact is currently normal-only, with particle-spacing geometry.
- An independent low-Mach MAC gas solve. Moving material volume displaces gas;
  gas density obeys conservative finite-volume transport. Heat transferred from
  the lava drives thermal expansion and buoyancy; gas temperature feeds back
  into the lava boundary heat loss. Dynamic gas pressure acts on the material.
- A finite-capacity 3-D conducting rock bed is available with `--bed`. Its
  temperature feeds back into the lava contact heat loss; energy exchange is
  measured on both sides. The earlier long cache used a cold reservoir instead.
- Energy-limited subgrid basalt dust: a declared 1% of fracture work produces
  new dust surface area at a nominal 3 micrometre effective radius. Dust mass
  and enthalpy leave the material and enter conservative gas transport, with
  Stokes settling, thermal exchange and extinction derived from concentration.
  This is a nominal fragmentation closure, not a calibrated volcanic ash model.
- Checkpointed particle and gas caches at actual physical timestamps. Code
  hashes are recorded per simulation chunk. CPU diagnostic surfaces interpolate
  the simulated temperature and phase; the mesh builder adds no fracture lines.

## What is not established or complete

1. The sample is approximately 10 cm across and initially 0.25 kg. Current
   runs are resolution studies, not the final large branded lava geometry.
2. Basalt properties are nominal, not fitted to a measured composition.
   The Arrhenius rheology and phase interval need experimental calibration.
3. Tensile damage uses a crack-band law. The connectivity threshold and
   directional edge rule are discretization choices. This is not a validated
   mixed-mode fracture toughness model; fragment-size convergence is unproved.
4. Contact acts at material-grid support scale. Subgrid open gaps and contact
   heat resistance are not resolved. Thermal transfer still uses a shared
   conducting grid, which can exchange heat across a crack narrower than a cell.
5. The gas uses a regularized volume fraction with a 2% residual fraction in
   fully occupied cells. This is a diffuse interface, not an exact cut-cell wall.
6. Gas water transport is present, but there is no active volcanic degassing,
   bubble nucleation or condensation microphysics. `liquid` remains zero.
   Fracture dust is not a replacement for those missing mechanisms.
7. The long material cache used a specified cold substrate. The finite bed has
   passed an exchange test, but a complete long lava/gas/bed/dust run has not
   passed validation.
8. Enthalpy conservation and contact momentum are tested. A complete coupled
   mechanical/thermal free-energy audit through fracture and phase changes is
   not complete. A passing heat ledger alone is not physical validation.
9. Cooling-run kernel reconstruction cannot resolve cracks smaller than particle
   spacing. The separate fractured-feed study embeds specified initial clast
   boundaries in fitted MPM motion. That is a surface approximation, not proof
   that this grid resolves fracture formation or subgrid contact.
10. Obsidian requires a separate composition/glass-transition model. It is not
    produced by allowing this basalt material to cool for longer.
11. The 10 mm versus 5 mm material-grid comparison has not established convergence.
    See `validation/material_grid_refinement.json` for the current result and
    source hashes; the earlier version differed by 19.48% against a 15% gate.
    **Do not start a final rendering batch or call the requested full sim done.**

## CPU evidence

### Earlier cooling-crust work, 2026-09-14

- `crust-local-10`: fresh 744-point run, 66.782 physical seconds. Crust
  stress retention, melt drag, local fracture fields and conditioned contact
  are active. At the checkpoint there are 31 failed bonds and 458 grid nodes
  with multiple velocity fields. Those counts do not establish visible cracks.
- `crust-fine-11`: fresh 5,860-point run at a 5 mm grid, 10.451 physical seconds.
  It is an early cooling study, not a finished flow or refinement proof.
- `lava_mpm_crust_check.py`: tests the packed-network elastic limit, Maxwell
  time convergence, and conservative implicit melt/crust drag.
- `lava_mpm_local_check.py`: a prescribed partial-crack coupon remains globally
  connected but has 20 locally split nodes. Uniform translation is preserved.
  The coupon's prescribed crack is a test fixture, not a lava simulation input.
- `lava_mpm_crack_surface.py`: **rejected experimental reconstruction**. It
  exposes particle-grid terraces and changes volume by about 7.5% in the tested
  coarse state. It must not be passed off as resolved basalt fracture geometry.
- At that stage no new Mitsuba batch or GPU work was performed. The kernel surface remains
  visibly too smooth and coarse for the heavy fractured basalt target. A passing
  component test is not visual acceptance.

Runs `crust-network-08` and early `crust-interface-09` chunks encountered contact
failures. Their checkpoints and logs are retained for diagnosis. The final fresh
`crust-local-10` run uses the subsequent contact-support and local-field fixes.

Those cooling cases are finite samples on a cold substrate. The newer inlet
experiments below are separate scenes with a continuous mass/enthalpy source.

### Inlet and fractured-feed work, 2026-09-14

- `lava_mpm_inlet.py`: prescribed quadratic-spline inlet velocity, reflected
  upstream/ground supports, source quadrature, and stationary conduit contact.
  Mass, enthalpy, source kinetic energy and boundary work are recorded.
- `inlet-crust-12` and `inlet-conduit-13`: incoming melt feeding the actual
  `crust-local-10` cache. Both remain visibly swollen smooth lumps. The small
  Mitsuba proof of case 13 is retained as a rejected visual baseline.
- `fractured-feed-18`: a separate initial condition containing six irregular,
  porous basalt pieces and molten material. **Initial cracks and vesicles are
  specified geometry, not outputs of cooling, fracture or gas nucleation.**
  The current short interval is in its `state.json`. Its motion, contact,
  source mass and heat evolution are computed by the MPM solver.
- An important boundary error was found: imposing no-slip on every material
  field anchored solid clasts whose support merely overlapped the ground.
  Only liquid fields now receive that boundary condition. Solid floor contact
  constrains finite particle-domain velocity inside the implicit solve.
- `lava_mpm_floor_check.py`: above-floor free fall and nonpenetration at every
  impact step. `lava_mpm_inlet_check.py`: moving boundary, inlet profile,
  source ledgers, and stationary conduit walls/downstream release.
- `lava_mpm_clasts.py`: explicit initial solid boundaries with per-clast
  particle-volume quadrature; fitted affine motion from actual material points.
  Maximum fit error and per-piece volume mismatch are in each surface receipt.
  Molten material is reconstructed separately to avoid averaging cold/hot
  optical properties together. Unresolved kernel overlap remains possible.
- `lava_mpm_render.py`: bounded Mitsuba `scalar_rgb` CPU proof, physical
  temperature emission, area lighting, nominal rough dielectric optics and
  CPU denoising. Surface pores include specified initial geometry and an
  additional optical bump approximation. No GPU or final movie batch.
- Cases 14–17 were intermediate geometry, contact and lighting trials. They
  are retained for diagnosis; none is claimed as an accepted production shot.

The failed grid-refinement gate, incomplete gas/bed/degassing coupling, nominal
material calibration and unfinished fracture convergence are still open. Do
not describe the fractured-feed initial condition as the complete formation
simulation requested by the user.

`validation/*.json` contains individual tests and numeric evidence. Tests cover
affine transfer, gravity, analytic viscous shear decay, enthalpy roundtrip,
insulated conduction, the one-phase Stefan front, crack-band energy,
liquid stress memory, ground collision, fragment momentum and separation,
phase-created connectivity, remelting, gas rest/buoyancy/displacement, and
matched gas/lava heat exchange. Tests are not a visual-quality acceptance.

Run scripts from the parent `mitsuba-rebuild` directory through `bounded.py`.
Each job is limited to two CPU cores, 3 GiB and 180 seconds. Simulation chunks
save state; there is no automatic movie-render queue.

```powershell
& .venv/Scripts/python.exe bounded.py --seconds 180 lava_mpm_validate.py
& .venv/Scripts/python.exe bounded.py --seconds 180 lava_mpm_gas_validate.py
& .venv/Scripts/python.exe bounded.py --seconds 180 lava_mpm_run.py --name new-run --seconds 10 --dx .005 --dt .1 --gas --gas-dx .02 --bed
& .venv/Scripts/python.exe bounded.py --seconds 120 lava_mpm_surface.py --name new-run
```

## Primary references

- [Stomakhin et al., Augmented MPM for Phase-Change and Varied Materials (2014)](https://alexey.stomakhin.com/research/melt.html).
  Establishes the coupled MPM/heat/phase-change approach. This implementation
  is a collocated APIC variant, not a reproduction of that paper's staggered solver.
- [USGS: how lava flows cool](https://www.usgs.gov/observatories/hvo/news/volcano-watch-how-do-lava-flows-cool-and-how-long-does-it-take).
  Supports distinguishing a solidifying surface from a long-lived hot interior.
- [USGS: cooling and vesiculation of Alae lava lake](https://pubs.usgs.gov/pp/0935b/report.pdf).
  Physical thermal data, with composition and porosity limitations.
- [USGS: glass transition in basalt](https://pubs.usgs.gov/publication/70011747).
  Thermal stress, relaxation and fracture are coupled processes.
- [USGS: obsidian](https://www.usgs.gov/news/volcano-watch-obsidian-a-scarce-commodity-hawaii).
  The obsidian branch is composition dependent.
