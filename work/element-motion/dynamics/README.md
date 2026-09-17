# CYBRDELIC material dynamics

This directory contains an independent rebuild using NVIDIA Warp, NumPy/SciPy,
Blender Cycles/Bullet, and the existing FLIP carrier caches. It has no Houdini
dependency. It does not reproduce Houdini's proprietary implementations.

The camera, emitter trajectory and original sigil masters remain shared. Black
camera rays are mandatory. Lighting can remain visible in reflection and
transmission rays without creating a visible backdrop.

## Systems

| Family | Implementation | Important limitation |
|---|---|---|
| Sand, snow, metal | 3D quadratic MLS-MPM/APIC; logarithmic sand yield projection, snow compaction hardening, metal deviatoric plastic yield | Reduced constitutive laws and artist-controlled bending forces; not calibrated engineering material parameters |
| Ice | Advected cooling, latent interval and breakable distance constraints; surfaces reconstructed from particles | One-way split coupling to a cached FLIP carrier; accelerated phase change; some frames still read as liquid |
| Glass | Persistent closed shell fragments, Bullet rigid bodies and breakable fixed connections | Fragments are guided before release; no geometry swap, but pre-fracture topology is authored and this is not thermomechanical glass blowing |
| Lava | Advected neighbor heat exchange and a moving crust population | Carrier viscosity is the retained viscous FLIP solve; crust does not feed a full multiphase pressure solve |
| Foam | Surface/acceleration/shear sources; persistent gas particles; carrier advection, buoyancy, ballistic spray and film loss | Subpixel foam uses an effective scattering material; no fully resolved wet-foam cell-pressure solve |
| Plants | Branched rods with stretch and bending constraints, attached scanned shoots | Growth is authored; dynamics are integrated after activation; leaf aerodynamic deformation is approximate |
| Mud, blood, crystal | Restrained optical refinement of the stronger FLIP/Bullet foundations | Intentionally retain the stronger existing primary motion |
| Combustion | 3D reactive transport, pressure projection, temperature/soot/reaction fields, directional expansion | Low-Mach graphics model, not a compressible shock solver |
| Lightning | Persistent hierarchical channels, subframe exposure, return strokes and restrikes | Procedural electrical VFX, not a full electromagnetic solver |
| Seismic | Finite-difference elastic wave displaces a granular witness sample | Authored floating sample with driven grain motion; not a grain-contact solve or geological tomography |
| Heat | Dark-field numerical schlieren from the advected 3D temperature field | Small-angle optical diagnostic with amplified sensitivity; warm air is not self-luminous |
| Sound, pressure | Retarded radial pressure pulses with geometric spreading and attenuation; depth-integrated optical gradients | Authored slow-motion wave speeds and optical amplification; not calibrated real-time acoustics |
| Abstract techniques | Distinct tracer, oscillation, channel, repair and projection mechanisms | Explicitly authored visualizations of fictional techniques; graphical appearance remains a limitation |

## Reproduction

Run simulation scripts with the workspace Python interpreter. Render scripts run
inside Blender 4.5 and use `scene.py` for the fixed camera and black-stage setup.
`pilot.py` renders selected frames. `render_all.py` records fresh complete frame
receipts. `encode.py` validates all 120 HD frames, clear black camera corners,
predominantly black empty pixels, and video metadata. Foreground particles may
legitimately cross a corner. `review_videos.py` decodes complete clips into contact
sheets for visual review. `release.py` requires complete frame receipts and an
explicit per-effect review before publishing a separate candidate gallery.
For MPM candidates, `motion_preflight.py` checks the cached particle envelope
through formation and hold before a full render starts. A large escape from the
fixed camera stops that render. This catches gross motion failures cheaply; it
does not substitute for a material review.

Example commands from the workspace root:

```powershell
python work/element-motion/dynamics/mpm.py sand --particles 70000 --frames 120
python work/element-motion/dynamics/granular_secondary.py sand
python work/element-motion/dynamics/pilot.py render_mpm.py:sand:30,45,65,90
python work/element-motion/dynamics/check_physics.py
```

Image metrics and finite-state checks are not claims of realism. See the visual
review records for which candidates pass, fail, or remain under review.

Blender is launched with factory settings and a nonzero Python-error exit code.
The pilot runner also rejects stale frames, because an existing image is not
evidence that the current script rendered successfully. Run GPU-heavy jobs
sequentially on the 8 GB device, and do not stop unrelated user simulations.

## References and assets

- [Hu et al.: MLS-MPM and CPIC](https://yuanming.taichi.graphics/publication/2018-mlsmpm/)
- [MPM course and practical notes](https://yuanming.taichi.graphics/publication/2019-mpm-tutorial/)
- [NVIDIA Warp](https://github.com/NVIDIA/warp)
- [SideFX MPM workflows](https://www.sidefx.com/docs/houdini/mpm/index.html)
- [SideFX whitewater behavior](https://www.sidefx.com/docs/houdini/nodes/dop/whitewatersolver-.html)
- [SideFX Vellum hair constraints](https://www.sidefx.com/docs/houdini/shelf/vellumhair.html)
- [NASA Glenn: Schlieren Flow Visualization](https://www.grc.nasa.gov/www/k-12/airplane/tunvschlrn.html)
- Poly Haven CC0 assets: [nettle plant](https://polyhaven.com/a/nettle_plant),
  [Studio Small 08](https://polyhaven.com/a/studio_small_08).
- AmbientCG Ice002 PBR maps provide the ice microfracture surface detail. Texture
  coordinates travel with persistent particle identities; they are not projected
  anew from the camera every frame.

No user font masters or accepted fire, water, or air videos are modified here.
