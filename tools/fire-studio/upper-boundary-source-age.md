# Upper-depth tangential completion and Sigil source age

This local candidate follows published experimental source `82c24d43bb9b008fc525949093058819ff61d370`.
The parent reports PR #12 merged as `af796b9ec707e774b7a96be8a7dc4faa9f5db2ee`
and Site v6 deployed successfully at 2026-10-07 20:02:01.533 UTC from
`6e1ffcf5ad37c7b8d165b1ddb663f10aa4aa99f4`. That publication, the previous-v5
runtime option and the independently saved whole-site v5 rollback are preserved.
This follow-up is not published or native-validated.

## Boundary operator and integration

The captured Sigil failure traced 74.5% of its midpoint residual to the upper
depth plane or its clamped extension. Interior pressure is zero there, so further
interior cycles cannot repair its tangential divergence. The correction solves
`D W^-1 D^T psi = S - D u` on that plane, with the actual stored-slot forward
divergence, clamped upper faces, impermeable floor and
`W = diag(extent.x^2, extent.y^2)`. Applying `W^-1 D^T psi` minimizes physical
velocity energy. The rectangle and two outlet edges are independent blocks;
the doubly clamped corner has no tangential degree of freedom. A nonzero source
there remains unrepresentable and is still exposed by unchanged acceptance.

Four fixed 2D multigrid cycles use Float32 pressure, filtered restriction,
bilinear prolongation, two pre/post smoothing sweeps and 48 coarsest sweeps.
This is an approximate solve of the replay-supported operator, not the exact
CPU spectral solver. The default hierarchy has eight levels and adds 6,113,600
requested texture bytes (5.83 MiB), including one half-float upper-plane buffer.
It adds 390 small-plane draws for the initial application, plus one application
and one tile copy for each later interior pressure cycle. Native cost is unknown.
There are no added CPU readbacks or full-volume velocity targets.

Only the upper plane's x/y normal-face components are corrected. Its z component
and source alpha are read again from the current interior solve for every
application; the correction never caches an earlier cycle's normal velocity.
The floor y component and rows below the floor remain unchanged. Interior atlas
tiles are not copied or overwritten. Tangential RHS/pressure is computed once
per candidate projection because interior pressure cycles cannot change those
components on the upper plane. Center/midpoint sample support, 0.1 eta and 0.2 rho
targets, original interior cycle/admission budgets, atomic rejection, transport
fluxes, scalar reconstruction and rendering equations remain unchanged.

## CPU evidence and limits

The final candidate passes all 493 CPU cases across 69 suite files, all nine
package tests, four asset-tool tests and runtime closure for 184 files, build
`dc69d528871335a3`. No browser or GPU is started by these checks.

An independent face-incidence matrix matches the emitted production GLSL
operator, including both clamped edges and the floor. Tests establish physical
energy minimality for the exact operator, representable-source closure,
unrepresentable-corner behavior and signed fuel/heat/soot inventory closure.
Control fixtures verify one boundary RHS per projection, current-normal retention,
correct tile bounds and unchanged failure handling. Native shader execution,
Float32 contraction, copy behavior, timing and visual quality remain unverified.
Both copy buffers use RGBA16F, matching the sized-format component constraint in
the [WebGL 2 specification](https://registry.khronos.org/webgl/specs/latest/2.0/#BACKWARDS_INCOMPATIBILITY).

The production four-cycle schedule modeled in Float32 reduced captured upper
residual L1 from 344,233.41 to 1,654.52 after actual half-float velocity rounding.
The frozen-field midpoint replay gave numerator 89,506.828125, eta/rho
0.02607189837; center numerator remained exactly 92,381.421875 and all interior
arrival velocities remained identical. The previous native midpoint eta was
0.100804730043. This CPU replay passes the unchanged targets on one preserved
field; it does not prove live Sigil advancement beyond 7.8 seconds or conservation
of the full reacting/material system.

## Sigil source clock and finite ignition budget

Legacy Sigil selection now begins a finite starter at age zero. Wood receives
elapsed time relative to that explicit ignition event, so Restart or relight
restarts its authored stroke clock consistently. Stop ignition is visible and
disables both the generic pilot and authored starter; previously `!freeMode`
kept the authored starter enabled after the brush was stopped. Other wood source
equations and gas/power source timing retain their existing implementations.

No watts, duration, source shape/position, thermal coefficient, ignition threshold
or rendering parameter is retuned. The generic pilot remains 120 kW for at most
4 seconds: 480 kJ. At scale four and its center, the no-cooling, fuel-free upper
bound is 0.1971497 normalized temperature rise (236.58 K), below the 0.35 fresh-gas
threshold (420 K rise). The corresponding ideal lower energy bound is 852.14 kJ.
Transport, cooling and fuel heat capacity reduce the pilot's isolated effect.
The authored starter supplies a separate unchanged 280 kW/m2 budget for 1.2
seconds per stroke to gas and substrate. Its combined delivery and material
thermal state were not captured, so correcting source age does not establish
ignition. Actual positive burn and temperature evidence are still required.
