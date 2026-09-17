from pathlib import Path
import json,hashlib,shutil
import numpy as np
from PIL import Image
R=Path(__file__).resolve().parent;O=R/'sigil-02-v2';public=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02'
audit=json.loads((O/'audit.json').read_text());assert audit['decodedFrames']==294 and audit['visualStatus']=='reviewed'
public.mkdir(parents=True,exist_ok=True);shutil.copy2(O/'fire-02.mp4',public/'fire-02.mp4');shutil.copy2(O/'fire-frames/0180.jpg',public/'poster.jpg')
with np.load(O/'source.npz') as a:mask=a['support']
im=Image.fromarray(np.uint8(np.flipud(mask)*226)).convert('RGB');im.resize((1920,1080),Image.Resampling.LANCZOS).save(public/'artwork-02.png')
html='''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — 02 / Fire</title>
<style>:root{color-scheme:dark;font-family:Arial,Helvetica,sans-serif;background:#000;color:#d9d5cc}*{box-sizing:border-box}body{margin:0;background:#000}main{max-width:1440px;margin:auto;padding:24px}header{display:flex;align-items:center;justify-content:space-between;gap:24px;padding-bottom:16px;font-size:11px;letter-spacing:.15em}header a{color:#777;text-decoration:none;letter-spacing:0}.stage{aspect-ratio:16/9;background:#000}video{width:100%;height:100%;display:block;background:#000}nav{display:flex;gap:18px;align-items:center;justify-content:space-between;border-top:1px solid #242424;padding-top:18px;font-size:12px}nav a{color:inherit;text-decoration:none;padding:8px 12px;border:1px solid #393630}button{font:inherit;color:inherit;background:#000;border:1px solid #393630;padding:8px 12px;cursor:pointer}button:hover,nav a:hover{border-color:#a8a298}a:focus-visible,button:focus-visible{outline:2px solid #e4ad74;outline-offset:4px}.meta{color:#777;margin-left:auto}figure{margin:28px 0 0}figure[hidden]{display:none}figure img{display:block;width:100%;background:#000}figcaption{color:#888;font-size:12px;padding-bottom:4px}@media(max-width:600px){main{padding:16px 10px}nav{flex-wrap:wrap;gap:10px}.meta{width:100%;order:3;margin-left:0}}</style></head>
<body><main><header><span>CYBRDELIC / 02 / FIRE</span><a href="../../">All bending videos ↗</a></header>
<div class="stage"><video id="film" controls autoplay muted loop playsinline preload="metadata" poster="poster.jpg" src="fire-02.mp4" aria-label="Cybrdelic sigil 02 formed in fire"></video></div>
<nav><button id="reference" aria-expanded="false" aria-controls="artwork">Compare 02 artwork</button><span class="meta">1920 × 1080 · 30 fps · 9.8 seconds</span><a href="fire-02.mp4" download="cybrdelic-02-fire.mp4">Download video ↓</a></nav>
<figure id="artwork" hidden><figcaption>Approved 02 artwork, in the same framing.</figcaption><img src="artwork-02.png" alt="The original broad, pointed Cybrdelic 02 sigil with its cutouts"></figure>
</main><script>const button=document.getElementById('reference'),art=document.getElementById('artwork');button.addEventListener('click',()=>{art.hidden=!art.hidden;button.setAttribute('aria-expanded',String(!art.hidden));button.textContent=art.hidden?'Compare 02 artwork':'Hide artwork';if(!art.hidden){document.getElementById('film').pause();art.scrollIntoView({behavior:'smooth',block:'nearest'})}});</script></body></html>'''
(public/'index.html').write_text(html,encoding='utf-8')
baseline=json.loads((R/'sigil-v1/existing-video-hashes.json').read_text());assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in baseline.items())
page=public.parents[1]/'index.html';text=page.read_text(encoding='utf-8');backup=O/'bending-page-before-sigil02.html'
if not backup.exists():backup.write_text(text,encoding='utf-8')
if 'sigils/02/' not in text:text=text.replace('<a href="../materials.html">Earlier material studies ↗</a>','<span><a href="sigils/02/" style="margin-right:22px">02 fire sigil ↗</a><a href="../materials.html">Earlier material studies ↗</a></span>');page.write_text(text,encoding='utf-8')
print(json.dumps({'page':str(public/'index.html'),'video':str(public/'fire-02.mp4'),'originalVideosUnchanged':len(baseline),'sha256':hashlib.sha256((public/'fire-02.mp4').read_bytes()).hexdigest()}))
