"""Check that the existing local gallery serves the exact inspected assets."""
from pathlib import Path
import urllib.request,hashlib,json,re
R=Path(__file__).resolve().parent;P=R.parents[2]/'outputs/cybrdelic-type/elements/motion/subelements/dynamics/lava'
base='http://127.0.0.1:8767/elements/motion/subelements/dynamics/lava/'
results=[]
for name in ['index.html','lava-folded.png','lava-folded-detail.png','lava-refined.png','lava-restored-first.png','review.json']:
    with urllib.request.urlopen(base+name,timeout=10) as response:
        body=response.read();status=response.status
    local=(P/name).read_bytes();assert status==200 and hashlib.sha256(body).digest()==hashlib.sha256(local).digest()
    results.append({'file':name,'status':status,'bytes':len(body),'matchesDisk':True})
html=(P/'index.html').read_text(encoding='utf-8')
buttons=re.findall(r'data-src="([^"]+)"',html);assert len(buttons)==4 and all((P/src).is_file() for src in buttons)
assert 'id="lava" src="lava-folded.png"' in html and 'background:#000' in html
out={'url':base+'?v=folded-lava','assets':results,'views':buttons,'default':'lava-folded.png'}
(R/'lava-focus/lobes/site-qa.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
