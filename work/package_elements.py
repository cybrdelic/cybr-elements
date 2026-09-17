from pathlib import Path
import json,hashlib,zipfile
OUT=Path(__file__).parent.parent/'outputs/cybrdelic-elements'
state=json.loads((OUT/'status.json').read_text())
assert state['status']=='complete' and len(state['completed'])==6
assert all(c['video'].endswith('-final.mp4') for c in state['completed'] if c['element']=='water')
manifest=[]
for c in state['completed']:
 path=OUT/c['video'];check=json.loads((OUT/f"{c['element']}-{c['variant']}-verification.json").read_text())
 meta=check['metadata'];assert meta['nb_read_frames']=='450' and meta['r_frame_rate']=='30/1' and float(meta['duration'])==15
 assert meta['width']==(3840 if c['element']=='water' else 2560)
 assert meta['height']==(2160 if c['element']=='water' else 1440)
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 manifest.append({'element':c['element'],'style':c['variant'],'file':path.name,'bytes':path.stat().st_size,'sha256':h.hexdigest(),**meta})
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2))
(OUT/'README.txt').write_text('''CYBRDELIC / ELEMENTS

Six MP4 intros: water, air, and earth in both approved wordmark styles.
01: Fluid sigil. 02: Cut blackletter.

Water: native 3840 x 2160.
Air and earth: 2560 x 1440.
All clips: 15 seconds, 30 fps, H.264, silent.

The word forms along a travelling path, pulls back for a hold, and releases.
The water exports include the corrected continuous stream exit.

Motion models
Water: authored suspended capillary sheet, refractive rendering, and ballistic droplets; a reduced model, not a FLIP bake.
Air: advected 2D condensation density with diffusion and evaporation, rendered as a scattering volume.
Earth: individually moving stone fragments and grit with gravity release.

manifest.json contains dimensions, frame counts, and SHA-256 checksums.
''',encoding='utf8')
archive=OUT/'Cybrdelic-Elements.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
 for row in manifest:z.write(OUT/row['file'],row['file'])
 for name in ['README.txt','manifest.json']:z.write(OUT/name,name)
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print(json.dumps({'videos':len(manifest),'archive':str(archive),'archiveBytes':archive.stat().st_size,'validated':True}))
