# Original residual-budget predecessor

This document records rejected residual-budget candidate
`9d6e881ae39008a6e4e6ac7a96d6de64f7905cdc`, which follows frozen filtered candidate
`d9d4e1862a612cbe273fc221eede62a58f444995`, which repaired rejected compact
candidate `cd8dab96c21cbee1e69ca88c36f8d27aa4145608`. Live v5 is unchanged.
The following native observations apply to that predecessor. It was rejected
after Sigil failed at 7.8 seconds and pacing remained about 6-10 FPS. The current
shared reconstruction change is described in [normal-face-reconstruction.md](normal-face-reconstruction.md).

An independent CPU translation of the exact 96x96x33 blast subhierarchy, with
compatible manufactured RHS `b=L*p`, found that point residual restriction plus
the rediscretized coarse correction amplifies a compact pressure packet. L1
residual ratios across four V cycles were 1.659, 2.517, 5.051 and 9.915. Fine
Jacobi alone decreased residual; floor extension alone did not repair the mode.

Restriction now applies the separable binomial filter `[1/4,1/2,1/4]` only on
coarsened axes, followed by the same mapped interpolation. The shader combines
those operations into four weights per reduced axis. Unchanged axes sample the
same index directly. Raw residuals outside the fluid mask remain zero;
pressure's floor Neumann extension remains confined to pressure sampling.
This is a filtered corrective experiment with the existing rediscretized coarse
operator, not a variational/Galerkin proof. The filtered transfer is retained
unchanged. Its implementation adds no texture allocation.

The independent packet fixture reaches residual ratio 0.0534809 after four
cycles and 0.00542940 after eight diagnostic cycles. Floor, smooth-depth and
random fixtures have decreasing residual and error energy. The smooth-depth
fixture is still at 0.150035 after four cycles. Unresolved results cannot be
accepted. The rho limit remains 0.2 and eta remains 0.1 at both center and actual
backtrace midpoint. The 512 transport-step cap and velocity remain unchanged.

Four V cycles remain the normal correction budget. After that, at most two
additional cycles are admitted when the measured controlling residual is within
1.6 times its target, contracts by at least 5%, and the observed contraction
predicts reaching the target within the remaining cycle and time budget.
The extra-work admission budget is 48 ms, using measured synchronized pass cost.
Each extra cycle is measured and exits immediately on actual acceptance.
Stagnation, growth, nonfinite metrics, distant residuals and exhausted budgets
still reject. This is a conditional residual controller, not a global six-cycle
loop. A GPU command/readback can overrun its estimate: 48 ms is an admission
guard, not a hardware deadline. The strict work bound is six V cycles.

For the default and Fireball hierarchies, each V cycle has 90 multigrid draws;
the maximum is 540 rather than 360. Additional acceptance/reduction/copy draws
are separate. Sigil's observed final correction/acceptance work was about 21 ms,
so its 0.100183 midpoint error predicts one extra cycle under this controller.
That prediction is not evidence that native Sigil now advances.

The preceding pressure is reused only as an initial guess in a separate lazy
R32F plane, independent of transport's aliased storage. The current RHS is built
normally. The actual half-float center and midpoint metrics must both pass before
a zero-cycle exit; otherwise the unchanged filtered solver corrects the defect.
A guess that worsens current divergence is discarded in favor of zero pressure.
Restart and any candidate/runtime failure discard acceleration history.
Only fixed pre-projection L1/Q sums are cached within a call; post metrics are
always measured afresh. Repeated midpoint checks skip recomputing the fixed
pre-backtrace field. Rejected candidates skip the unused transport-rate reduction.

Requested default flow textures remain 266.927 MiB before history allocation;
history adds 28.125 MiB, yielding 295.052 MiB. Fireball history adds 36 MiB.
These are requested texture bytes, excluding driver overhead and other runtime
systems. Warm reuse can reduce cycles/readback fences; a changing or rejected
guess can add a probe. CPU tests do not establish a native speed improvement.

