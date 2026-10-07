# Shared normal-face reconstruction candidate

This unpublished CPU-only candidate follows rejected release candidate
`9d6e881ae39008a6e4e6ac7a96d6de64f7905cdc`. Live v5 remains unchanged.
Native shader compilation, actual Sigil advancement and improved pacing are
unverified. The expected fetch/timing improvement is a hypothesis.

## One scoped change

`OriginalFineFlow.faceReconstructionGLSL` generates one normal-face reconstruction
and passes that exact string to the intensive scalar advection class. It is used
by the actual oxygen predictor, the reverse corrector, the corrector's limiter
backtrace and midpoint acceptance. The velocity predictor and renderer retain
their existing sampling. F/E/S continue to use the unchanged Hancock face fluxes.

Each normal component is linear between its lower and upper transport face slots
and constant along tangential coordinates inside a cell (lowest-order RT0
reconstruction). Its analytic divergence is the sum of those three normal slopes.
Cell widths are 1/nx, 1/ny and 1/(depth-1), with half-width endpoint depth cells.
The existing upper-face clamping, physical box clamping, floor zero velocity and
floor no-penetration rules are retained. Evaluation points are not dropped or
excluded to make acceptance pass. Nonzero divergence in an unconstrained boundary
shell remains a real error. Outside the physical box, the derivative follows the
same clamped field extension used by the actual intensive scalar trajectory.

The midpoint source uses the pressure RHS's unchanged cell law at the containing
cell. It does not recompute that nonlinear law from interpolated fuel/temperature.
Reaction, expansion cap 64/s, conservative transport, grid size and the pressure
operator are unchanged. The center/midpoint rho 0.2 and eta 0.1 targets, residual
controller, admission limits, readbacks, storage and rollback rules are retained.
No extra target or texture is allocated. Shader startup receives the shared
snippet directly from the fine-flow owner.

## Diagnostic consistency versus physical failure

The former diagnostic applied a whole-cell forward difference to a collocated
trilinear velocity field. That can report zero for a discrete-curl field whose
actual interpolant has nonzero pointwise divergence. Changing only the diagnostic
would leave the actual scalar trajectory inconsistent. This change updates both.

Interpolating cell sources is also different from applying the nonlinear source
law to interpolated chemistry. The CPU example with fuel 0/4 has a 0.293333 source
commutator even though its solved cell residual is zero. The new source/velocity
representation reproduces the solved cell source throughout each cell.

This does not excuse real divergence: an affine divergent normal field, an
unconstrained open-boundary shell, a floor-cell normal ramp and nonfinite metrics
still fail the unchanged acceptance predicate. Half-float rounding of a
manufactured discrete curl creates divergence -0.00018310546875; it is measured
and rejected under the test's unchanged normalization rather than rounded away.

The CPU reference checks 3,150 fluid points of a discrete-curl field, shared-face
normal continuity, floor behavior, depth endpoint widths, clamped open faces,
source-law consistency and a full-volume divergence theorem. Existing independent
F/E/S boundary-ledger and runtime rollback tests remain required. These tests do
not replace native shader/half-float/visible-motion evidence.

## Limits and next gate

Piecewise-constant tangential reconstruction is less smooth than the old
trilinear field. Oxygen trajectories and limiter donors change; visible flame
and smoke quality require review. The main velocity predictor is still the
existing predictor followed by pressure projection, not a claim that every
interpolation in the application is pointwise divergence preserving.

The post midpoint field lookup count is expected to fall from roughly 56 to 10,
while serial residual readback architecture is unchanged. Prior midpoint waits
were 11-16 ms and feed projection stages about 32 ms. A proposed measurement gate
is midpoint below 6 ms and at least 7 ms less feed projection time. Those are
targets, not measured improvements or a promise of viable frame speed.

After parent agreement, bounded native validation must compile the real shaders,
compare old/new diagnostic components on captured fields, reject true failures,
advance Sigil beyond 7.8 seconds, verify actual boundary closure and report matched
stage/frame timing and visual quality. No promotion is implied by CPU success.

## Publication status update — 2026-10-07

The native candidate compiled but retained the known Sigil stop and slow performance.
The user requested experimental publication with those defects accepted. Earlier
CPU-only authorization and pending-native notes above describe their checkpoint,
not the later publication instruction. Safeguards remain unchanged. See
[the final validation and rollback record](../../docs/EXPERIMENTAL_ORIGINAL.md).
