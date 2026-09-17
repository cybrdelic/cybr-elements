# Lava review 26 — rejected as a visual replacement

The published solver-25 frame is still a rounded, continuous cap with a red
underside. It does not depict the requested heavy fractured basalt over a
moving molten interior. Component checks never established that appearance.

## What was checked and changed

- A 16 cm continuous lobe now has a thermal profile from a 1D enthalpy solve,
  with radiation, convection, latent heat and a hot deep reservoir. Mapping
  this profile onto a stress-free initial lobe is an approximation; it does
  not simulate its prior 3D emplacement or cooling stress history.
- The first screen cooled the supply inlet itself, making the prescribed
  flow pull on a solid plug. Its concentrated upstream damage was an inlet
  loading artifact. The corrected initial condition blends enthalpy to a
  molten supply reservoir before the inlet plane.
- Source layers now meter partial-cell volume at 0.25 s intervals. The old
  spacing/speed interval was 2 s at this scale, too late to screen continuous
  replenishment in short runs. This source-time approximation still requires
  temporal convergence; smaller source layers are not additional full cells.
- A proposed bilateral starting estimate for the unilateral pressure solve
  matched the captured solution but was slower (0.916 versus 0.795 s), with
  the same six iterations. It was removed from the live solver. The exact
  experimental module and numerical comparison remain in `pressure-proof`.
- A native Mitsuba triangle-atlas path removes Python callbacks at shading
  samples. It bakes solved temperatures and material-attached optical pores;
  it does not create fracture geometry. A 320 x 200, 4 spp CPU proof took
  2.22 s including baking and denoising. This timing is not a like-for-like
  speedup measurement against the earlier 640 x 400 render.

## Actual outcomes

| CPU screen | Accepted time | Peak damage | Open fractures | Decision |
| --- | ---: | ---: | ---: | --- |
| Cooled inlet | 0.020 s | 0.880 | 0 | Reject: loading a solid inlet plug |
| Hot inlet, old source interval | 0.240 s | 0.000392 | 0 | No visible breakup demonstrated |
| Hot inlet, partial source layers | 0.500 s | 0.001582 | 0 | Reject as a visual replacement |

The last two runs hit their 120 s CPU screening deadlines. They do not prove
that fractures will never form; they failed to demonstrate usable fracture
within the tested interval. All three screens remain saved with their actual
solver hashes. The failed pressure experiment was subsequently reverted;
existing case hashes must not be rewritten or resumed as if unchanged.

The last geometry image was directly inspected. It still has one smooth cap
and no separated plate edges. The native optical proof was also inspected:
its pores are more apparent, but the same rounded shape remains. Neither was
promoted to the website. No GPU was used and no new final video was rendered.

## What remains unresolved

1. A suitable lava-flow setup must generate distributed crust loading and
   actual plate separation, not stress at a prescribed inlet or merely carry
   one intact cap downstream. Boundary setup is part of this problem.
2. The present resolution and regularized fracture representation have not
   demonstrated open, contacting basalt plates at a useful rate. Increasing
   render samples cannot repair that geometry.
3. The melt and rock laws are references from different experimental regimes;
   the phase rule, fracture parameters and porosity are not calibrated as one
   lava material. Dense rock creep at confinement is not a validated model
   of partially molten, vesicular crust at atmospheric pressure.
4. Full motion, gas release, smoke and sustained surface renewal remain
   unverified in this setup. A still image must not stand in for those results.

The next visual acceptance must be an untextured CPU sequence showing open
cracks, finite plate thickness, molten interior flow and plausible plate
contact. Until that exists, this remains unfinished.

## Physical references considered

- [USGS: pāhoehoe and ʻaʻā](https://www.usgs.gov/news/volcano-watch-pahoehoe-and-aa-lava-flows): localized toe breakouts differ from widespread crust breakup.
- [Fracture and surface crust development, Tenerife](https://www.sciencedirect.com/science/article/abs/pii/S0191814100000894): layered crust, thermal contraction and flexure create fractures at different scales. This study is not claimed as a calibrated implementation here.
- [Mitsuba area emitters](https://mitsuba.readthedocs.io/en/latest/src/generated/plugins_emitters.html): native texture emission used with a unique per-triangle UV atlas.
