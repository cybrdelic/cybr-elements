"""Publish a complete, visually reviewed candidate gallery; retain the originals."""
from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parent
ROOT=R.parents[2]/'outputs/cybrdelic-type/elements/motion'
SITE=ROOT/'subelements';OUT=SITE/'dynamics'
TARGETS='lava metal foam ice combustion lightning sand mud plants snow glass crystal blood healing spirit energy lightning-redirection seismic sound flight spirit-projection pressure heat'.split()
EXPECTED={'fire-sheets.mp4':'4c44bc8d485b0341aa4730a1ee544913e0cb7986a9ac0a47599ebb711e6f9f58','water-optical.mp4':'f2e1f8001affdc84ffbcb87a16301fd4821e4102ec9c67ffbf0a8b5b3f7f793a','air-filaments-lit.mp4':'bdb7d06ba622ad102b51c4d48a53d7d17f1781498ab6fb979ab6fc72daaa2bef'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,h in EXPECTED.items():assert sha(ROOT/name)==h,('Accepted core changed',name)
reviews=json.loads((R/'visual-review.json').read_text(encoding='utf-8'))
notes={
'lava':'Cooling crust over a hot viscous flow.',
'metal':'A steel sheet folds and retains its deformation.',
'foam':'Surface-carried foam drains and separates into finer spray.',
'ice':'Cooling liquid forms brittle bonds and breaks into frozen fragments.',
'combustion':'A reactive jet ends in a short expanding ignition.',
'lightning':'Brief branching channels with repeated return strokes.',
'sand':'Frictional grains spread and separate under the shared gesture.',
'mud':'A wet viscous flow with fine mineral roughness.',
'plants':'Connected stems bend while attached leaves unfurl.',
'snow':'Compacting snow breaks apart into finer particles.',
'glass':'Persistent glass fragments follow the gesture and release under rigid-body dynamics.',
'crystal':'Faceted mineral fragments with absorption and internal reflections.',
'blood':'A cohesive red liquid with absorption through its depth.',
'healing':'A localized repair front closes damaged plant tissue.',
'spirit':'Organized luminous channels relax along the shared path.',
'energy':'Two interwoven channels carry traveling light pulses.',
'lightning-redirection':'Incoming discharge, a guided middle section, and an outgoing release.',
'seismic':'An elastic wave displaces a granular rock sample.',
'sound':'An optical view of propagating compression and rarefaction wavefronts.',
'flight':'Fine tracers follow a counter-rotating wake.',
'spirit-projection':'A coherent copy of the original sigil separates from its source.',
'pressure':'Sparse rarefaction pulses and their rebound, viewed through index gradients.',
'heat':'An optical visualization reveals the refractive gradients of heated air.'}
validated={}
for k in TARGETS:
    m=R/'media'/f'{k}.json';d=json.loads(m.read_text(encoding='utf-8'))
    assert d.get('fresh') and d.get('nb_frames')=='120' and d.get('width')==1920 and d.get('height')==1080,(k,'missing frame receipt')
    assert d.get('clearCornerMax',d['blackCornerMax'])<=3 and sha(R/'media'/f'{k}.mp4')==d['sha256'],k
    assert reviews[k]['frames'] and reviews[k]['observation'] and reviews[k]['sampledSequenceReviewed'],(k,'visual review missing')
    assert reviews[k]['videoSha256']==d['sha256'],(k,'visual review refers to an older video')
    validated[k]=d
OUT.mkdir(exist_ok=True)
studies=json.loads((SITE/'studies.json').read_text(encoding='utf-8'))
for item in studies:
    k=item['id']
    if k in validated:
        d=validated[k];stem=k+'-'+d['sha256'][:10]
        for ext in ['mp4','jpg']:shutil.copyfile(R/'media'/f'{k}.{ext}',OUT/f'{stem}.{ext}')
        item.update(previous='../'+item['video'],video=stem+'.mp4',poster=stem+'.jpg',note=notes[k],rebuild='dynamics')
    else:
        for key in ['video','poster','previous']:
            if key in item:item[key]='../'+item[key]
(OUT/'studies.json').write_text(json.dumps(studies,indent=2),encoding='utf-8')
html=(SITE/'index.html').read_text(encoding='utf-8')
html=html.replace('../materials.html','../../materials.html').replace('../../../?study=6','../../../../?study=6').replace("fetch('../shared-trail.json')","fetch('../../shared-trail.json')")
html=html.replace('Material rebuilds.','Bending dynamics.').replace('<p><a href="realism-tests/">New surface tests and rebuild scope</a></p>','<p><a href="../">Previous gallery</a> · <a href="review.html">Review notes</a></p>')
html=html.replace('The same gesture, with rebuilt surfaces, interiors, and lighting.','A shared emitter gesture with independent material dynamics. These are review candidates; the previous versions remain available for comparison.')
html=html.replace('background:#080a0b','background:#000')
(OUT/'index.html').write_text(html,encoding='utf-8')
from html import escape
rows=''.join('<tr><th>'+escape(next(s['title'] for s in studies if s['id']==k))+'</th><td>'+escape(reviews[k]['observation'])+'</td></tr>' for k in TARGETS)
reviewhtml='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>CYBRDELIC / Review notes</title><style>body{background:#000;color:#ddd;font:16px/1.6 system-ui;max-width:950px;margin:40px auto;padding:0 24px}a{color:inherit}h1{font-weight:400}table{border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-top:1px solid #333;padding:16px 12px}th{min-width:140px}</style><a href="./">Back to the studies</a><h1>Dynamics rebuild review</h1><p>Implemented without Houdini, using Warp, NumPy/SciPy, Blender Cycles/Bullet, and existing liquid caches. These are simplified graphics solvers and authored effects, not reproductions of Houdini’s proprietary implementations or a claim of photoreal quality.</p><table>'+rows+'</table>'
(OUT/'review.html').write_text(reviewhtml,encoding='utf-8')
manifest={'replaced':TARGETS,'preservedCore':EXPECTED,'videos':{k:v['sha256'] for k,v in validated.items()},'status':'complete review candidates, not certified photoreal finals'}
(OUT/'release.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(R/'release.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
# Add navigation without overwriting the earlier comparison candidates.
for page in [SITE/'index.html',SITE/'realism-tests/index.html']:
    source=page.read_text(encoding='utf-8');href='dynamics/' if page.parent==SITE else '../dynamics/'
    banner='<p style="padding:16px;border-bottom:1px solid #333;background:#000;color:#ddd"><a style="color:inherit" href="'+href+'">Open the new dynamics rebuild: all 23 studies</a></p>'
    if 'Open the new dynamics rebuild: all 23 studies' not in source:
        updated=source.replace('<body>','<body>'+banner,1) if '<body>' in source else source.replace('<main>','<main>'+banner,1)
        assert updated!=source,('Navigation insertion failed',page)
        page.write_text(updated,encoding='utf-8')
print('Published 23 complete candidate clips:',OUT)
