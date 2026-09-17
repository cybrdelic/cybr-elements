# Lava simulation: CPU implementation and evidence

This directory contains a new three-dimensional simulation. It does not load
the old magma/lava/basalt stage meshes. It is under validation, not approved as
a complete production lava solver or a photorealistic final shot.

## Implemented

- Quadratic APIC particle/grid transfer; particles carry mass, enthalpy,
  deformation, elastic stress, thermal volume strain and tensile history.
- Implicit three-dimensional momentum solve. A Newtonian melt and a Maxwell
  crystal network act in parallel. Temperature changes viscosity; latent heat
  and the solid fraction come from one enthalpy law.
- Cell-averaged bulk response, with separate pressure degrees of freedom for
  separated material components. The nominal bulk and elastic moduli have not
  been reduced to make explicit timesteps affordable.
- Nonlinear implicit Fourier heat conduction, surface radiation, convection,
  and contact with a specified cold substrate. Viscous/contact dissipation
  returns heat to the particles. There is no extra cooling sink or time scale
  multiplier in the equations.
- Thermal contraction and an energy-regularized tensile damage law. Material
  connectivity is created as it solidifies; sufficiently failed bands lose
  connectivity. Disconnected components receive separate grid velocity fields.
- Equal/opposite unilateral contact impulses solved inside the implicit
  material step using a nonnegative dual solve. Separation does not create an
  attractive contact impulse. Interfragment contact is currently frictionless;
  a validated Coulomb cone solve remains outstanding. A no-slip substrate and
  material-point collision constraints provide ground contact.
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
9. The reconstruction cannot resolve cracks smaller than particle spacing.
   No procedural crack displacement is substituted for that missing resolution.
10. Obsidian requires a separate composition/glass-transition model. It is not
    produced by allowing this basalt material to cool for longer.
11. The 10 mm versus 5 mm material-grid comparison failed its early-flow gate:
    RMS speed differed by 19.48%, exceeding the declared 15% threshold.
    **Do not start a final rendering batch or call the requested full sim done.**

## CPU evidence

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
