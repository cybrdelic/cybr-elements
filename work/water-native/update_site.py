from pathlib import Path
import json,shutil
R=Path(__file__).resolve().parent;S=R.parent.parent/'outputs/cybrdelic-type/elements'
status=json.loads((S/'status.json').read_text())
for c in status['completed']:
 if c['element']=='water':
  v=c['variant'];assert (S/f'water-{v}-native.mp4').exists()
  c.update(video=f'water-{v}-native.mp4',poster=f'water-{v}-native.jpg',width=3840,height=2160,seconds=8,fps=24,scene=f'water/?variant={v}')
status.update(status='complete',current=None);(S/'status.json').write_text(json.dumps(status,indent=2))
p=S/'index.html';html=p.read_text(encoding='utf-8')
html=html.replace('Two wordmarks, three new treatments. Water in native 4K; air and earth in 1440p. Each intro is 15 seconds at 30 fps.','Study 06’s two approved sigils. Water rebuilt with the original offline FLIP solver and Three.js renderer: native 4K, 8 seconds at 24 fps. Air and earth: 1440p, 15 seconds at 30 fps.')
html=html.replace('<a href="../typefaces/">Typefaces</a>','<a href="../typefaces/">Typefaces</a><a href="../?study=6">Approved sigils</a>')
html=html.replace("'<span>'+c.width", "'<span>'+c.width")
needle="const a=document.querySelector('#link-'+id);"
replacement="if(c.scene){const scene=document.createElement('a');scene.href=c.scene;scene.textContent='Open water scene ↗';scene.style.cssText='display:block;margin-top:12px;font-size:12px';el.append(scene)}"+needle
if 'Open water scene' not in html:html=html.replace(needle,replacement)
# Remove the obsolete temporary water preview so it cannot flash before status loads.
start=html.find("const opening=document.querySelector('#media-water01');")
end=html.find('async function refresh()',start)
if start>=0 and end>start:html=html[:start]+html[end:]
p.write_text(html,encoding='utf-8')
notes='''# CYBRDELIC water / native renderer rebuild

Both sources are the full approved Study 06 silhouettes: 01 Fluid sigil and 02 Cut blackletter. No substitute font or centerline tube is used.

The original offline FLIP III.1 numerical solver, quality profile, reconstruction and Three.js water shader match the user’s local source by SHA-256. A new scene adapter supplies the source geometry, camera, and simple backdrop. The offline project itself is unchanged.

Water receives ballistic launch position and velocity only at birth. There are no home-position springs, continuing letter guides, animated vertex targets, repeated silhouette replenishment, or opacity-based logo disappearance. Slow motion around formation provides a brief display interval; gravity then brings the liquid into the basin, where it splashes and settles. The ending intentionally retains the physical water rather than deleting it on screen.

The first two source tests—vertical replenishment and shallow-surface replenishment—were rejected after visual review. The retained shot uses one-time emission, 48,085 / 50,400 particles, 2.5 cm simulation cells and the reference reconstruction spacing of 0.43 cells. Only empty reconstruction space is cropped; voxel spacing is preserved.

Primary isolated droplets are rendered once through the original renderer. No artificial fragment groups or decorative secondary spray cloud is added. The renderer uses its original screen-space dielectric optics, which are an approximation and can still look glass-like in a still image.

Each video contains 192 distinct simulated states at native 3840 × 2160, 24 fps, eight seconds. Playback varies smoothly in speed around formation; it is not real-time playback. See the verification JSON for physical durations, state checks, source hashes and export hashes.

The current versions are integrated into the existing Elements gallery, with links to the replayable Three.js scene and the approved artwork. Earlier files and the font package are preserved.
'''
(R.parent.parent/'outputs/cybrdelic-water-native-notes.md').write_text(notes,encoding='utf-8')
print('Updated existing Elements site with both native water videos')
