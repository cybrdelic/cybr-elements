# Experimental Original publication

Frozen numerical source: `cb2fc8d2395a8b10851ba1ed4464414cdb0d2c36`.
Public base: `eaba4e093aab6145212ef5d0f74394ac75c5f111` (prior v5).

The final candidate difference from the public base is curated into one commit.
Private intermediate history, raw diagnostic field dumps, browser profiles,
environment files and unrelated experiments are excluded. The candidate remains
preserved separately. Numerical code is unchanged by publication preparation;
only loader cache tokens, a visible version/limits notice and a previous-v5
runtime choice are added around it.

## Checks and their limits

The final publication checkout passed all 487 CPU cases across 68 suite files,
all 9 package tests and all 4 asset-tool tests. Runtime closure covers 184 files
with content build `41d07a98c158cb0b`. The actual loader's previous-v5 path also
passed startup, first-frame execution and disposal in the CPU WebGL fixture.
No browser or GPU run was added for publication preparation.

The frozen candidate passed 486 CPU tests, 9 package tests, 4 asset-tool tests
and the runtime closure check. The reserved GLSL identifier correction was then
checked in 31 targeted CPU tests, with all 61 assembled shader programs compared:
three changed only the identifier. Native candidate startup compiled, and shared
normal-face diagnostics agreed with the CPU reference. The native Sigil run
stopped before Fireball, Sooty or the conservation ledger, so those checks remain
incomplete. Full native validation is not a passing release gate.

The last accepted Sigil time was 7.76667 seconds. Attempted 7.8 seconds failed
midpoint eta 0.100804730043 against the unchanged 0.1 limit. The rejected state
was not published into simulation history. Four normal cycles were used and
extra-cycle admission failed its existing contraction budget. The saved Sigil
gas field had zero burn/soot and a maximum temperature around 447 K; visible
ignition remains defective.

Short instrumented windows measured feed projection 23.17 ms, feed wall-frame
97.76 ms, coast-prefix projection 33.13 ms and coast-prefix wall-frame 177.27 ms.
Waits overlap GPU work, so they must not be added together. These windows do not
establish sustained frame rate, mobile behavior or all-preset correctness.

Publication is authorized with these limitations accepted. Safeguards remain
enabled. No CPU boundary counterfactual or additional numerical change is included.

## Previous version and rollback

The version notice switches Original to `?runtime=v5`. Its fire, shader and
corrected-advection code is preserved from the public base. The v5 shader import
uses a distinct filename so both versions coexist; numerical expressions remain
identical. Other assets are shared unchanged. The candidate is the default.

Whole-site rollback is also available from saved Site version 5, source commit
`0d1f9cad31b48f7ad1a236bbf6554ff265dc9cfe`, archive SHA-256
`a1a553b2a0a7b54e1d3cfe176525a6f071b0672be0bc1bfaed1642e9ff62bc49`.
That copy is retained independently of the new publication.
