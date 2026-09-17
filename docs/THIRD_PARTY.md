# Third-party materials and tools

The root `LICENSE` is the GPL v2 license already present in the target repository.
It has been preserved verbatim. Component notices take precedence for their
respective files.

## Rock scans

The retained download metadata, authorship and checksums are in
`work/element-motion/sigil-02-repair/scans/`.

| Asset | Artist | Source | License |
| --- | --- | --- | --- |
| Boulder 01 | Rico Cilliers | https://polyhaven.com/a/boulder_01 | CC0 |
| Rock 07 | Jenelle van Heerden | https://polyhaven.com/a/rock_07 | CC0 |
| Rock 09 | Jenelle van Heerden | https://polyhaven.com/a/rock_09 | CC0 |

The current lava uses Rock 09 textures. The scan files are restored with
`python scripts/fetch_assets.py --all`. These notices record the provenance in
the checked-in download manifests; no external images were generated for the README.

## Native fluid implementation

`work/flip-lettering/vendor/` contains the locally supplied CYBR FLIP III.1
implementation and reconstruction tools. Its original GPL v2 `LICENSE` remains
in that directory. The browser copy has its own retained license at
`outputs/cybrdelic-type/elements/water/LICENSE`.

## Runtime dependencies

Blender, Python, Node.js, FFmpeg, NumPy, SciPy, PyTorch, Mitsuba, Warp, Pillow,
OpenCV, scikit-image, Shapely, fontTools, Brotli and Three.js are used by different
parts of this research project. They are separate dependencies with their own
licenses. Their installers, Python environments, node_modules and GPU compiler
caches are not distributed here. The browser's bundled Three.js file retains
its embedded copyright notice; the complete MIT text is included beside it as
`outputs/cybrdelic-type/elements/water/vendor/THREE-LICENSE.txt`.

The custom typeface outlines are authored project assets. Windows Arial and
Segoe UI are used only for some rendered captions and specimen labels; the font
files themselves are not copied into this repository.
