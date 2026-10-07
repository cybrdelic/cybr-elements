# Fire-source assets

## Reviewed forest tree

The tree comes from the latest `world/output/forest-surface/forest.blend`,
using the reviewed tree index 538, variant 1. Wood and roots retain the actual
displaced meshes. Crown membership follows the mature stand's whole-leaf
selection, with the same random sequence as its original renderer.

From the outer CYBR workspace:

```powershell
& 'C:/Program Files/Blender Foundation/Blender 4.5/blender.exe' -b --factory-startup -t 2 --python cybr-elements/tools/fire-sources/export_forest_tree.py
python cybr-elements/tools/fire-sources/leaf_coordinates.py
python cybr-elements/tools/fire-sources/voxelize_forest_tree.py
```

The export is a 0.23171848-scale display specimen fitted to the existing six-metre
fluid chamber. Source metre coordinates and scale are recorded in its manifest.
It is not a full-scale wildfire simulation. No triangles are simplified or
replaced with canopy ellipsoids. The leaf-coordinate pass adds UVs to each
connected leaf without altering positions or topology.

`forest-tree/manifest.json` records provenance, counts and file hashes.
The display mesh has 1,027,597 vertices and 1,588,926 triangles, including
29,397 connected leaf meshes. The solver's separate 64³ fuel/collision proxy
comes from this same mesh. Foliage supplies fuel without becoming an opaque
solid canopy shell.

`build.py` still builds the explicitly labelled house/car/mannequin/log
**prototypes**, then rebuilds the tree proxy from the reviewed export.
It cannot silently regenerate the rejected tree-study skeleton.

## Current physical scope

The tree has local ignition, gas-to-surface heating, neighbour heat diffusion,
moisture evaporation with a heat cost, finite pyrolysis fuel, char accumulation,
surface recession, leaf loss and widening of existing bark fissures.
These are reduced, accelerated material equations, not species-calibrated fire
physics. Gas combustion, soot and tracer embers use the existing common flow.

The section-stiffness value is a damage diagnostic only. There is **no branch
fracture, detached-limb dynamics, collapse, crack-topology remeshing, or
firebrand-to-fuel ignition**. Those require mechanical connectivity, material
calibration and moving solid/fuel coupling; they must not be claimed from the
current surface shaders. Mesh spotlight shadows are exact to the rasterized
tree; internal fire/GI occlusion still uses the coarse wood proxy. The material
renderer is diffuse and does not reproduce every Blender material lobe.
