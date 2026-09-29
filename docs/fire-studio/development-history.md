# Live Fire / CYBRDELIC 02

Serve `outputs/cybrdelic-type` and open `/elements/motion/bending/sigils/02/fire-live/` directly. This development preview is separate from the style 02 player until its visual quality matches the approved film.

## Fire-lit room

### Sources and fire types

The approved pre-preset runtime is saved in commit `647619b`.

**Source** selects the sigil, a movable free flame, campfire fuel bed, torch jet,
upright burning ring, spherical shell, broad fire wall, or explosion. Changing
source starts a fresh simulation and frames its extent. Restart preserves the camera. The six additional emitters use analytic 3D
fuel support in `fire-emitters.js`; the campfire and torch also have analytic log and burner props in room mode. Props receive live clustered light and occlude the volume; they are not fluid collision meshes.
Click/drag repositions continuous sources. Restart resets the selected preset;
Free fire retains its Clear fire behavior. Camera controls do not inject fuel.

**Fire type** changes the feed, soot yield and jet speed. Wood is the balanced
default, Gas produces less soot and blue reaction light, and Oil produces more soot. The shared emission model also changes the room lighting. These are artistic
combustion profiles, not calibrated material chemistry. Existing smoke keeps
advecting when the profile changes. On the sigil, the profile changes soot yield;
its authored ignition and jet timing remain intact.

**Explosion** now uses its own 384 × 384 × 64 volume over an 8 × 8 × 4
world-unit region. Its horizontal voxel spacing is slightly finer than the
original 640 × 360 × 32 flame volume; depth spacing stays comparable while the
physical depth more than doubles. Selecting Explosion reinitializes the page
with `?preset=explosion`; selecting another source restores the original volume.
Fuel profile and room preference survive that transition. Restart stays within
the current volume and retains the camera.

A single irregular 0.10-second charge injects varied fuel/air composition,
temperature and launch velocity. A reaction-dependent positive divergence
source drives expansion in the pressure solve (96 × 96 × 32, 24 Jacobi passes),
replacing the zero-divergence solve that resisted the blast. The old eleven
moving spherical fuel pockets and prescribed rolling-cap force were removed.
Oxygen enters through advection and bounded neighbor mixing instead of being
replenished throughout the fuel cloud. Ignition has a higher threshold so warm
fuel is not all active. Two scales of true 3D curl force act on the live gas;
the static vector-potential texture contains no images or animation. The
renderer and room lights use the same cooler emission curve. The render-time
noise-displacement trial was rejected and removed.

Trigger burst (or click the canvas) adds another charge to the current gas
state. Holding the mouse does not repeatedly detonate. Pause freezes the charge
clock. There is no prerecorded playback, blast damage or compressible shock
solver. Smoke and residual fuel continue to advect after injection closes.

