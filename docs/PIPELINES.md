# Authoring and rebuilding

The delivered films, typeface specimen and Fire Studio can be served directly
with the root README command. Offline authoring is a separate workflow: source
preparation, a native simulation or authored motion, rendering, then encoding.
The published tree retains adopted authoring source and inputs, rather than the
large accumulated frame caches and diagnostic receipts.

## Tools

The production scripts were developed on Windows with Python 3.12, Blender 4.5.3
LTS, Node.js and FFmpeg/ffprobe. Full Cycles renders use OptiX where configured.
Cross-platform full renders have not been established. Source preparation uses:

```sh
python -m pip install numpy scipy numba pillow opencv-python scikit-image shapely fonttools brotli
```

Gas/fire authoring additionally needs a compatible PyTorch installation. Install
FFmpeg and ffprobe on PATH. Run Blender scripts in Blender's Python environment;
the plain Python interpreter does not provide `bpy`. Some authoring scripts
retain machine-specific Blender paths and output revisions. Inspect and adapt
those paths before running a full production queue. Never run every script in
the directory as an installation step.

## Entry points

Names below are relative to `work/element-motion/`.

| Workflow | Source and renderer | Scope |
| --- | --- | --- |
| Approved source fields | `sigil_02_source.py` | Full artwork cross-section, topology and ignition order |
| Fire | `sigil_02_build_v2.py`, `sigil_02_fire_v2.py` | Fuel/heat transport, reaction and offline volume rendering |
| Air | `sigil_02_air_v2.py` | Advected gas and turbulent smoke |
| Water | `sigil_02_active_water_run.py`, `sigil_02_active_water.mjs`, `sigil_02_active_mesh.py`, `sigil_02_active_water_render.py` | Native APIC/FLIP, reconstructed liquid and Cycles optics |
| Earth | `sigil_02_ground_earth_build.py`, `sigil_02_ground_earth_render.py`, `sigil_02_return_finish.py` | Rigid source family and r6 editorial reversed entrance |
| Ice / lava | `sigil_02_new_materials.py`, `sigil_02_atmosphere.py` | Authored fractured solids, optical materials and gas |
| Lightning | `sigil_02_electric_tree_export.py`, `sigil_02_atmosphere.py`, `sigil_02_new_materials.py` | Branching channels, authored pulses and local volumetric lighting |
| Telekinesis | `sigil_02_coherent_earth_build.py`, `sigil_02_telekinetic_contours.py`, `telekinesis_02_render_v2.py` | Current approved fractured mark, authored field and directional cast |

The films do not imply a general ice/freezing, molten lava, electromagnetic or
force-field solver. Water's current edit joins its prior opening to a new forward
hold/release calculation. [Known issues](KNOWN_ISSUES.md) records these limits.
The existing browser water viewer plays cached reconstructed meshes.

## A bounded CPU preparation example

This runs the actual source-field builder without initializing a GPU:

```sh
python work/element-motion/sigil_02_source.py sigil-02
```

It writes `work/element-motion/sigil-02/source.npz`, `source-report.json` and
`source-review.jpg`. It overwrites that revision's generated source outputs:
use a separate working copy for reproducibility checks. `sigil-02-v2` is the
other accepted argument and matches the wider source domain used by later work.
The report checks artwork topology and silhouette intersection over union.
Those checks establish source preparation, not final fire appearance.

## Rebuilding a film

1. Inspect the selected script's inputs, dependencies, renderer path and output
   revision. Use a fresh working copy/output revision.
2. Restore missing historical inputs with `python scripts/fetch_assets.py --all`
   if required. The current player and Fire Studio need no restore.
3. Run source preparation and a small representative native case. Inspect actual
   source/render output along with finite-state, volume and contact checks.
4. Coordinate one GPU job at a time. Full simulation caches can require much
   more storage than this checkout. The ice/material queues are optional
   production orchestration, not part of local app startup.
5. Encode, fully decode and inspect motion before selecting a film in the player.
   The encoded films in this consolidation retain their original bytes.

Native water/FLIP implementation and license are under
`work/flip-lettering/vendor/`. Historical pack restoration verifies checksums and
refuses differing-file overwrites. Retaining authoring code does not mean a full
render resumes without rebuilding the omitted state/frame caches.

## Fonts and showcase

`outputs/cybrdelic-type/typefaces/README.md` describes the retained outline JSON,
OpenType features and font builders. `python scripts/build_showcase.py` rebuilds
the seven-film README GIF using CPU FFmpeg and Pillow; it does not run a simulation
or change the films. Telekinesis is the eighth element in the current player.
