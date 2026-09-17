"""Publish three reviewed local revisions together and retain their predecessors."""
from pathlib import Path
import hashlib,json,shutil
R=Path(__file__).resolve().parent;O=R/'sigil-02-alive';W=R/'sigil-02-water-arrival/full';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
preserved={name:sha(P/name) for name in ['fire-02.mp4','air-02.mp4','water-02-r3.mp4','earth-02-r3.mp4','lightning-02-r3.mp4']}
assert preserved['fire-02.mp4']=='3bb0dd50aa6c2f4ce55edbf18753fc9db27b656d83d4efbcd29a4a33282e83f6'
assert preserved['air-02.mp4']=='80d89a5bd8ccb347da1659b5dcc8f8417db156bffe66759498adab4cb40b7120'
artifacts=[]
for name in ['water','earth','lightning']:
 folder=W if name=='water' else O;a=json.loads((folder/('audit.json' if name=='water' else f'{name}-audit.json')).read_text())
 assert a['visualStatus']=='agent-reviewed-improvement',name
 src=folder/f'{name}-candidate.mp4';assert sha(src)==a['sha256']
 shutil.copy2(src,P/f'{name}-02-r4.mp4');shutil.copy2(folder/('poster.jpg' if name=='water' else f'{name}-poster.jpg'),P/f'{name}-r4-poster.jpg')
 artifacts.append(dict(element=name,path=str(P/f'{name}-02-r4.mp4'),sha256=a['sha256'],duration=10))
page=(P/'index.html').read_text(encoding='utf-8');(O/'previous-player.html').write_text(page,encoding='utf-8')
marker="const revised=new Set(['water','earth','lightning']),previous=document.getElementById('previous');let active='fire',showPrevious=false;"
helpers="\nconst revisions={water:4,earth:4,lightning:4};\nfunction movieFor(name,prior=false){return revisions[name]?`${name}-02-r${revisions[name]-(prior?1:0)}.mp4`:`${name}-02.mp4`;}\nfunction posterFor(name,prior=false){return name==='fire'?'poster.jpg':revisions[name]?`${name}-r${revisions[name]-(prior?1:0)}-poster.jpg`:`${name}-poster.jpg`;}"
assert marker in page and 'const revisions=' not in page;page=page.replace(marker,marker+helpers)
page=page.replace("name==='fire'?'poster.jpg':revised.has(name)?`${name}-r3-poster.jpg`:`${name}-poster.jpg`",'posterFor(name)').replace("revised.has(name)?`${name}-02-r3.mp4`:`${name}-02.mp4`",'movieFor(name)').replace("showPrevious?`${active}-r2-poster.jpg`:`${active}-r3-poster.jpg`",'posterFor(active,showPrevious)').replace("showPrevious?`${active}-02-r2.mp4`:`${active}-02-r3.mp4`",'movieFor(active,showPrevious)')
assert 'film.src=movieFor(name)' in page and 'film.src=movieFor(active,showPrevious)' in page
(P/'index.html').write_text(page,encoding='utf-8');assert preserved=={name:sha(P/name) for name in preserved}
(O/'publication.json').write_text(json.dumps(dict(artifacts=artifacts,preserved=preserved,userAccepted=False),indent=2))
print('Published water, earth, lightning r4 together. Fire, air and all predecessors unchanged.')
