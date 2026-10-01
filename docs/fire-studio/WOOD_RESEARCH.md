# Wood combustion, structure and appearance

Research reviewed through 30 September 2026. This is a targeted primary-source survey, not an exhaustive review or a claim that a browser reproduces an offline research solver.

## Implementation decisions

| Mechanism | Chosen browser model | Evidence and limitation |
|---|---|---|
| Drying and pyrolysis | Persistent virgin wood, moisture, char and surface/core heat; temperature-dependent heat capacity, conductivity and Arrhenius rates | Heat drives stock conversion. Demo material time can be accelerated separately from the fluid and rigid bodies. A reduced pine model cannot predict every species. |
| Solid–gas coupling | Finite volatile mass transferred from occupied material cells; normalized exterior deposition; gas heat feeds solid heat | Avoids an arbitrary emission shell. Water and inert pyrolysis products are recorded in the material ledger; the existing gas solver does not transport separate chemical species. |
| Char | Separate char stock, insulation, shrinkage damage and oxygen-limited oxidation | Char oxidation produces heat and inert products; it does not create a second volatile-fuel source. |
| Structural failure | Authored beam graph with remaining section, char, irreversible cracking, self-weight, axial/shear load and thermal strength loss; detached rigid subtrees and capped faces | Real geometry detaches. This is reduced beam failure, not a finite-element or phase-field crack propagation solver. |
| Solid appearance | Random-access grain, rings, pores, rays and growth distortion in rest coordinates; rough char and crack relief | Cut faces and falling pieces retain their material coordinates. This is procedural anatomy, not a trained reconstruction of a specimen. |
| Rendering | Imported tree bark color, relief and roughness retained; rough dielectric lighting and a small fiber sheen | The simplified sheen is not the measured finished-wood BSDF in the cited work. |

The browser retains the fixed gas and chemistry resolutions. Original uses a projected material inventory and its existing layered fluid; Volume uses a 64³ material inventory and the existing 128³ flow / 256³ chemistry. Neither is a fire-safety engineering model.

## Combustion and deformation

