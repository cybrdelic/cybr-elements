from pathlib import Path
import json,hashlib,shutil,re
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parent;O=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements'
notes={
 'lava':'A hot viscous core, cooling basalt skin, and exposed melt where the surface stretches.',
 'metal':'A formed steel strip retains its section and strikes the floor as a solid body.',
 'foam':'Packed wet cells over a coherent body, with gradual drainage and collapse.',
 'ice':'Clouded and frosted ice holds together before breaking into contacting pieces.',
 'glass':'Cast glass carries depth, green absorption, and a brittle release.',
 'crystal':'Intergrown quartz and amethyst with mineral roots and optical interiors.',
 'mud':'Cohesive wet soil with finer grit and restrained surface highlights.',
 'blood':'A dark absorbing liquid with a wet surface and preserved flow.',
 'plants':'Photographed nettle geometry, irregular shoots, and unfolding foliage.',
 'sand':'Fine grains pack, collide, lose momentum, and accumulate.',
 'snow':'Porous ice aggregates flutter, drag through the air, and settle.',
 'combustion':'A focused ignition followed by expanding reactive flow and cooling soot.',
 'lightning':'Brief leaders and return strokes with persistent branching within each flash.',
 'lightning-redirection':'An incoming strike is received, conducted along the gesture, and released.',
 'healing':'A moving repair front closes torn foliage and restores its color.',
 'spirit':'A solid form clears from dark material into a warm luminous surface.',
 'energy':'Opposing charges travel across a solid subject and illuminate its surface.',
 'spirit-projection':'A recognizable translucent form separates from its solid source.',
 'seismic':'An elastic disturbance travels through a rough material carrier and fine grains.',
 'sound':'Vibration is carried by a tensioned strip and fine surface grains.',
 'flight':'Sparse entrained particles reveal a moving vortical wake.',
 'pressure':'Fine particles compress toward the moving source and rebound after release.',
 'heat':'An incandescent source sheds heat and cools toward darkness.'}
assert len(notes)==23
accepted=json.loads((O.parent/'material-review.json').read_text(encoding='utf-8'))['acceptedMaterialVideos']
core={item['file']:item['sha256'] for item in accepted.values()}
for name,digest in core.items():assert hashlib.sha256((O.parent/name).read_bytes()).hexdigest()==digest,('Accepted core changed',name)
records=[];black=[]
for K in notes:
 report=R/f'{K}-integrity.json';assert report.exists(),('Missing encoded video',K);row=json.loads(report.read_text(encoding='utf-8'));video=O/row['file'];assert hashlib.sha256(video.read_bytes()).hexdigest()==row['sha256'];records.append(row)
 ext='png' if K in ['metal','plants','healing'] else 'jpg';corners=[];digests=[]
 for f in range(120):
  p=R/f'{K}-frames/{f:04}.{ext}';digests.append(hashlib.sha256(p.read_bytes()).hexdigest())
  with Image.open(p) as im:
   a=np.asarray(im);corners.append(max(int(patch.max()) for patch in [a[:12,:12],a[:12,-12:],a[-12:,:12],a[-12:,-12:]]))
 assert hashlib.sha256(''.join(digests).encode()).hexdigest()==row.get('sourceFrameDigest'),(K,'encoded video is stale')
 assert max(corners)<=2,(K,'nonblack corner',max(corners));black.append({'id':K,'frames':120,'maxCornerChannel':max(corners)})
# Preserve the published baseline and all accepted core clips.
base=O/'studies-before-v4.json'
if not base.exists():shutil.copy2(O/'studies.json',base)
studies=json.loads(base.read_text(encoding='utf-8'));byId={x['id']:x for x in records}
for study in studies:
 K=study['id']
 if K not in notes:continue
 old=study['video'];row=byId[K];suffix='?v='+row['sha256'][:12];study.update(previous=old,video=row['file']+suffix,poster=Path(row['file']).with_suffix('.jpg').name+suffix,note=notes[K])
for name in ['studies.json','revised.json']:(O/name).write_text(json.dumps(studies,indent=2),encoding='utf-8')
p=O/'index.html';html=p.read_text(encoding='utf-8');html=html.replace('<p><a href="realism-tests/">New surface tests and rebuild scope</a></p>','<p>23 rebuilt studies. Pitch-black backgrounds. Solo playback and synchronized comparison.</p>');html=html.replace('The same gesture, with rebuilt surfaces, interiors, and lighting.','Each effect uses the shared source gesture.');html=html.replace('video{display:block;width:100%;height:100%}','video{display:block;width:100%;height:100%;background:#000}')
credits='<p>CC0 assets: <a href="https://polyhaven.com/a/nettle_plant">Nettle Plant</a>, <a href="https://polyhaven.com/a/marble_bust_01">Marble Bust 01</a>, <a href="https://polyhaven.com/a/metal_plate_02">Metal Plate 02</a>, <a href="https://polyhaven.com/a/rock_boulder_cracked">Rock Boulder Cracked</a>, <a href="https://polyhaven.com/a/studio_small_08">Studio Small 08</a>, and <a href="https://ambientcg.com/view?id=Ice002">Ice 002</a>. Powered by Poly Haven.</p>'
if 'Marble Bust 01' not in html:html=html.replace('</footer>',credits+'</footer>')
p.write_text(html,encoding='utf-8')
(O/'realism-tests/index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0;url=../?v=materials-4"><title>CYBRDELIC material rebuilds</title></head><body style="background:#000;color:#ddd;font:16px Arial"><p><a style="color:inherit" href="../?v=materials-4">Open the complete material gallery.</a></p></body></html>',encoding='utf-8')
report={'revision':4,'rebuiltCount':23,'preservedVariants':['blue-fire','steam','smoke'],'acceptedCoreHashes':core,'backgroundChecks':black,'videos':records,'limits':['The source gesture is directed; material responses use the recorded fluid solve, rigid-body contacts, particle contacts, elastic waves, or authored field behavior as appropriate.','Spirit, healing, energy and projection are visual interpretations. These are not calibrated scientific simulations.'],'sources':[{'name':'Poly Haven','url':'https://polyhaven.com/','license':'CC0'},{'name':'ambientCG Ice 002','url':'https://ambientcg.com/view?id=Ice002','license':'CC0'}]}
(O/'rebuild-4.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print('23 replacements published; 2760 source frames checked; accepted core hashes preserved.')
