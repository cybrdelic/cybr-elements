from pathlib import Path
import json,hashlib,shutil
R=Path(__file__).resolve().parent;ROOT=R.parents[2];SITE=ROOT/'outputs/cybrdelic-type';OUT=SITE/'elements/sigils'
if (R/'quality-hold.json').exists():raise SystemExit('Publication stopped: material quality was rejected. Read quality-hold.json.')
materials=json.loads((SITE/'elements/motion/subelements/dynamics/studies.json').read_text(encoding='utf-8'));reviews=json.loads((R/'reviews.json').read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
preserved=json.loads((R.parent/'dynamics/release.json').read_text())['preservedCore']
for name,digest in preserved.items():assert sha(SITE/'elements/motion'/name)==digest,('Original core changed',name)
sources={}
for variant in ['01','02']:
    source=json.loads((R/f'source-{variant}.json').read_text())
    assert sha(Path(source['source']))==source['sourceSha256'],('Original sigil changed',variant)
    sources[variant]=source['sourceSha256']
entries=[]
for item in materials:
    for variant in ['01','02']:
        key=item['id']+'-'+variant;meta=json.loads((R/'media'/f'{key}.json').read_text(encoding='utf-8'));movie=R/'media'/f'{key}.mp4'
        assert meta['nb_frames']=='450' and meta['width']==1920 and meta['height']==1080 and sha(movie)==meta['sha256'],key
        decoded=json.loads((R/'sequence-check'/f'{key}.json').read_text())
        assert decoded['decodedFrames']==450 and decoded['sha256']==meta['sha256'],('Missing full-frame decode',key)
        assert reviews[item['id']]['videoHashes'][variant]==meta['sha256'] and reviews[item['id']]['sampledFrames'],('Missing visual review',key)
        entries.append({'id':key,'material':item['id'],'variant':variant,'title':item['title'],'group':item['group'],'video':key+'-'+meta['sha256'][:10]+'.mp4','poster':key+'-'+meta['sha256'][:10]+'.jpg','sha256':meta['sha256']})
assert len(entries)==52
OUT.mkdir(parents=True,exist_ok=True)
for item in entries:
    for ext in ['mp4','jpg']:shutil.copyfile(R/'media'/f"{item['id']}.{ext}",OUT/item['video' if ext=='mp4' else 'poster'])
(OUT/'studies.json').write_text(json.dumps(entries,indent=2),encoding='utf-8');shutil.copyfile(R/'gallery.html',OUT/'index.html')
notes='<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sigil animation notes</title><style>body{background:#000;color:#d9e0e4;font:16px/1.6 system-ui;max-width:850px;margin:40px auto;padding:0 24px}a{color:inherit}h1{font-weight:400}</style><a href="./">Back to the sigils</a><h1>Animation notes</h1><p>Both forms use the unchanged approved source artwork and the earlier 15-second writing, camera, hold and release timing. No white text layer is added.</p><p>The surface studies reuse the material shaders from the dynamics gallery on new sigil geometry. Their motion uses an authored bending support with damped motion and a gravity release. These are material retargets, not new FLIP or MPM bakes. Gas versions use the existing 3D gas-line solver. Sound, pressure and heat are amplified optical diagnostics. Fictional techniques remain authored effects.</p><p>The earlier material realism limitations still apply. This set changes the source shapes and choreography; it is not a claim that all materials are now photoreal.</p>'
(OUT/'notes.html').write_text(notes,encoding='utf-8')
page=SITE/'elements/motion/subelements/dynamics/index.html';html=page.read_text(encoding='utf-8');marker='Open all 52 sigil films'
if marker not in html:page.write_text(html.replace('<h1>','<p><a href="/elements/sigils/">'+marker+'</a></p><h1>',1),encoding='utf-8')
(R/'release.json').write_text(json.dumps({'count':52,'variants':['01','02'],'url':'http://127.0.0.1:8767/elements/sigils/','videoHashes':{s['id']:s['sha256'] for s in entries},'sourceHashes':sources,'preservedCore':preserved},indent=2),encoding='utf-8')
print('Published',len(entries),'verified sigil films:',OUT)
