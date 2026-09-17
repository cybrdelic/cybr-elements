# Acceptance contract

Target: a moving molten mass that forms, deforms and fractures a heavy basalt
crust, with localized incandescent openings, on a pitch-black backdrop. The
geometry, temperature, phase and motion must belong to the same evolving state.

1. **Physical mechanism.** Start hot and intact. Integrate heat and mechanics
   together, record inlet mass/enthalpy and boundary work, retain an accepted
   checkpoint after any failed trial. No prepared plate layout or painted heat.
2. **Geometry.** Inspect the same camera, scale and lighting through time using
   CPU diagnostics. Broken-edge counts alone are insufficient: measure open
   faces and inspect actual separation, coherent flow and crust thickness.
3. **Motion.** Compare multiple times and a finer timestep/resolution. Reject
   particle jitter, lattice patterns, broad uniform trenches and volume loss.
4. **Optics.** Render only a cache that passed the preceding reviews. Use its
   temperature and surface without substituting a different cached scene.
5. **Publication.** `lava_acceptance38.publish` binds the selected image to the
   reviewed state hash. Failed physical checks, missing open fractures or a
   missing visual review block it. A numerical pass is never a beauty pass.

Use no more than four mechanism variants before reassessing a failed model.
Do not spend render samples, add smoke, or sculpt noise to disguise a failed
mechanism. A free-cooling control is allowed to remain intact; it cannot stand
in for the loaded lava shot. Keep progress reporting separate from final media.

Current experiments: uniform hot free-cooling control; hot grounded inlet.
The old `material-37` image is a rejected appearance study. It has not passed
this contract. Its source geometry must not be reused as a successful result.

The default driver now uses a finite rock bed, volume-integrated initial
boundary cells and adaptive step-doubling. `--fixed-step` and `--bed hot` are
diagnostic controls. Do not use them as validated final runs. A fixed-step
comparison at 5 s missed the 0.5 K local temperature-error limit. The optional
TR-BDF2 heat experiment passed a scalar ODE reference but failed in the coupled
scene; keep backward Euler with adaptive acceptance as the main method.

Pressure line minimization passed the captured failing system at the original
residual tolerance. Both normal-pressure and friction-response GPU benchmarks
were slower on this machine, so the current selected backends remain CPU.

Publication additionally requires temporal records covering the entire
accepted history from zero. A short successful startup test, damage value,
or a connection released by melting is not evidence of sustained fracture.

The thermal preflight can only reject an interval; accepted steps still pass
full coupled step-doubling. Keep the selected timestep when resuming. Its
rollback equivalence and the previously stalled cooled interval now pass.
The longer validated history currently ends at 4.184148 s, paused before its
declared target. No final render has been authorized by the evidence gate.

The cheap 1D cooling screen places coherent upper crust near 11 s and a top
below 1000 K near 39 s for its declared 6 mm layer. Those are not 3D predictions.
Validate the 3D thermal boundary and spatial resolution against an appropriate
small reference before committing to a long, finer coupled run. The current
short-duration specimen cannot demonstrate the requested mature crust.