Projection now throws before returning an unaccepted velocity. Transport checks
both convergence and current storage ownership. Its schedule is validated before
diffusion or auxiliary state updates. All candidate passes finish before wood,
fuel, vorticity, ability clocks or main fields advance; those passes retain their
original accepted VF/chemistry inputs. If a candidate pass fails after diffusion,
both chemistry aliases and framebuffer attachments roll back. The runtime
restores its clock, stops the loop, disables Resume and shows the rejection.
Failed pressure/RHS and source texture references remain available for diagnosis.
Explicit Restart resets the simulation. General failures in the preexisting
auxiliary/main stages still use the preexisting failure handler.

The native first-failure run saved reductions, not complete field bytes. At
0.045 seconds, center residual ratios were 0.337, 0.184, 0.164 and 0.214. The
previous accepted fine pressure was zero, so retaining that pressure would not
alter this first failure. Expansion is nonnegative and capped at 64/s; the open
sides/top make the pressure problem compatible with net expansion. The
manufactured failure needs no chemistry or expansion, establishing an operator
defect independently of the precise native RHS.

The frozen d9d4e186 native diagnostic ran for 70.556 seconds on the RTX4060.
Fireball reached age 3 and Sooty Plume age 5 with acceptance passing. A separate
injected Fireball transport failure preserved age 3 and 1,179,648 sampled VF/chem
values exactly. Sigil rejected attempted age 7.5, restoring age 7.466667:
center eta 0.036523, midpoint eta 0.100183. Its midpoint eta fell from 0.124933
at cycle three to 0.100183 at cycle four.

Observed feed projection GPU times were 40.14 ms Fireball, 28.11 ms Sooty and
41.05 ms Sigil. Conservative transport was 8.56, 17.69 and 28.45 ms, respectively.
Named screen-render GPU work was 1.42, 0.86 and 1.01 ms; full feed loop frame
wall times were about 167, 106 and 172 ms. They are distinct measurements.
Per-step CPU readback blocking was 79.0, 54.4 and 72.8 ms and overlaps queued GPU
work: do not add it to GPU elapsed time. Midpoint/readback waits averaged 14.36,
10.63 and 13.54 ms. Center waits include prior multigrid/apply/reduction work.
Short queried/streamed intervals are not sustained benchmarks. This performance
and the Sigil failure still block release of the numerical candidate.

## Optional boundary-accounted material ledger

Call `fineFlow.enableMaterialLedger(true)` for a diagnostic window and
`fineFlow.readMaterialLedger()` after pausing. It is disabled by default, with
zero extra per-step draws or storage until enabled. Its additional requested
default storage is 492,432 bytes (0.470 MiB); Fireball uses 314,672 bytes.

The ledger saves full-volume F, E=(1+F)T and S inventories before and after one
actual conservative transport. For every actual directional substep, a boundary
atlas evaluates the same production Hancock face function against that exact
pre-sweep state. Signed outward flux includes both outer faces, endpoint
half-depth areas and the impermeable floor. GPU reductions and small ping-pong
totals accumulate flux without per-step CPU reads. An explicit paused read
returns `after + outwardBoundaryFlux - before`, relative closure and finite flags.
Totals belong to the latest audited transport and become unavailable on a new
projection, Restart, failure or disabling the ledger. They exclude diffusion,
oxygen, source and reaction stages, which need their own separate budgets.

The CPU atlas/reduction model closes 36 signed open-face F/E/S cases with maximum
relative closure 1.86e-7 and a closed contracting case at 5.97e-8, under the
unchanged 16 Float32 epsilon policy. Native compilation and actual open-flow
closure remain pending. Each audited transport adds two full-volume inventory
reductions and one boundary reduction/accumulation per substep; profile ledger
overhead separately from ordinary solver pacing.

No publication, merge or deployment is authorized by this CPU checkpoint.

## Publication status update — 2026-10-07

The native candidate compiled but retained the known Sigil stop and slow performance.
The user requested experimental publication with those defects accepted. Earlier
CPU-only authorization and pending-native notes above describe their checkpoint,
not the later publication instruction. Safeguards remain unchanged. See
[the final validation and rollback record](../../docs/EXPERIMENTAL_ORIGINAL.md).