The implementation is still a visual approximation. The opening can remain too
rounded and uniform, and fine flame detail does not match filmed fire. Captures
and rejected trials are in `work/fire-expansion-qa/`. References:
[SideFX pyro expansion](https://www.sidefx.com/docs/houdini/pyro/background.html),
[filmed petrol fireball](https://www.youtube.com/watch?v=sFe7sKz8HSU).

Smoke now uses four subcell density samples for the lighting grid, twelve
samples per shadow segment, and more scattering in cool soot with less in the
hot flame core. Temperature-dependent hot-soot emission is shared by volume
rendering and room lighting, allowing a brief incandescent tail after reaction
fades. Cold unlit soot remains dark; no room fill light was introduced.

Preset QA artifacts are in `work/fire-presets-qa/`. Eight captures across the
iterations had finite reduced GPU state and zero WebGL errors. Between 0.7 and
3.0 seconds after a burst, heat fell to 6.7% while soot retained 67.3% of its
earlier total. Manual checks covered preset/profile selection, moving a fuel
bed, shutoff, burst retriggering, pause and source framing. These checks do not
establish a new sustained frame-rate result or offline-render parity.

### Recognizable source behavior

Campfire fuel is divided into three pockets above crossed charred logs, with
lower buoyancy and faster cooling to keep the flame bed compact. The torch has
a visible narrow burner and a stronger, fast upward jet. The wall spans six
world units and has varying upward jets across its width.

The ring and sphere are sculpted fire effects: a circulating force field and
shorter heat lifetime hold an open torus and compact orb. The sphere circulates
around a tilted 3D axis. These forces act on the gas velocity; no rendered shape
mask clips the fire. The explosion has a finite charge, stronger radial impulse
and a brief expanding pressure-force pulse before buoyancy takes over. This is
an artistic incompressible solver, not a compressible shock simulation. Sphere
views use 64 interpolated ray samples through the original 32-layer volume;
explosions use 128 samples through 64 layers. Other sources keep 32 samples.

Source placement respects the floor clearance of each shape and prop. Selecting
a preset frames it automatically; manual zoom/pan and Restart retain their roles.

### Camera and demo controls

- Wheel/trackpad over the canvas zooms around the cursor, from 70% to 300%. The slider and +/− buttons also work on touch devices. This changes the camera lens, not simulation resolution.
- **Move view**, Shift-drag or right-drag pans without injecting fuel. **Fire** (or Escape) restores the fire tool. The camera remains adjustable while paused.
- **Focus fire** frames the current source at 130–250%, allowing more space for larger presets; **Reset view** (0) restores zoom, pan and angle without clearing the simulation.
- **Fullscreen** (F) keeps the controls with the scene; Escape exits the browser's fullscreen view. Space pauses/resumes and R restarts/clears. Form controls retain their normal keyboard interaction.
- Camera and input share the same unprojection, including zoom/pan in black-background mode. Frozen-state lighting is cached when inspecting a paused frame.

The default view is a dark room with a floor, back wall, side walls, ceiling, and shallow grid grooves. The **View angle** slider orbits the camera between -30° and +30°. Each viewing ray samples all 32 simulated depth layers at their actual world positions, so the fire has volume parallax and is occluded by the room surfaces. Pointer positions are unprojected onto the source plane; clicking near/below the floor places the source just above it. **Dark room** switches back to the original front view for comparison without resetting the fluid state.

`fire-room.js` samples current reaction, temperature and soot into a 128 × 64 × 16 field and reduces emission to 32 moving light clusters. Twelve samples integrate soot extinction along each source-to-receiver segment, clipped to the gas bounds. Both smoke and surfaces receive this attenuated illumination. Five 96 × 96 irradiance maps cache the room lighting, while thin 3 mm grid grooves are shaded with analytic pixel coverage in the display pass. The material is matte, with no glossy tile bevels. The room has no ambient fill, overhead light, or cursor-attached lamp: zero emission produces a black room.

This approximates direct area lighting and participating-medium shadows; it is not ray-traced global illumination. Room surfaces clip visible fire. The floor now removes subsurface gas and blocks downward velocity, but the room is not a general fluid obstacle solver. The gas domain is 1.8 world units deep, with broader, corrugated sources and velocity shear through depth. Pressure retains the previous 128 × 72 × 8 grid and 18 Jacobi iterations, with derivatives scaled to the deeper domain. The main simulation remains 640 × 360 × 32 at 30 steps per simulated second. Baseline, revised views, sequences, state checks and GPU timings are in `work/fire-quality-qa/`; the earlier room-only experiment remains in `work/fire-room-qa/`.

`fire-optics.js` shares emission and extinction between the volume and its lights. Temperature separates orange edges from hot yellow regions. Lower exposure, a partial luminance-preserving tone map, and a highlight-only bloom threshold retain more hot-region color and structure. Uneven fuel feed breaks up the cursor source through the evolving gas state; no texture is applied over the rendered flame.

The browser creates every frame from evolving GPU state. WebGL2 advances velocity, fuel, oxygen, temperature, soot, and reaction in an atlas volume. A MacCormack predictor and local limiter preserve scalar detail during transport. A coarse GPU pressure solve feeds velocity correction back into the next step. The renderer integrates the current volume through depth and maps linear radiance to the display. The pointer applies a force to the velocity field. Clicking the canvas switches to free-fire mode, clears the sigil, and ignites a persistent fuel source at the pointer. Dragging moves the source through the same volume; releasing leaves it burning, and a later click relocates it. Clear fire empties the volume; Return to sigil restores the original emitter. The sigil's 9.8 second ignition and decay cycle restarts with a fresh state, while free fire keeps running until cleared or the mode changes.

The renderer shades the simulated soot and reaction directly. Its earlier screen-space noise modulation was removed because it painted a repeated texture over the flame. The free-fire emitter supplies a thin, corrugated fuel sheet with changing shear and depth velocity. Holding the pointer supplies fuel without applying an outward force; only pointer movement transfers momentum to the nozzle. Releasing at the same position leaves the same source running.

`vorticity.js` measures live velocity curl and its magnitude gradient, then applies bounded confinement to retain rotating folds. Its 192 × 144 × 16 grid covers the entire sigil domain or follows a 4 × 5.6 × 1.8 region around the cursor source. Both modes use confinement. Cold empty cells skip derivative work; the scalar update skips empty-region confinement reads, and sigil cells outside the emitter bypass ignition/nozzle calculations while retaining identical air entrainment. These optimizations do not lower the main simulation resolution.

Soot has an independent lifetime: fuel-rich combustion yields more soot, hot oxygen oxidizes it (consuming oxygen and releasing heat), and cold soot disperses with a 0.055/s decay coefficient instead of the temperature's 1.15/s cooling coefficient. Its density reduces buoyancy through `temperature * 6.5 - soot * 0.32`. Fuel, oxygen, temperature and soot all use the full-resolution MacCormack transport and limiter. These are visual-model coefficients, not calibrated combustion chemistry.

In the optional black-background comparison mode only, `smoke-light.js` integrates soot toward an overhead inspection light using a 128 × 72 × 32 volume. Room mode uses the fire-only, soot-attenuated illumination described above. **Stop fuel** closes the source while remaining gas keeps burning, cooling and moving; click to reignite. Once all emission dies, room-mode smoke becomes invisible in the unlit room even though soot remains in the simulation. **Clear fire** empties the volume.

The emitter shader branches uniformly between sigil and free-fire sources, avoiding sigil texture sampling and emitter calculations in drag mode. Current-cell velocity uses an exact texel read, and uniform locations are cached. Transported scalars occupy one RGBA16F texture `(fuel, oxygen, temperature, soot)`; the other stores `(velocity.xyz, reaction)`. This halves the limiter's corner reads and removes redundant predictor samples without changing the transport algorithm, grid, or precision. GPU timing and smoke-shutoff evidence are recorded in `work/fire-smoke-qa/report.json` (local QA artifacts); the QA server and instrumentation are not part of the shipped runtime.

The Gaussian nozzle skips jet calculations beyond squared normalized radius 12, where injection is below one half-float subnormal quantum. This bounds emitter work without bounding transported fire or smoke. Script version parameters keep the packed field layout consistent across cached modules.

`source/` contains one **static emitter**, exported from the approved Fire 02 artwork. It specifies fuel support, ignition arrival, launch direction, and sheet thickness. The runtime loads the native 896 × 504 variant listed in `source/source.json`. These assets contain no rendered frames or animated fields. `source/export_source.py` reproduces the export from the original `work/element-motion/sigil-02-v2/source.npz`.

This runtime is a visual prototype, with a different fluid solver from the approved offline film. Its 640 × 360 × 32 volume uses 30 steps per second, corrected scalar advection, and a coarse pressure solve; the 896 × 504 projection is displayed at 1920 × 1080. The offline film used 896 × 504 × 56 cells, 90 solver steps per second, resolved vorticity, and full-grid pressure projection. Exact visual parity has not been reached. On this machine, the Codex in-app browser uses Intel UHD graphics for WebGL despite requesting a high-performance adapter, so rendered frame rate varies substantially. Compare the live view with the **Original film** link before using it as final portfolio footage.

### Quality-pass verification

`work/fire-quality-qa/report.json` records 20 captures across the iterations, all with zero WebGL errors and finite reduced state. The final drag sequence contains 20 distinct frames at 0.2 simulated-second intervals. Three seconds after shutting off fuel, heat falls to about 5% of its shutoff value and the soot centroid rises about 1.06 world units; residual fuel continues producing soot. The empty room is exactly RGB zero. Angle views retain the same underlying simulation state.

Performance remains a limitation. Short instrumented single-context sigil runs measured roughly 8 rendered FPS for the revised scene versus 11 for the previous room on this Intel GPU. Query instrumentation and system load affect wall timing; this is not a sustained production benchmark. Added volume activity, confinement and soot visibility cost GPU time. The source-support optimization preserves exact state sums while reducing emitter work. The heavier 12-layer/22-iteration pressure trial and 24-layer confinement trial were reverted; neither the main simulation grid nor the rendered projection was reduced. Sustained 30 FPS and the offline film's smallest filaments are not established.

The isolated `webgpu-experiment/`, `offline-flow-study/`, `procedural-experiment/`, and `sparse-experiment/` folders record alternative renderers and feasibility measurements. They are archived under `work/fire-studio-research-archive/`, outside the served source tree. None passed both the approved-look comparison and the 30 fps target; their own READMEs describe the observed limits. The approved film remains the portfolio presentation.

The recognizability pass is recorded in `work/fire-presets-qa/recognizability-report.json` and `recognizable-sources.jpg`: all six source families produced finite GPU state with zero WebGL errors. The image sheet shows individually framed views. The sphere remains a stylized guided fire orb; offline filament detail and a new sustained performance result are not established.

### Torch shape and motion pass

The torch now feeds a thin outlet above the burner instead of a hot Gaussian
reservoir. Fuel/air mixing, cooler injected gas, stronger spatial jet variation,
lower wood-jet speed, and torch-specific buoyancy/cooling/extinction reduce the
bulb base and long reactive thread. Campfire, torch and fire-wall feed vary with coherent
noise in the injected gas; the former regular high-frequency pulse is retained
only for other emitters. No noise is multiplied over the rendered flame.

Black-background inspection retains the campfire/torch props, with the existing
inspection key also revealing their surfaces. Both views integrate front to
back; props occlude the gas consistently. The black view computes only the
emission clusters needed to light props, skipping room shadow/receiver passes.
Room mode remains lit by the fire alone. Camera-only redraws reuse illumination.

Before/after motion sequences, bounded state checks, and frame traces are in
`work/fire-motion-qa/`. They are development evidence, not prerecorded runtime
assets. These visual coefficients remain an approximation of combustion.

Torch combustion also tapers smoothly below a dilute-fuel/oxygen mixing threshold, suppressing reactions in transported trace filaments. This is a scalar combustion rule, not a rendered shape mask.

At the new presets' flame fronts, a MacCormack correction outside the eight donor-cell bounds now falls back to the predictor for that step. The sigil and original free flame keep the previous clamp; valid corrections in the new presets retain the higher-order result. This addresses thin-front staircasing without changing the simulation grid.


## Optional scene lighting

Open **Scene lighting** below the view controls. Choose **Studio**, **Moonlight**,
or **Fire only**, then adjust either spotlight's intensity, color, direction,
height and beam width. Both lights aim at the shared horizontal/height target.
Ambient fill has independent intensity and color. Settings are saved locally
and survive source changes, including the explosion's separate simulation domain.
Changes apply to a paused volume without advancing the simulation.

The two spots use smooth cone falloff, distance attenuation and twelve-sample
soot transmittance for smoke and room receivers. The existing props receive the
spots and ambient light, but do not cast geometry shadows. Colors are converted
from sRGB to linear before lighting. Black-background mode supports the same
external lights; with external lighting disabled it retains the previous
inspection-light rendering.

**Room bounce** is approximate single-bounce diffuse GI: ten room patches sample
current direct receiver irradiance (including fire and spotlights), reflect it
using the stone albedo, and contribute to the volume and room. It is deliberately
labeled approximate; it is not path tracing, multiple scattering, or a converged
radiosity solve. The coarse patches can miss small pools of light. Dark stone
reflects little energy, so the effect is subtle. It is disabled without the room.
One extra receiver pass is used only when bounce is enabled. Illumination is
cached while paused and invalidated by lighting, simulation or room changes.

Lighting QA: `work/fire-lights-qa/` holds matching paused frames for Fire only,
Studio and isolated bounce, plus Moonlight against black. This addition does
not change the fluid solver or claim to fix the existing fire/explosion fidelity.

## Unified Fire studio (2026-09-27)

The main page now hosts both Original and 3D volume simulations through one set of controls. Scene, Library and Lighting switch views without navigating. The shared library includes 20 fire sources, 16 lighting rigs and six combined scenes. The former `pyro-gpu/` page is a redirect alias, not a second interface. Hidden views stop scheduling GPU work; switching simulation disposes the previous runtime. The original simulation remains the default. The experimental 3D solver remains slower and its earlier realtime gate is still unmet.

## Offline detail comparison (2026-09-27)

The Original renderer now uses the offline Fire 02 heat-to-color curve, reaction
emission response and non-blast soot extinction. Its unlit inspection view also
uses the offline scattering coefficients, reducing the grey veil over flame
fronts. Room illumination still samples the same shared emission model.
The Original presets now reject out-of-bounds MacCormack corrections per scalar,
so an overshoot in one field does not discard valid corrections in the others.
This uses a vector selection with no extra texture fetches or simulation passes.
Explosion optical coefficients and the 3D volume runtime are unchanged.

Same-time images and asynchronous GPU timings are in `work/fire-detail-qa/`.
These changes improve visibility and preserve some front structure; they do not
recover the offline film's smallest resolved curls. Offline uses 896 x 56 x 504
cells and 90 solver steps per second, versus 640 x 360 x 32 and 30 steps per
second for the Original sigil, with coarser pressure and vorticity grids.
A tighter vorticity-region trial was reverted after insufficient visual benefit
and higher measured GPU cost. No simulation or projection resolution was lowered.


## Burning solids and empty-space optimization

Build `burning-sources-2` adds finite surface-fuel objects (house, vehicle, mannequin, imported CYBR world tree, wood logs), swept/pulsed fuel jets, nine emission color looks and optional flow-driven ember tracers. Bonfire and hearth use the log geometry. The shared studio library exposes Objects and Jets categories; saved looks include color and ember visibility. Static geometry assets are generated by `tools/fire-sources/build.py`; provenance lives in `pyro-gpu/objects/manifest.json`.

Gas heats the surface; heated surfaces release fuel and sensible heat additively. Reaction creates soot in the common advected field. Relight preserves solid fuel; Restart replenishes it. Geometry is simplified, obstacle pressure uses an approximate damping treatment, and embers are one-way tracers rather than ignition-capable firebrands. Color looks other than Natural are art direction, not chemical spectra.

Object surface/brick intersection avoids simulating an entire source cube. A shared conservative occupancy halo supports empty-space ray skipping and replaces repeated lighting-neighbour scans. Velocity/scalar grids and visible ray sampling remain unchanged. The short native frozen-state test reduced lighting/render time about 20%, with matching captures; this is not a sustained browser FPS result. See `work/burning-sources-qa/RESULTS.md` for measurements and unresolved browser/GPU-load limitations.

## Reviewed forest sources (`forest-review-3`)

The tree-study proxy is replaced by tree 538 from the latest forest-surface
scene: 1.59 million original triangles, displaced bark and roots, and the
mature stand's actual individual leaves. It is rasterized separately from the
fluid collision grid and composited with the volume at its actual depth.
Both inspection spotlights use mesh shadow maps; internal fire/GI shadows
still use the coarse wood proxy. Source assets load only when a tree is used.

The library opens on 12 controlled tests. Basal ignition, damp fuel and crown
ignition have explicit, local starters. Surface heat, drying, pyrolysis, char,
leaf loss and widening of existing fissures respond to state rather than a
timed whole-tree ignition mask. Twelve neutral inspection lighting rigs are
separate from creative color looks; older blockout objects are labelled
Prototypes. Existing URLs and saved looks remain supported.

This does **not** implement branch fracture or collapse. The stiffness field
is diagnostic, not a mechanics solver. Fuel and thermal parameters are
accelerated and uncalibrated, and ember tracers cannot ignite new fuel.
See `tools/fire-sources/README.md` for asset reproduction and physical scope,
and `work/burning-sources-qa/FOREST_REVIEW.md` for validation and performance.