1. **FlameForge (2025, PACMCGIT / SCA).** [Full manuscript](https://arxiv.org/html/2412.16735v1), [publication](https://doi.org/10.1145/3747855). Coupled solid temperature, volatile fuel and char fields, evolving surfaces and insulation are the strongest reference for replacing timer-driven emitters. Reported CPU simulation takes approximately 1.1–30 seconds per frame. The manuscript does not provide a browser-ready fracture solver.
2. **Pirk et al., Interactive Wood Combustion for Botanical Tree Models (2017).** [Author project](https://storage.googleapis.com/pirk.io/projects/fire_trees/index.html), [publication](https://doi.org/10.1145/3130800.3130814). Botanical skeletons, surface combustion and rod structure provide a practical interactive architecture for a detailed tree without simulating every mesh vertex as a solid element.
3. **Lahouze, Jooma et al., Pyromechanics (2025).** [Author manuscript](https://sam.ensam.eu/bitstream/handle/10985/26063/i2m-fuel-jooma-2025.pdf?isAllowed=y&sequence=1), [publication](https://doi.org/10.1016/j.fuel.2025.134557). Links temperature, anisotropic thermal strain, pyrolysis shrinkage and orthotropic stress. Its validated shrinking elastic wood model is a useful material reference; it does not validate our reduced fracture thresholds.
4. **Caraccio et al., anisotropic multiphase biomass pyrolysis (2026 revision).** [Full manuscript](https://arxiv.org/html/2510.17588v2). A conservative multiphase shrinking-particle formulation and anisotropic transport address effects omitted by a simple solid fuel mask. Its detailed CFD is substantially beyond this runtime's reduced chemical channels.
5. **Charring and pyrolysis of coniferous wood (2026).** [Publication](https://doi.org/10.1016/j.ijheatmasstransfer.2025.127644). Microstructure, porosity and changing permeability matter during conversion. The browser model uses a reduced insulation and conversion response, not resolved cellular transport.
6. **Microstructural Features and Initial Char Formation in Spruce Wood (2026).** [Primary article](https://www.mdpi.com/2571-6255/9/8/333). Observations of initial char, local cracking and brittleness motivate persistent physical damage. Its particular specimen and heating conditions should not be treated as universal ignition constants.
7. **Li and Hostikka, charring shrinkage and cracking of fir (2017).** [Author record](https://research.aalto.fi/en/publications/charring-shrinkage-and-cracking-of-fir-during-pyrolysis-in-inert-/), [publication](https://doi.org/10.1016/j.proci.2016.07.001). Direction-dependent shrinkage and different longitudinal/transverse crack depths support grain-aware checking rather than an isotropic painted crack grid.
8. **Baroudi et al., thermomechanical crack topology (2017).** [Manuscript](https://arxiv.org/abs/1604.01249), [publication](https://doi.org/10.1016/j.combustflame.2017.04.017). Thermal stress can establish crack patterns before appreciable pyrolysis. Damage therefore includes temperature gradients and softening; it is not exclusively a burn-percentage texture.
9. **Timber-panel char cracking model (2025).** [Publication](https://doi.org/10.1016/j.csite.2025.106788). Experiments connect crack spacing to panel dimensions and heating. This is not a transferable three-dimensional tree failure law.
10. **Chu et al., char crack growth in densified wood (2025).** [Author record](https://research.polyu.edu.hk/en/publications/investigation-on-the-char-crack-growth-of-densified-wood/), [publication](https://doi.org/10.1016/j.engfracmech.2024.110697). Grain cohesion, shrinkage and heat flux influence crack development; densified material parameters require specimen-specific fitting.
11. **Noël et al., anisotropic phase-field fracture identification in spruce (2025).** [Publication](https://doi.org/10.1016/j.engfracmech.2025.111304), [experimental dataset](https://doi.org/10.57745/NGOKFP). A stronger route for physically resolved grain-dependent fracture, but the experiments identify uncharred wood. Implementing the paper requires a spatial mechanical solve and validated thermal damage parameters, not just changing the graphics API.
12. **Sreekanth, Kolar and Leckner, primary wood fragmentation (2008).** [Author record](https://research.chalmers.se/en/publication/74972). Thermal stress and shrinkage contribute to fragmentation, while impact can complete a weakened fracture. Fluidized-bed conditions are not equivalent to a freely burning tree.

## Appearance

13. **Liu, Marschner and Dye, Procedural Wood Textures (2015).** [Full manuscript](https://arxiv.org/pdf/1511.04224). Anatomical fields and directional fiber scattering are a better foundation than independently projected side and end textures.
14. **Liu, Dong, Hašan and Marschner, Simulating the Structure and Texture of Solid Wood (2016).** [Author project](https://www.cs.cornell.edu/projects/wood/), [publication](https://doi.org/10.1145/2980179.2980255). A solid volume can expose coherent rings, pores, rays and fiber direction on arbitrary cuts. The runtime uses a compact approximation of that idea.
15. **Marschner, Westin, Arbree and Moon, Measuring and Modeling the Appearance of Finished Wood (2005).** [Author publication](https://www.cs.cornell.edu/~srm/publications/SG05-wood.html). Measured subsurface fiber cones differ from a generic surface anisotropic highlight. Our uncoated/charred material keeps that term weak and does not claim a measured reproduction.
16. **Larsson et al., Procedural Wood with Knots (2022).** [Author manuscript](https://www.ma-la.com/procedural_knots/Procedural_Knots_2022.pdf), [publication](https://doi.org/10.1145/3528223.3530081). Skeleton-aware growth around knots motivates rest-space fields aligned with the existing branch graph.
17. **Larsson et al., Learned Inference of Annual Ring Patterns (2024).** [Primary article](https://onlinelibrary.wiley.com/doi/10.1111/cgf.15074). Learned growth-time fields reconstruct interior patterns from observations. No such specimen data or trained model is present here, so the runtime does not claim to implement this learned reconstruction.
18. **Nindel et al., anatomical wood fitting from a photograph (2025 revision).** [Manuscript](https://arxiv.org/abs/2302.01820). Ring detection and fitted phase fields can preserve a particular specimen. This remains a future asset-authoring route; the shipped procedural grain is not photo-fitted.

## What was deliberately not claimed

- No universal species model, safety prediction or calibrated smoke yield.
- No full finite-element, phase-field, porous-gas or cellular wood simulation.
- No promise of identical FPS across desktop and mobile GPUs.
- No prerecorded burning animation, rendered fire sequence or replacement tree topology.
- Native GPU measurements validate shader execution and cost on the recorded adapter; they do not establish live browser frame pacing.

## Material capacity and imported geometry

19. **Wright et al., The worldwide leaf economics spectrum (2004).** [Primary publication](https://doi.org/10.1038/nature02403), [author manuscript](https://conservancy.umn.edu/bitstream/11299/176900/1/Wright%20et%20al%202004.pdf). Leaf dry mass per area varies greatly across species. The reviewed tree uses an explicit authoring value of 0.05 kg/m², rather than treating each voxel touched by a leaf as a full voxel of pine. This is not a fitted species measurement.

The former full-cell tree proxy implied about 710 kg of material. Its corrected finite inventory is 26.9455 model kg: 26.4921 kg of authored beam wood and 0.4533 kg of dry foliage. Source SDF, conductivity and material IDs remain unchanged. Fractional capacity accounts for thin branches and the sigil slab; world-scale mass is model mass multiplied by scale³. Logs, timber and the native-contour sigil contain 283.0850, 307.2327 and 9.61189 model kg respectively. The solid, volatile transfer and structural load use the same donors.

Every original reviewed tree triangle is retained: 1,588,926 triangles, plus 88,760 fracture-cap triangles. Partitioning duplicates 44,415 seam vertices without simplifying the source. All new interfaces close; the original 33 nonmanifold seams and 252 boundary edges are preserved. Fresh caps, bark and grain remain in rest coordinates as pieces fall.

The procedural solid uses approximately 5.6 mm ring spacing and submillimetre cellular-channel spacing in model coordinates, with small fresh-surface relief. These are explicit authoring values, not species measurements. World scaling follows the piece. Phase derivatives filter unresolved rings and cracks into their mean; close views retain detail without a coarse repeating grain pattern at a distance.

## Authoring and implementation

The shared runtime is in `wood-thermo.js`, `wood-material.js`, `wood-structure.js`, `wood-state-gl.js` and `wood-structure-gl.js`; Volume transfer and moving support are in `pyro-gpu/wood-flux.js` and `wood-collision.js`. The finite floor bed uses the same chemistry. Shared source IDs and the Wood time control survive mode changes, URLs and saved looks.

Offline authoring lives in `tools/fire-sources/export_wood_structure.py`, `export_wood_presets.py`, `calibrate_wood_proxy.py` and `finalize_wood_manifests.py`. These tools partition source geometry, cap interfaces, author owners and capacities, and record SHA-256 manifests. They require the reviewed source inputs and NumPy/SciPy/scikit-image/Shapely; raw authoring inputs are not part of the web package. `tools/fire-studio/wood-metadata.py` derives the exterior transfer donors from the corrected stock. The package checks geometry, companions and flux provenance together before shipping.

Native validation and matched cost measurements are recorded in [RC14_WOOD_PROOF.json](RC14_WOOD_PROOF.json). The added solid physics increases complete GPU work in the measured tree fixture despite faster transfer-support and structural mass passes. Native execution does not establish browser FPS, and the benchmark is a short matched trial.

## Runtime approximations

- Reduced strengths use authored dry bending strength, compression/tension ratios 0.45/0.9 and shear ratio 0.1. They are not specimen-validated fracture parameters. Beam failure considers the actual remaining mass above the joint, including healthy children above an oxidized support; previously detached children stop loading that joint. There is no elastic beam displacement, arbitrary crack topology, redundant-joint solve or fragment-to-fragment contact.
- Volume transfers finite volatile mass and sensible energy through a normalized exterior kernel. Subquantum release carries forward. Completely blocked quantities remain in fixed coarse world cells until fluid space opens; this is a trapped-vapor approximation, not porous transport inside moving wood. Outside-domain escape is recorded separately.
- Material cells without coverage cannot resolve thin-beam burning individually. Surface sampling normalizes occupied corners, preserves exhausted zero stock and uses healthy fallback outside coverage. Unsupported branches still follow a parent fracture. No artificial fuel is added to fill coverage gaps.
- Original stocks are projected columns, so overlapping pieces share thermal state. Mechanical load retains each actual donor owner and current stock; rigid release uses the projected depth centroid. This is not independent three-dimensional material transport.
- Water and inert oxidation products are recorded by the material model but are not separate transported gas species. The oxygen-limited oxidation closure is not a full solid/gas oxygen budget. Gas embers are one-way visual tracers, without conserved wood/char mass or firebrand ignition.
- Dropped wood is a finite floor bed with the shared thermochemistry and material. It does not become a pile of rigid lumber.

The material clock defaults to 12× for demonstrations; gas and falling pieces keep real time. Set Wood time to 1× for unaccelerated ageing. The gas resolution, chemistry resolution and ray detail do not scale down to hide wood cost.
