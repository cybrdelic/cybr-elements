"""Read-only checks of the served stage gallery and exact media bytes."""
from pathlib import Path
from html.parser import HTMLParser
import urllib.request,json,hashlib,io
from PIL import Image
R=Path(__file__).resolve().parent;P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'
B='http://127.0.0.1:8767/elements/motion/subelements/dynamics/lava/'
class Parser(HTMLParser):
    def __init__(self):super().__init__();self.buttons=[];self.images=[];self.videos=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='button' and 'data-key' in a:self.buttons.append(a)
        if tag=='img':self.images.append(a)
        if tag=='video':self.videos.append(a)
def get(name):
    with urllib.request.urlopen(B+name,timeout=10) as r:data=r.read();assert r.status==200
    assert data==(P/(name.split('?')[0] or 'index.html')).read_bytes();return data
p=Parser();p.feed(get('?v=stages').decode());assert len(p.buttons)==5 and sum(b['aria-pressed']=='true' for b in p.buttons)==1
assert p.images[0]['src']=='stage-cooling.png';assert len(p.videos)==1 and 'controls' in p.videos[0] and 'autoplay' not in p.videos[0]
rows=[]
for b in p.buttons:
    name='stage-'+b['data-key']+'.png';data=get(name);size=Image.open(io.BytesIO(data)).size;assert size==(960,540);rows.append({'image':name,'size':size,'sha256':hashlib.sha256(data).hexdigest()})
for name in ['lava-flow-plume.mp4','motion-poster.png','stage-contact.png','lava-stage-images.zip','stages-review.json','basalt-depth.html']:get(name)
result={'url':B+'?v=stages','assets':rows,'pageMatchesDisk':True,'nativeVideoControls':True,'autoplay':False,'allStageControlsWired':True,'limits':'HTTP, exact bytes, media dimensions and static control wiring; browser interactions are reviewed separately.'}
(R/'lava-focus/stages/site-qa.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
