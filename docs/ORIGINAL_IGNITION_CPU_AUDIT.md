# Original ignition CPU audit

The Original plume caller supplied the end of the current physical step to a pilot integrator whose age argument denotes the start of that step. `fire.js` advances `elapsed` before `runStep`; `boundedPilotDose` integrates the interval `[age, age + delta]`. Passing `burstAge - delta` corrects that mismatch. The Volume caller already submits its age before advancing it and requires no change. Four loader cache keys are refreshed so browsers request the corrected shader module; the retained v5 route is unchanged.

The CPU comparison starts from public commit `a23ada5c45bedd6248e035de4bc71b55489415b2`. Native confirmation of this correction is pending. It does not resolve all presets, visual limitations or performance issues.

## Demonstrated budget error

The authored steady rate is 8 normalized units/s, with an additional 4 units/s for the first 0.25 s. At one second, the prescribed integral is 9. The fixture executes the emitted production plume block, including its actual pilot call.

| Physical step partition over 1 s | Original call | Corrected call | Prescribed |
| --- | ---: | ---: | ---: |
| 30 equal steps | 8.866666667 | 9 | 9 |
| 60 equal steps | 8.933333333 | 9 | 9 |
| 0.12, 0.13, 0.01, 0.24, 0.50 s | 8.48 | 9 | 9 |

At 30 Hz, the missing dose is `4 / 30 = 0.133333333` normalized units. The denominator for the **total one-second dose** is `8 × 1 + 4 × 0.25 = 9`, giving a **1.481481% total-dose loss**. The denominator for the **separate finite startup increment** is `4 × 0.25 = 1`, giving a **13.333333% startup-increment loss**. These percentages describe different denominators.

The temperature scale is `(kelvin - 300) / 1200`; reference density is 1 kg/m³ and heat capacity is 1200 J/(kg K). One normalized dose unit supplies `1 × 1200 × 1200 = 1,440,000 J/m³`, multiplied by the unchanged `sourceHeat / 0.9` and spatial Gaussian. The mixture-capacity denominator converts that supplied energy into a temperature change; it does not change the supplied energy. At the Sooty pilot center (`sourceHeat = 0.9`, Gaussian = 1), the total intended one-second energy is 12,960,000 J/m³, the startup increment is 1,440,000 J/m³, and the missing startup energy is 192,000 J/m³. Correcting the caller restores the prescribed integral without changing rates, fuel, heat settings, spatial profiles or the physical clock.

## Preset and lifecycle distinctions

- Free fire selects the plume branch with the current selected fuel; a fresh default selection uses wood. Selection clears the source and waits for a click. A source that has not been ignited supplies neither fuel nor pilot energy. Restarting or changing the fuel can change this comparison.
- Sooty plume uses oil, pilot heat 0.9, fuel-rate multiplier 1.2 and soot-yield multiplier 1.7; smoke-only simulation is disabled. Selection ignites it automatically. This is the warm-vapor plume branch, not the separately premixed smoke/fire burst.
- Warm plume fuel enters at 396 K, below the reduced gas activation interval of 720–1200 K. A Gaussian pilot heats a compact neighborhood; a cold parcel away from that pilot can contain fuel without burning. Transport and air supply determine whether neighboring cells ignite.
- Fireball uses gas and pilot heat 0.72. Its finite startup cue precedes the 0.22 s travel transition. Released power fuel uses the existing oxygen-weighted bounded igniter. Its source pool already uses start-age midpoint sampling, and its host corrects the source clock by `clock - delta`; neither contract needs this plume fix.
- Wood Sigil uses a separate wood source and activation path. A three-second wood startup is not a settled gas-plume acceptance check. Pausing advances no physical step; stopping disables the source; re-igniting resets `burstStart`.

The actual reduced reaction consumes at most `min(fuel, oxygen / 0.7)`, multiplied by `1 - exp(-5.8 * delta)` and thermal activation. Incoming sensible energy and external pilot energy are checked against the actual mixture capacity. The fixture also checks fuel consumption and oxygen consumption, including soot oxidation. These are the reduced model's concentration and heat-source accounting, not a detailed species or product-enthalpy model.

## CPU observations and their limits

A manufactured stationary parcel at the actual pilot offset, with a fixed feed-noise sample of 0.5, burns on the first 1/30 s step in both Free fire and Sooty plume **before and after** the correction. Over 0.5 s, the uncorrected fixture consumes 0.330836004 and 0.456506972 normalized fuel respectively, with nonzero soot. Correcting the finite pilot budget leaves those particular fuel totals unchanged. Inactive Free fire and a parcel far from the pilot produce zero burning. This demonstrates a budget error, not a complete explanation or fix for every zero-burning observation.

For one manufactured Fireball release at 1/80 s, an added dose of 0.001 gives about 334 K and zero reaction; a dose of 0.02 gives about 752 K and nonzero reaction. A fuel-rich dose with little oxygen gives zero reaction. Those local states cannot establish the behavior of a moving, entraining plume.

The CPU fixture executes emitted scalar GLSL helper bodies, the live plume injection block and the live Original reaction block using JavaScript doubles. It includes local grey-body cooling, but excludes transport, diffusion, spatial integration, geometry, native shader compilation and F16/F32 execution. Its stationary parcel temperatures are manufactured results, not rendered-flame predictions. No browser or GPU is started. Native confirmation of the corrected candidate remains outstanding.

## Reproduce

From the repository root with Node installed:

```sh
node tools/fire-studio/original-ignition.test.mjs
node tools/fire-studio/original-ignition-audit.mjs
```

The second command writes source hashes, units, budgets and local probe results as JSON to stdout; an optional first argument saves that JSON to a file. The interval tests cover first steps, negative initial ages, unequal steps crossing age zero and 0.25 s, and explicit energy and mass accounting. The existing startup fixture executes actual host code through first step, reset/restart, pause, stopped-source coasting and burst recasting. The burst and power branches retain their existing clocks and never receive the plume correction. The Volume caller retains its already-correct start-age contract. No thermal parameters or solver time scales are adjusted.
