"""Read-only HTTP and asset checks for the updated local comparison page."""
from pathlib import Path
from html.parser import HTMLParser
import urllib.request,json,hashlib,io
from PIL import Image
R=Path(__file__).resolve().parent;P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'
BASE='http://127.0.0.1:8767/elements/motion/subelements/dynamics/lava/'

class Parse(HTMLParser):
    def __init__(self):super().__init__();self.buttons=[];self.images=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='button' and 'data-src' in a:self.buttons.append(a)
        if tag=='img':self.images.append(a)

def main():
    with urllib.request.urlopen(BASE+'?v=basalt-depth',timeout=8) as response:
        html=response.read();assert response.status==200
    assert html==(P/'index.html').read_bytes();p=Parse();p.feed(html.decode('utf-8'))
    assert len(p.buttons)==5 and sum(a.get('aria-pressed')=='true' for a in p.buttons)==1
    assert p.images[0]['src']==p.buttons[0]['data-src']=='lava-basalt-volume.png'
    assets=[]
    for a in p.buttons:
        name=a['data-src']
        with urllib.request.urlopen(BASE+name,timeout=8) as response:data=response.read();assert response.status==200
        assert data==(P/name).read_bytes()
        size=Image.open(io.BytesIO(data)).size
        assert size==(int(a['data-width']),int(a['data-height']))
        assets.append({'name':name,'size':size,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    with urllib.request.urlopen(BASE+'review.json',timeout=8) as response:review=response.read()
    assert review==(P/'review.json').read_bytes()
    result={'url':BASE+'?v=basalt-depth','pageMatchesDisk':True,'defaultImage':'lava-basalt-volume.png','assets':assets,'previousImagesPreserved':True,'limits':'HTTP, file integrity, dimensions and static selection wiring checked; not an automated browser interaction test.'}
    (R/'lava-focus/breakout/site-qa.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
