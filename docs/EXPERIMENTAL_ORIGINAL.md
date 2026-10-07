# Experimental Original publication

Tested numerical source: `5ce5a7f80e52e99fb20db751aa6ed9d9e17f2034`.
Public base: `af796b9ec707e774b7a96be8a7dc4faa9f5db2ee` (merged PR #12).

The focused follow-up adds an upper-depth tangential correction and repairs
Sigil source age and Stop/Restart controls. Its two numerical runtime files are
byte-identical to the tested source. Publication adds separate documentation,
an accurate experimental notice and loader cache tokens. Private overlays,
field dumps, browser profiles, environment files and unrelated experiments
are excluded. No heat budget, threshold, transport or rendering is retuned.

## Checks and limits

The numerical candidate passed 493 CPU cases across 69 suites, nine package
tests, four asset-tool tests and 184-file runtime closure. Publication repeats
the CPU/package/closure checks after notice and cache changes, without GPU work.

Native startup and shared-face shader consistency passed. A native half-float
fixture changed 204 tangential slots with zero changes to normal velocity,
source alpha, interior atlas cells, floor slots and interior center divergence.
Sigil advanced through 8.4333 seconds beyond its former attempted-7.8-second
boundary failure. At 8.4 seconds, center eta/rho was 0.0576788 and midpoint
eta/rho was 0.0644853, passing unchanged 0.1 eta and 0.2 rho limits.

One actual conservative transport step closed signed fuel/heat-proxy/soot
inventory plus outward boundary flux with relative errors
[-1.31424e-7, -4.93066e-8, 0], within 16 Float32 epsilons. This excludes source,
reaction, diffusion and oxygen stages; it does not certify the full reacting
or material system. Native controls verified Restart at time zero, its first
step age/clock at 1/30 second, positive pilot/starter uniforms, both uniforms
zero after Stop, and continued accepted advancement after Restart.

Sustained ignition remains unproved. Bounded native planes had zero sampled
soot and gas temperature below the fresh ignition threshold. Thermal/source
delivery limits remain. No wattage, duration, geometry or threshold tuning is
included. Native Fireball, Sooty, long-session and mobile checks are incomplete.

Coast median GPU times were 1.10 ms for the upper solve, 0.0184 ms for apply/copy
and 3.21 ms per interior cycle. Whole-projection CPU wall median was 57.5 ms
with private observer and readback overhead. Physical clock advancement was
about 0.26–0.51 native seconds per wall second in bounded phases. These are
single-device observations, not a matched total-projection GPU comparison or
a sustained performance claim. Real-time performance remains unresolved.

## Previous versions and rollback

`?runtime=v5` selects the preserved previous Original runtime. Its numerical
files remain unchanged. The default is the tested experimental follow-up.

The prior v6 candidate `cb2fc8d2395a8b10851ba1ed4464414cdb0d2c36` is preserved
separately. Archive-backed Site version 6 remains available from source
`6e1ffcf5ad37c7b8d165b1ddb663f10aa4aa99f4`, archive SHA-256
`f68151e544e6db260da96b61728b87085cb7b122b6fda9598dd226e03e28756a`.

Saved Site version 5 remains independently available for whole-site rollback:
source `0d1f9cad31b48f7ad1a236bbf6554ff265dc9cfe`, archive SHA-256
`a1a553b2a0a7b54e1d3cfe176525a6f071b0672be0bc1bfaed1642e9ff62bc49`.

## Fireball startup typing correction

The blast domain generated integer `6` coefficients multiplied by floating-point
pressure differences, preventing Original Fireball startup. The focused follow-up
emits `6.0` instead. Numeric values, solver equations, acceptance/CFL limits,
clock, sources, reaction and render quality are unchanged. All normal/object
shader stages retain their prior bytes.

The native-tested source is `1c5a66f3efe55c974a8628f6b55ac23e5c38f8ca`.
CPU/static checks cover 76 preset identities, five domain forms and 718 generated
shader stages. Full validation passed 496 CPU tests across 70 suites, nine
package tests, four asset-tool tests and the 184-file runtime closure. A brief
RTX 4060 Laptop / ANGLE D3D11 check linked all 64 fine-flow programs, advanced
Fireball to 0.1125 physical seconds with center/midpoint eta 0.0648961 and rho
0.1180095, and passed deliberate transport-failure rollback with zero changed
accepted-state values. This verifies startup and a short prefix, not sustained
Fireball behavior or realtime performance. The separate transport-stencil and
decision-batching experiments are not included.
