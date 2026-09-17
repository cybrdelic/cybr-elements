"""Derive the existing water reconstruction/optics without changing its look."""
from pathlib import Path
import sys
R=Path(__file__).resolve().parent
s=(R/'sigil_02_water_hold_mesh.py').read_text().replace("O=R/'sigil-02-water-hold'","O=R/'sigil-02-water-arrival'")
s=s.replace("frames=range(60,166,3) if preview else [45,75,120,165] if pilot else range(300)","frames=range(9,121,3) if preview else [12,24,36,48,60,75,90,120] if pilot else range(300)")
s=s.replace("if not pilot:\n  while len(list(out.glob('*.mesh.gz')))>=5", "if not pilot and not preview:\n  while len(list(out.glob('*.mesh.gz')))>=5")
s=s.replace("[45,75,120,165,200,240,299]","[24,48,75,90,120,165,200,240,299]")
if '--full' in sys.argv:
 s=s.replace("O=R/'sigil-02-water-arrival'","O=R/'sigil-02-water-arrival/full'")
 s=s.replace('for f in frames:\n',"for f in frames:\n if (O/f'frames/{f:04}.jpg').exists() and (out/f'{f:04}.json').exists():continue\n")
(R/('sigil_02_water_arrival_full_mesh.py' if '--full' in sys.argv else 'sigil_02_water_arrival_mesh.py')).write_text(s)
s=(R/'sigil_02_water_hold_render.py').read_text().replace('sigil-02-water-hold','sigil-02-water-arrival')
s=s.replace("else 24;s.cycles", "else 12;s.cycles").replace("else 1280;s.render.resolution_y=1080 if '--full' in sys.argv else 720", "else 768;s.render.resolution_y=1080 if '--full' in sys.argv else 432")
s=s.replace("else [45,75,120,165]","else [12,24,36,48,60,75,90,120]")
if '--full' in sys.argv:s=s.replace('sigil-02-water-arrival/','sigil-02-water-arrival/full/')
(R/('sigil_02_water_arrival_full_render.py' if '--full' in sys.argv else 'sigil_02_water_arrival_render.py')).write_text(s)
print('Derived arrival mesh and render scripts; existing release and water optics retained.')
