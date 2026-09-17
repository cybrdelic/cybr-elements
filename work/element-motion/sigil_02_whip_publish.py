"""Publish only reviewed water r6; retain r5 and every other element."""
from pathlib import Path
import hashlib,json,shutil
from PIL import Image
R=Path(__file__).resolve().parent;O=R/'sigil-02-water-whip';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=json.loads((O/'audit.json').read_text());assert a['visualStatus']=='agent-reviewed-improvement'
assert digest(O/'water-candidate.mp4')==a['sha256'] and a['decodedFrames']==390
protected=['fire-02.mp4','air-02.mp4','lightning-02-r4.mp4','water-02-r5.mp4','earth-02-r5.mp4'];before={n:digest(P/n) for n in protected}
page=(P/'index.html').read_text(encoding='utf-8');assert 'const revisions={water:5,earth:5,lightning:4}' in page
(O/'previous-player.html').write_text(page,encoding='utf-8')
shutil.copy2(O/'water-candidate.mp4',P/'water-02-r6.mp4')
Image.open(O/'full/frames/0210.jpg').resize((1280,720)).save(P/'water-r6-poster.jpg',quality=95)
(P/'index.html').write_text(page.replace('const revisions={water:5,earth:5,lightning:4}','const revisions={water:6,earth:5,lightning:4}'),encoding='utf-8')
assert before=={n:digest(P/n) for n in protected}
(O/'publication.json').write_text(json.dumps(dict(status='published-for-review',userAccepted=False,path=str(P/'water-02-r6.mp4'),sha256=a['sha256'],preserved=before),indent=2))
print('Published water r6. Previous water r5 and other elements preserved.')
