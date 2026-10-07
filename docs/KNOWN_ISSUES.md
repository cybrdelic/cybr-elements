# Known issues and scope

This consolidation preserves the current Fire Studio and offline implementations.
It does not close existing numerical, appearance or performance findings.

## Fire Studio

- **Thermal and source behavior:** gas and wood use reduced, accelerated visual
  models. Preset ignition, exposure and burnout can vary. Recent owner repairs
  are included, but they do not certify all fuel/color/power combinations.
  Original free fire deliberately shares the plume's broad inlet, cold-vapor
  ignition, slower buoyancy and stronger confinement. Its height, readability
  and wider visual acceptance remain open. A scoped ambient-force unit correction
  has passed bounded actual browser motion/control checks for Original free fire
  and fireball; those checks do not certify every fuel or appearance combination.
  A subsequent scoped force-peak limiter reduces sampled peak speeds in matched
  free-fire and fireball captures. It retains weaker eddies, but the free-fire
  plume can still grow taller and the wider uncontrolled-motion visual goal
  remains open. It is not a whole-volume stability or conservation guarantee.
- **Power appearance:** smooth or overbright packet heads and limited fine flame
  breakup remain visual concerns. Original and Volume use their own flow and
  optical models; matching controls do not imply matching pixels. Fireball's
  authored packet spin and warm-gas turbulence remain active; the unit correction
  produced a smaller motion change for fireball than for free fire.
  The peak-force mitigation retains the smooth packet head and authored travel;
  it does not replace the optical model or promise fine breakup in every scene.
- **Original fine pressure and transport:** compatible coarse pressure boundaries
  and fine-grid sampling are corrected, but point restriction still misses fine
  velocity modes. A same-stage torch measurement reduces coarse mean residual
  from 0.042674 to 0.007294 per second, while fine active-interior mean residual
  stays near 2.75 per second. This is not an all-preset or fine-flow fix.
  Semi-Lagrangian scalar transport plus a universal divergence factor is not
  demonstrated conservative: isolated same-input replays add fuel/soot/reaction
  below numerical ceilings. Universal dilution is therefore not enabled.
  [Measured scope and provenance](VALIDATION.md#original-compatible-pressure-boundary-and-sampling).
- **Refined/adaptive flow:** the coarse/fine path is experimental and can fall
  back to dense flow immediately. It has not established a general speed gain.
- **Sparse:** pooled chemistry retains dense fallback resources. Sparse adds
  roughly 96 MiB to 384 MiB of dense chemistry backing, before other resources.
  Capacity/coverage fallback can erase any sparse-storage advantage.
- **Performance:** smoke-heavy scenes can exceed the 16.7 ms budget for 60 FPS.
  Prior short windows and native stage timings are not a current browser or
  mobile performance certification. Cleanup alone does not accelerate rendering.
  Warmed, instrumented matched captures show throughput changes below one percent
  for the peak-force mitigation. Synchronous image readback is included; these
  short desktop observations are not a general performance certification.
- **Startup and compatibility:** WebGPU presence does not guarantee a usable
  adapter. Limits, driver state, memory and contention can prevent startup.
  Keep recovery controls and test actual supported scenes on the intended device.
- **Material/contact detail:** finite wood/beam models and tracer embers are
  approximations. Prototype props do not establish arbitrary fracture,
  fragment-to-fragment contact or firebrand ignition.

Volume currently enables the owner's accepted cached pressure-source path.
Sparse keeps it opt-in. The owner retained a Sparse-house startup timeout even
though isolated repeats succeeded. That record is an existing reliability concern,
not evidence that cleanup introduced a failure.

## Offline and historical workflows

The delivered films are intact. Some historical release assets were already
missing locally, including water-viewer mesh frames. The retained v0.1.0 manifest
and downloader provide a verified-metadata restoration route; those assets are
not bundled into the current tree. Full rerendering requires preparation of new
solver/frame caches and the documented renderer/dependency environment.

Water contains an editorial opening/overlap and a forward native simulation
segment. Earth, Ice and Lava combine authored assembly with rigid release.
Ice/Lava do not implement a general thermodynamic phase-change or liquid-lava
solver. Lightning and Telekinesis are authored visual effects with source-derived
geometry. Several historical authoring scripts retain machine-specific paths;
inspect inputs and use a new output revision before executing them.

## Validation status

Source/asset identity, real media decoding, CPU source preparation and package
dependency checks can verify preservation without occupying a GPU. Live
Original/Volume/Sparse startup, controls, pixel inspection and current performance
must be checked separately. Bounded desktop source/control preservation checks
and the Original motion correction have completed; see [validation](VALIDATION.md).
Actual Android hardware, whole-volume stability and sustained performance remain
unverified. Desktop Chrome touch input is not Android hardware certification.

Any new regression found in that run blocks promotion. Existing accepted defects
are documented rather than silently rewritten. See [validation](VALIDATION.md).
