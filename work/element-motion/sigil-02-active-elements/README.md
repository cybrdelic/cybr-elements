# Delivered revision

All four films are encoded, visually reviewed, published in the existing 02
player, and verified for browser playback. Water is 11.2 seconds; ice, lava
and electricity are 10 seconds each. All are 1920 x 1080 at 30 fps.
The rejected ice render was replaced before publication. See `completion.json`,
`browser-verification.json`, and `protected-baseline-audit.json` for receipts.
User acceptance is still pending.

# Cybrdelic 02 — active water and additional materials

This is the revision requested on September 16–17, 2026. The approved 02
artwork, black backdrop, existing player, and accepted fire, air and earth
films are preserved. New films are not published until decoded and reviewed.

## Water

The hold is a new forward native APIC/FLIP calculation, not a deformation of
the old rendered lettering. Gravity remains active. A spatially varying
boundary force contains horizontal/depth motion; a vertical bending force
waits for sag before restoring height. A deterministic 1/193 subset of the
original liquid parcels is exempted from upward recovery. This is an authored
bending control, not a claim that unsupported hovering water occurs naturally.

Pressure projection, transport, surface tension and floor collisions are
solved by the existing native solver. The initial 138,022 material parcels
remain accounted for. Sparse liquid clusters are reconstructed as droplets
from their own volume and velocity; they are not added to a meshed copy of the
same mass. Droplet detail is limited by the solver's particle spacing.

The CPU preview has 24,698 parcels and 240 frames. All pressure solves converged
and all positions remained finite. Its 90th-percentile sag was approximately
0.14 world units; 7,572 parcels recovered at least 0.025 world units between
the sampled held states. Two rejected containment settings are retained as
small CPU comparisons; neither was promoted to a full-resolution render.

The finished edit reuses the existing loose floor-lift opening. A 0.20-second
editorial overlap joins that opening to the new held simulation. The opening
itself remains reverse playback of the earlier solved breakup. The new hold
and release run forward. These are explicitly different processes.

## Ice and lava

These use the approved 02 interlocking 3D fractures, bounded quaternion
assembly, and Bullet inter-body/floor collisions after release. Ice has
transmission, absorption, scattering and rough fracture surfaces. Lava has
separate hot interior geometry beneath displaced, scanned basalt crust, with
authored cooling and slow relative motion before release.

They are solid-fracture material effects. They do **not** implement liquid-lava
rheology, latent-heat freezing, thermally driven fracture creation, or a
calibrated ice constitutive law. No full phase-change simulation is claimed.

## Atmospheres and electricity

Local gas uses CPU semi-Lagrangian advection, buoyancy, dissipation and FFT
pressure projection, with absorbing outer boundaries. The fields are cached
as 3D texture atlases, not screen-space smoke overlays. Lava's volume extends
to 8.1 world units so its plume does not hit the old low ceiling.

Electricity uses existing 3D Laplacian-growth discharge trees constrained to
the approved 02 control volume, with separate trunk/fork current levels,
changing discharge families and local return pulses. Their pulsed local lighting illuminates
the surrounding gas, with dim studio fill for visible cloud depth. Explicit
trilinear atlas sampling avoids Eevee mip filtering mixing unrelated density
slices; the rejected halo, box and coarse-grid checks are retained. This is an authored visual discharge model, not a
calibrated atmospheric plasma prediction.

Cycles renders water, ice and lava. Electricity uses Eevee volumetric lighting
with a frustum fitted to the scene. Both output 1920 × 1080 at 30 fps. Renderer
comparison images and experimental native-grid code are retained; the native
grid conversion was not adopted because it failed the performance/appearance
comparison. GPU renders run serially after concurrent jobs slowed this laptop.

## Evidence and scripts

- `plan.json`, `STATUS.json`: scope and live work state.
- `water-cpu/physics-audit.json`: CPU dynamics checks.
- `water-full/particles/manifest.json`: full solver diagnostics.
- `water-full/mesh/*.json`: surface/droplet volume accounting.
- `*-cpu-review.jpg`: representative CPU sequence checks.
- `*-review.jpg`, `*-audit.json`: final encoded sequence review and integrity.
- `publication.json`: exact media versions and hashes of protected films.
- `browser-verification.json`: player selection, download and playback checks.

Entry points are `sigil_02_active_water_run.py`, `sigil_02_atmosphere.py`,
`sigil_02_electric_tree_export.py`, `sigil_02_new_materials.py`,
`sigil_02_active_material_queue.py` and `sigil_02_active_finish.py` in the parent
directory. Old videos and solver sources remain intact. Large old render logs
were losslessly compressed, duplicate movie working copies were replaced with
verified hardlinks, and redundant old JPG frames were removed only after
verifying their complete encoded movie.

User acceptance is pending. Rendering and numerical checks alone do not prove
that these materials meet the user's visual standard.

## Review evidence added during final production

Water encodes to 336 frames (11.2 seconds). All 240 new forward-simulation
frames retain 138,022 original parcels; pressure solves converged, all values
are finite, and the maximum measured reconstructed volume discrepancy is
0.174%. These are numerical checks, not proof of visual realism. The final
contact sheet and detailed hold/transition sheets were reviewed.

The hold has restrained small shedding and travelling sag/recovery. The
0.20-second editorial transition from the prior opening changes fine surface
detail and is not a continuous single forward solve. The optical cards,
control-force choices, emissive cooling and discharge envelopes are authored.

Final full renders use OptiX denoising, matching the water renderer. The initial
CPU-denoised ice frames are retained as a comparison; they were rerendered,
not mixed into the final sequence. Cycles uses its native linear interpolation
for density slices; explicit eight-sample interpolation is needed only in
Eevee to prevent atlas mip leakage.

The first full-size ice hold exposed a flat gray highlight problem that its
small pilot concealed. That run was stopped; representative rejected frames
remain in `ice/rejected-flat-ice-frames`. The revised look lowers broad key
illumination, strengthens blue depth absorption, and rounds/roughens the
render surface. Rigid collision hulls and their gas-emitter trajectories stay
unchanged; this is a shading/surface refinement, not a new freezing solver.
A new full-resolution hero gate is required before the remaining ice render.

The refined ice full-resolution hero and final encoded sequence both passed
agent visual review. No further renders or review gates remain pending.
