# Lava mechanics rebuild

CPU only. Existing caches and the structure-23 comparison remain historical
evidence. They must not be relabelled as results from the revised equations.

## Acceptance contract

1. Continuous hot-crust creep with analytic relaxation checks. Material
   parameters are nominal until fitted to a specified basalt composition.
2. Energy-based, length-regularized damage with irreversibility, unloading,
   compression and fracture-energy checks. Coupled equilibrium must converge.
3. Transactional step rejection and a three-level temporal comparison of work,
   motion and fracture. Rejected steps must leave no heat/source/contact state.
4. Friction inside implicit mechanics; validate analytical stick/slip,
   separation, momentum balance, rotation and coupled constraints.
5. Crack-preserving solid reconstruction and a separate liquid surface path;
   compare topology, volume, temporal correspondence and actual CPU images.
6. Fresh cooled-flow validation; a prescribed tensile coupon is not a free-flow
   lava demonstration. Spatial refinement and motion review precede beauty.

## Compute and evidence

Small analytic and CPU coupon tests first. Retain reports and source hashes.
No GPU use, no full video render, no invented crack patterns or hidden
geometry repairs. Tests gate the current source, never an unrelated old run.

## Reference scope

The new phase-field prototype uses the standard quadratic crack-density
functional and a volumetric/deviatoric tensile split. It is not a port of
CD-MPM or a claim of equivalence to that implementation. CPIC, reference
implementations and production remeshing remain comparison targets until
their corresponding validations are demonstrated here.

Sources:
- https://mingg13.github.io/papers/2019_Fracture_tech_doc.pdf
- https://www.disneyanimation.com/publications/augmented-mpm-for-phase-change-and-varied-materials/
- https://arxiv.org/abs/2403.13783
- https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019JB018815


## Current result

24 component/regression checks pass. The short tensile comparison passes, with work error decreasing from 3.483% to 1.813%. These are different cases from the historical structure-23 fracture, not a 157% to 1.8% rerun claim.

Strong softening initially exposed per-remap APIC velocity filtering. The experimental affine impulse transfer has zero-time identity and a declared 1 ms filtering timescale. Its bounded continuation reaches about 95% damage; it remains experimental. No complete new lava video or photorealism is claimed.

Production remains blocked on complete fracture/time and spatial checks, calibrated rheology, large-deformation surfaces and a validated natural-flow scene.
