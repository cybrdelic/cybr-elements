# Lava rebuild 38 — incomplete visual result

No final image or video has passed review. The previous material-37 render
remains available as a rejected study. The public page now reports measured
progress separately from final media, with fixed-camera CPU diagnostics.

## Repaired and checked

- The fracture stress update used inconsistent residual-stiffness floors.
  A saturated nonlinear trial could amplify stress and heat catastrophically.
  Equivalent saturated trials now produce matching finite responses.
- The finite inlet lacked an end-face collision, then mishandled slightly
  penetrated corners. Both cases have independent collision regressions.
- Enclosed inlet surfaces were radiating to cold air. They now exchange heat
  with a metered hot wall. Ground beyond the nozzle can be a finite rock bed,
  with equal/opposite heat exchange and checkpointed temperature.
- A pressure case exhausted 100 Newton iterations. Exact minimization along
  the existing Newton direction solved that captured system in 16 iterations
  at a residual of approximately 1.53e-9. Tolerances were not weakened.
- Initial volume used a binary cell-center mask, baking steps into the free
  boundary. Volume quadrature reduces initial volume error from 0.98% to
  0.0026% on the coarse case; the finer initialization is within 0.011% of
  an independent column integral. Its geometry visibly improves.
- Checkpoint writes prepare both data and metadata before replacement; loads
  reject mismatched times. Source schedules and substrate state resume with
  the cache. A disk reserve stops new steps before the drive fills.
- Melting connections are counted separately from fractured solid edges.
- The power-creep fallback previously over-relaxed an oscillating map. The
  revised damping passes scalar return-map comparisons without changing the
  constitutive equations or acceptance tolerances. Whole-scene performance
  is not yet established.
- Thermal preflight rejects oversized heat intervals before nonlinear
  mechanics. Its trials are completely rolled back. With/without preflight,
  accepted positions differ by 1.8e-18 m, enthalpy by 2.4e-10 J/kg, and the
  substrate temperature is identical. The controller retains its chosen
  timestep through checkpoint/resume instead of restarting at the maximum.

## Tests that did not establish success

- A 0.1 s step at the 5 s cooling state differed from two half-steps by about
  1.72 K, exceeding the 0.5 K local temperature tolerance. Fixed-step caches
  are diagnostics, not temporally validated production results.
- Startup and resume completed 0.2 s. The previously stalled 5.0-to-5.1 s
  interval now passes in seven accepted intervals, after three thermal
  preflight rejections. Its largest accepted normalized error is 0.715 and
  the test took 123 s. This is local validation, not an accurate history
  before 5 s for the older fixed-step source used by that particular test.
- The separate `validated-flow` run continues the accurate startup history
  and reached 4.184148 s before its 600 s wall budget. Its accepted states,
  substrate ledger, ancestry and temporal coverage pass. The requested 8 s
  interval is incomplete, with zero broken edges and no open fractures.
  Maximum thermal balance residual is 2.47e-11; mass error is 8.74e-19 kg.
- Fixed-camera CPU frames of that new run remain visually rejected: the
  body is connected, but it has reconstruction bands and no open cracks.
  These are not approved geometry or motion for the sigil shot.
- TR-BDF2 greatly improved the independent scalar heat ODE test but failed
  its nonlinear stage on the coupled grid. It is experimental and unselected.
- The corrected fixed-step flow reached 7.7586 s, with maximum damage 0.9788
  and no fractured solid edges. It then paused at its computation limit.
  A high damage value is not proof of a visible, open crack.
- Normal-pressure GPU solve: CPU 6.53 s, warm CUDA 7.73 s. The captured
  friction case was also faster on CPU (0.578 s versus 1.75 s). These are
  case-specific measurements, not a general claim that GPU MPM is slower.
- Three additional coupling experiments did not sufficiently reduce global
  iterations. Damped Anderson, longer-history Anderson, and a bracketed
  local creep-return target were reverted from the production solver. The
  isolated return-map derivation remains a labelled experiment.

## Cooling timescale screen

An independent 1D finite-volume enthalpy calculation uses 6 mm of lava over
12 mm of finite rock, with radiation/convection at the top and latent heat.
The finer case forms coherent material at the top around 10.975 s and reaches
1000 K at 38.85 s. Halving the timestep changes the recorded top temperature
by at most 0.23 K; halving the cell size changes it by at most 6.15 K.

This omits lateral cooling, flow, the hot inlet, mechanics and gas. It cannot
certify the 3D thermal discretization. It shows why an 8 s test window is not
adequate evidence for the requested mature upper crust. The cold bed starts
forming a lower crust first. The full 3D thermal boundary and surface still
need a spatial comparison; more render samples cannot establish that.

## Remaining gates

Finish a temporally controlled crust-forming sequence; demonstrate actual
open fracture and sustained flow; establish spatial convergence; review the
same geometry through motion; then add verified smoke/heat coupling and
Mitsuba optics. The current specimen is a centimetre-scale mechanism test,
not the final Cybrdelic sigil shot.

The publication helper requires exact cache/image hashes, hot-state ancestry,
physical and temporal checks, measured crack openings, and an explicit visual
review covering geometry, motion and resolution. None of the current lava
caches is approved for final publication.

Evidence lives in `rebuild-38/`; `progress-38.json` on the public review page
contains compact test records. CPU images were inspected individually. The
local page, manifest and image returned HTTP 200. Browser screenshot QA was
unavailable: the in-app automation failed to initialize, the Playwright CLI
was not cached, and headless Edge produced no screenshot.

Disk recovery removed 201 reproducible AOV buffers (760,390,830 bytes), plus
two prior render intermediates earlier in the turn. Simulation checkpoints,
source files, displayed images and videos were preserved.
