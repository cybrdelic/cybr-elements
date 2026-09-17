from pathlib import Path
from PIL import Image
import numpy as np,json
r=Path('outputs/cybrdelic-type')
a=np.array(Image.open(r/'exploration-v2/cybrdelic-brandmark-studies.png').convert('L'))<100
b=np.array(Image.open(r/'exploration-v3/cybrdelic-brandmark-refined.png').convert('L'))<100
assert a.shape==b.shape
rows=[]
for top,bottom in [(90,540),(560,1040),(1080,1460)]:
    aa=a[top:bottom,30:1000];bb=b[top:bottom,30:1000]
    rows.append({'inkOverlapIoU':round(float((aa&bb).sum()/max(1,(aa|bb).sum())),4),'inkAreaChange':round(float(bb.sum()/aa.sum()-1),4)})
(r/'exploration-v3/comparison-check.json').write_text(json.dumps(rows,indent=2))
p=r/'index.html';s=p.read_text(encoding='utf-8')
(r/'exploration-v2/index-previous.html').write_text(s,encoding='utf-8')
s=s.replace('STUDY 02','SUBTLE REFINEMENT · STUDY 03')
s=s.replace('Readability is secondary.','A light refinement opens a few interior cuts and clarifies letter cues while keeping the silhouettes.')
s=s.replace('<img class="board"','<div class="compare"><button type="button" id="refined" aria-pressed="true">Refined</button><button type="button" id="previous" aria-pressed="false">Previous</button><span>Compare the small changes.</span></div><img id="board" class="board"',1)
s=s.replace('src="exploration-v2/cybrdelic-brandmark-studies.png"','src="exploration-v3/cybrdelic-brandmark-refined.png"')
s=s.replace('href="exploration-v2/cybrdelic-brandmark-studies.png"','href="exploration-v3/cybrdelic-brandmark-refined.png"')
s=s.replace('</style>', '.compare{display:flex;align-items:center;gap:10px;margin:0 0 24px}.compare button{font:inherit;font-size:12px;background:#fff;border:1px solid #111;padding:10px 16px;cursor:pointer}.compare button[aria-pressed="true"]{background:#111;color:#fff}.compare span{font-size:12px;color:#777;margin-left:10px}@media(max-width:650px){.compare{flex-wrap:wrap}.compare span{margin-left:0}}</style>')
s=s.replace('</body>', '''<script>const img=document.getElementById('board'),refined=document.getElementById('refined'),previous=document.getElementById('previous');function choose(isRefined){img.src=isRefined?'exploration-v3/cybrdelic-brandmark-refined.png':'exploration-v2/cybrdelic-brandmark-studies.png';refined.setAttribute('aria-pressed',String(isRefined));previous.setAttribute('aria-pressed',String(!isRefined))}refined.onclick=()=>choose(true);previous.onclick=()=>choose(false);</script></body>''')
p.write_text(s,encoding='utf-8')
print(json.dumps({'comparison':rows,'image':str(r/'exploration-v3/cybrdelic-brandmark-refined.png')}))
