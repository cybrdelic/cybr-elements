# Supported workflows and preservation scope

CYBR ELEMENTS includes delivered offline work and current interactive Fire
Studio. Element Studio is the future multi-element workspace. Retaining source
does not certify full re-rendering, calibrated physics or current live performance.

## Current delivered films

Source filenames below are relative to `work/element-motion/`. The exact local
import/helper closure and per-file source hashes are recorded in
[offline-source-closure.json](offline-source-closure.json). Closure counts include
entrypoints and retained transitive code, not generated caches or external tools.

| Element / current media | Retained entrypoints and local closure | External dependencies / missing generated inputs | Validation here |
| --- | --- | --- | --- |
| Fire / `fire-02.mp4` | `sigil_02_source.py`, `sigil_02_build_v2.py`, `sigil_02_fire_v2.py`; 6 files, including `sigil_02_fire.py` and `bending-fire.py` used by the builder | NumPy, SciPy, Pillow, OpenCV, scikit-image, PyTorch, FFmpeg; full state/frame caches must be rebuilt | Actual source builder arrays/review pixels match baseline; film fully decoded; full reactive-flow render not rerun |
| Air / `air-02.mp4` | `sigil_02_air_v2.py`; 1 file | NumPy, Pillow, PyTorch, FFmpeg; full gas states/frames must be rebuilt | Film fully decoded; numerical/render source hash preserved; gas rendering not rerun |
| Water / `water-02-r8.mp4` | `sigil_02_active_prepare.py`, `sigil_02_active_water_run.py`, `sigil_02_active_water.mjs`, `sigil_02_active_mesh.py`, `sigil_02_active_water_render.py`, `sigil_02_active_finish.py`; 18 files including FLIP solver and `bending_surface.py` / vendor mesh helpers | Node, NumPy/SciPy/Numba/scikit-image, Blender/Cycles, FFmpeg; historical parcels, guide fields and reconstructed mesh caches are already absent locally | Actual small APIC/FLIP CPU component matches baseline state exactly; r8/r7 films decoded; full 02 solve/reconstruction/render not rerun |
| Earth / `earth-02-r6.mp4` | `sigil_02_ground_earth_build.py`, `sigil_02_ground_earth_render.py`, `sigil_02_coherent_earth_build.py`, `sigil_02_return_finish.py`; 5 files | Blender/Bullet, NumPy/SciPy/OpenCV/Shapely, Pillow, FFmpeg; omitted production frames must be regenerated | r6/r5 films decoded; geometry and code retained; rigid solve/render not rerun |
| Ice / `ice-02.mp4` | `sigil_02_new_materials.py`, `sigil_02_atmosphere.py`; 2 files | Blender/Cycles, NumPy/SciPy/Pillow, FFmpeg; atmosphere atlases and frames must be regenerated | Film decoded; source/geometry retained; no new ice job launched |
| Lava / `lava-02.mp4` | Same material/atmosphere pair; 2 files | Blender/Cycles, NumPy/SciPy/Pillow, FFmpeg; Rock 09 textures have retained CC0 provenance; production caches must be regenerated | Film decoded; source/geometry retained; full render not rerun |
| Lightning / `lightning-02-r5.mp4` | `sigil_02_electric_tree_export.py`, `sigil_02_atmosphere.py`, `sigil_02_new_materials.py`; 3 files | Blender/Eevee, NumPy/SciPy/Pillow, FFmpeg; channel/atmosphere production outputs must be regenerated | r5/r4 films decoded; authored discharge source retained; full render not rerun |
| Telekinesis / `telekinesis-02-r4.mp4` | `sigil_02_coherent_earth_build.py`, `sigil_02_telekinetic_contours.py`, `telekinesis_02_render_v2.py`; 3 files, plus retained geometry/contours | Blender/Eevee, NumPy/SciPy/OpenCV/Shapely/scikit-image, FFmpeg; production frames must be regenerated | r4/r3 and older delivered films decoded; exact source/geometry retained; rigid effect not rerendered |

Water's r8 edit joins a reused earlier opening to its new forward hold/release.
Earth's r6 opening is an editorial reversal of solved breakup footage; its later
fall is retained. Neither is one newly solved continuous forward entrance.
Ice/lava are authored fractured solids with rigid release and gas, not general
phase-change or liquid-lava solvers. Lightning and Telekinesis are authored effects.

