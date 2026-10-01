# Power motion and floor contacts — rc.20

This update repairs the shared source choreography in Original, Volume and Sparse. It does not replace the gas solvers. All flames are live transported combustion; no captured fire is used at runtime.

## Visible problems addressed

- Projectile endpoints previously always released a spherical burst, even in empty air.
- A 2.2-unit aftermath reservation pulled most targets toward the centre, and fan casts reserved still more space.
- Whip and crescent sources used two straight segments. Dragon breath repeatedly reset its length.
- Three directional sinusoids produced regular folds and ribbed wakes.
- Tornado fuel was injected along two persistent helical strands.

Projectiles now use a quadratic swept-body trajectory with an analytical descending floor contact. At contact, the source redirects incoming momentum into a flattened, expanding fuel crown, a short rebound, staggered inclined lobes and a finite low residual release. Fuel, heat and soot continue through the existing flow and combustion. Reaching an aim point in air ends fresh release; it does not invent a solid surface.

The source work bounds use the same contact time and include the full aftermath. Curved sweeps sample four short curve segments but evaluate the fuel packet once at the closest position, avoiding double injection at overlaps. The whip's air crack is a short moving release. Breath grows once, then transports pulses along its established reach. Tornado fuel is concentrated near its base and shaped by the rotating flow. The source folds use one octave of four-corner gradient noise, following the simplex construction described in [Gustavson's paper](https://itn-web.it.liu.se/~stegu76/TNM084-2019/simplexnoise.pdf), with a project-specific hash and gradients.

Aiming now uses a floor ray for low targets and otherwise preserves target height independently of emitter placement. Out-of-bounds floor aims are rejected. The four cast slots, charge/release, pan, zoom, light controls and source library remain available.

## Verification

[RC20_POWERS_CONTACT_PROOF.json](RC20_POWERS_CONTACT_PROOF.json) records the exact package fingerprint and bounded evidence paths.

| Gate | Result |
| --- | --- |
| CPU power/state/input tests | 67 pass, including swept contact against an independently sampled trajectory and actual floor picking. |
| Package | 43 runtime runners against source and packaged directory; nine package tests pass. Directory and ZIP byte inventories verified. |
| Strict WGSL | Official Dawn null backend: 219 unique modules / 528 generic and recorded variants; zero warnings/errors. The invalid derivative fixture is rejected. |
| Original native | All 24 powers replayed on Intel UHD; 192 captures. A final two-power whip/tornado replay adds 16 captures. All 208 pixel hashes and dimensions checked. |
| Volume/Sparse native | 684 simulated frames plus held views on RTX 4060. A ground-aimed fireball, meteor, four overlapping Sparse barrages and a tornado pass production feedback and numerical gates. Maximum measured CFL 1.166 against 1.5. GPU resource allocations remain fixed after startup. |
| Matched cost | Meteor at unchanged 128³ flow, 256³ chemistry and 768×432 output: completed GPU median 20.85 → 20.72 ms; p95 29.41 → 27.49 ms. No material cost regression in this native comparison. This is not browser FPS. |

## Remaining scope

This is a floor-contact improvement. Arbitrary mesh collision, debris, scorch decals and damage reactions are not added. Several sources still need further art direction; this proof does not declare every power to meet a finished game's visual standard. Original retains its projected rendering limits. Native captures verify the shaders and selected motion sequences, while browser input/display pacing and mobile performance remain open. Browser automation was blocked by automatic approval review for this session.
