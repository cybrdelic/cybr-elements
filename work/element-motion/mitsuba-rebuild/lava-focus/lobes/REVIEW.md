# Folded lava material study

The shallow slab has been replaced by overlapping, rounded lava lobes. Coarse folds alone looked like fabric and evenly spaced ribs looked manufactured, so the retained shape uses nested, curved folds with varying spacing and strength. Thin independent basalt shells have real aperture walls over a separate molten body. Nose masks use world-space fields to remove radial pinching. Thermal emission comes from temperature; the skin columns cool through conduction, radiation and convection, with an approximate lateral boundary layer beside the crust. Back lighting reduces broad white/pink reflections on the molten faces.

The final hero and close-up were inspected directly. The changes improve the relief, silhouette and crust/melt transition; some fold families and breakup patches remain visibly procedural. This is an authored material study, not a validated new fluid simulation or a finished moving sigil. The enthalpy residual describes the one-dimensional columns only; it is not a global energy audit for the assembled geometry.

The earlier rough-basalt and original images remain byte-for-byte intact. All generation, rendering and denoising used the CPU. No GPU workload or video batch was launched.

Reference: [NPS lava flow forms](https://www.nps.gov/articles/000/lava-flow-forms.htm). No external mesh or texture asset was incorporated.

The larger close-up exposed a separate renderer defect: temperature groups assigned a constant radiance to each face, producing visible bands across molten openings. The retained emitter interpolates per-vertex Planck radiance continuously and samples geometry independently of the repeated texture coordinates. CPU checks verify known barycentric colors, radiance divided by sample density, PDF consistency and an occluded light sample. The original grouped-temperature renders remain diagnostic artifacts only.