## Current interactive modes

| Mode | Entrypoints / dependencies | Validation status |
| --- | --- | --- |
| Original | `fire-live/studio.js` → `fire.js`, `original-shaders.js`; WebGL 2 + float targets | CPU controls/lifecycle/shader-assembly fixtures and package startup fixture pass; real consolidated browser/render/control review pending |
| Volume | Same workspace → `pyro-gpu/app.js`, `solver.js`, `shaders.js`, `renderer.js`; WebGPU | CPU resource/binding/lifecycle fixtures pass; native GPU and browser review pending |
| Sparse | Same workspace and Volume source catalog + `brick-pool.js` / pooled coupling; WebGPU and dense fallback backing | CPU pool/fallback/mode fixtures pass; real browser review pending; no established general speed advantage |
| Air / smoke | Fire Studio smoke presets in existing engines | Retained source/preset fixtures pass; a dedicated Air workspace remains roadmap |
| Historical water viewer | `outputs/.../elements/water/index.html`, `water.js`, bundled Three.js and reconstructed mesh playback | Code/license retained; required historical meshes already absent; not a live water solver or verified current playback session |
| Other interactive elements | Element Studio roadmap | No completed realtime Earth/Ice/Lava/Lightning/Telekinesis mode is claimed |

## Earlier authored workflows

The selected tree also retains the root `work/` build/render scripts for branded
wordmarks, fonts, cast/gesture/intro/fire/gas/handprint studies; the corresponding
`work/element-motion/` motion and material source families; `work/brand-font/`;
and the FLIP, native-water, directed-water and water-motion-study implementations.
These earlier workflows were not rerendered here. Many gallery inputs require
historical restoration. Optional legacy gas gesture flags 20–23 refer to Python
helper aliases already absent in the captured source; the default 02 path does
not use those branches. They are a baseline rebuild limitation, not a successful
install or validation claim.

| Earlier workflow family | Representative retained entrypoints | Status |
| --- | --- | --- |
| Branded wordmark fire / air | `work/build_brand_fire.py`, `brand_fire_motion.py`, `render_brand_fire.py`, `bake_air_marks.py` | Source retained; historical data/full renders not reproduced |
| Cast / gesture / intro | `work/build_cast.py`, `cast_motion.py`, `render_cast.py`, `build_gesture.py`, `gesture_motion.py`, `render_gesture.py`, `build_intro.py`, `render_intro.py` | Source retained; legacy helper/path limits apply |
| Handprint / lettering water | `work/setup_handprint_renders.py`, `render_water_handprint.py`, `render_water_sans.py`; `work/water-native/`, `water-directed/`, `water-motion-study/`, `flip-lettering-v2/` | Solver/authoring code retained; old simulation inputs and optics renders not verified here |
| Typeface authoring | `work/brand-font/`; `outputs/cybrdelic-type/typefaces/source/build_families.py` | Existing font bytes/download/HTTP paths verified; fonts not rebuilt or installed |

The two unadopted Telekinesis concept-image v5/v6 pilots are preserved outside
the public tree. They are not the current r4 implementation. No new concept
image, ice render, simulation benchmark or quality-reduced substitute was made.

## Why the file counts differ

The checkpoint receipt's `offlineSourceFilesInCore: 2660` counts **every `work/`
file**, including reports, manifests, proof images and iteration copies. Of
those, 978 have a code extension. It is not a count of 2,660 independent solvers.

The curated tree retains 655 `work/` files, including 486 code files. It selects
the adopted authoring implementations, source geometry and minimal configuration
inputs, rather than nested copies of generated scripts, render iteration folders,
status/QA receipts, per-frame diagnostics and unrelated prototypes. Core and
supplemental selection counts are recorded in the closure JSON. The verified
private checkpoint retains the excluded original work and exact path inventory;
the active checkout remains untouched. No source file is deleted from originals
or backups.

Static closure confirms retained local source dependencies. It cannot prove
arbitrary computed paths, external tool installation or missing production input
availability. [Pipelines](PIPELINES.md) describes safe fresh-output rebuilding;
[known issues](KNOWN_ISSUES.md) and [validation](VALIDATION.md) state the limits.
