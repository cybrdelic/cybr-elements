"""Build a separate gallery; publish only after all ten clips validate."""
from pathlib import Path
import json,subprocess,shutil,hashlib
from PIL import Image
R=Path(__file__).resolve().parent;B=R/'sigil-v1';P=R.parents[1]/'outputs/cybrdelic-type/elements/motion/bending';O=P/'sigils'
elements=['earth','fire','water','air','lightning']
O.mkdir(exist_ok=True)
def main():
 rows=[]
 for variant in ['01','02']:
  for element in elements:
   stem=f'{element}-{variant}';src=B/f'{stem}.mp4';assert src.exists(),src
   q=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,r_frame_rate:format=duration','-of','json',str(src)]))
   v=q['streams'][0];assert (v['width'],v['height'],int(v['nb_read_frames']),v['r_frame_rate'])==(1920,1080,300,'30/1'),q
   assert abs(float(q['format']['duration'])-10)<.04
   subprocess.run(['ffmpeg','-v','error','-i',str(src),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
   shutil.copy2(src,O/src.name)
   poster=B/stem/'0120.jpg'
   if not poster.exists():poster=B/stem/'frames/0120.jpg'
   im=Image.open(poster).convert('RGB');im.thumbnail((1440,810));im.save(O/f'{stem}.jpg',quality=94)
   rows.append(dict(element=element,variant=variant,**v,bytes=src.stat().st_size,sha256=hashlib.sha256(src.read_bytes()).hexdigest()))
 (O/'validation.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
 original=(P/'index.html').read_text(encoding='utf-8')
 css=original[original.index('<style>'):original.index('</head>')]
 html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cybrdelic — Elemental Sigils</title>'''+css+'''<style>.styles{display:flex;gap:0;margin-top:24px}.styles button[aria-pressed="true"]{background:#e9e7e3;color:#000}.edition a{color:#aaa}details{font-size:12px;color:#777;margin-top:30px;line-height:1.7}summary{cursor:pointer}.error{color:#ef806b}</style></head><body><main>
 <header><div><div class="brand">CYBRDELIC</div><h1>Elemental sigils.</h1><p>Five elements. Two signatures.</p><div class="styles" role="group" aria-label="Sigil style"><button data-style="01" aria-pressed="true">Sigil 01</button><button data-style="02" aria-pressed="false">Sigil 02</button></div></div><div class="edition">10 SECONDS / BLACK<br><a href="../">Bending studies ↗</a></div></header>
 <div class="controls"><button id="playAll">Play together</button><button id="pauseAll">Pause</button><button id="restartAll">Restart</button><button id="hold">Show full sigil</button><input id="scrub" type="range" min="0" max="10" step="0.01" value="0" aria-label="Shared playback position"><output id="clock">0.00 / 10.00</output></div><section class="grid" id="grid" aria-label="Elemental sigil videos"></section>
 <details><summary>About the motion</summary>The original Cybrdelic marks guide each element as it forms. The complete sigil holds for three seconds before release. Fire and air use transported gas fields; water uses FLIP/APIC with an authored letter-shaped guide; earth assembles closed fragments before a rigid-body release. Lightning uses guided electrical channels and a corona model. These are art-directed effects, not unconstrained physical experiments.</details>
 <footer><span>1920 × 1080 · 30 fps · Original sigils 01 / 02</span><a href="validation.json">Video details ↗</a></footer></main><script>
 const elements=[['earth','Earth','#ac8b60'],['fire','Fire','#fa874a'],['water','Water','#8faebf'],['air','Air','#d0dbe1'],['lightning','Lightning','#97adff']];
 let style=new URLSearchParams(location.search).get('style')==='02'?'02':'01',together=false,seeking=false;
 const grid=document.querySelector('#grid'),scrub=document.querySelector('#scrub'),clock=document.querySelector('#clock');
 grid.innerHTML=elements.map(([id,name,color],i)=>`<article class="card" id="${id}" style="--accent:${color}"><div class="heading"><h2><span class="number">0${i+1}</span><span class="dot"></span>${name}</h2><span class="state">Ready</span></div><div class="stage"><video controls playsinline preload="metadata" aria-label="${name} sigil"></video></div><div class="actions"><button class="solo">Play solo</button><button class="replay">Replay</button><a class="download" download>Download ↓</a></div></article>`).join('');
 const videos=[...document.querySelectorAll('video')];let selected=videos[0];
 function pause(){together=false;videos.forEach(v=>v.pause())}
 function seek(t){pause();videos.forEach(v=>{if(v.readyState>=1)v.currentTime=Math.min(t,v.duration)});scrub.value=t;clock.value=`${t.toFixed(2)} / 10.00`}
 async function solo(v,restart=false){pause();selected=v;if(restart||v.ended)v.currentTime=0;await v.play().catch(()=>{})}
 async function all(restart=false){const t=restart||Number(scrub.value)>=9.99?0:Number(scrub.value);seek(t);together=true;selected=videos[0];await Promise.allSettled(videos.map(v=>v.play()))}
 function setStyle(next){pause();style=next;document.querySelectorAll('[data-style]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.style===style)));videos.forEach(v=>{const c=v.closest('.card'),stem=`${c.id}-${style}`;v.poster=stem+'.jpg';v.src=stem+'.mp4';v.load();const a=c.querySelector('.download');a.href=stem+'.mp4';a.download=`cybrdelic-${stem}-sigil.mp4`;c.querySelector('.state').textContent='Ready'});scrub.value=0;history.replaceState(null,'','?style='+style)}
 videos.forEach(v=>{const c=v.closest('.card'),state=c.querySelector('.state');c.querySelector('.solo').onclick=()=>solo(v);c.querySelector('.replay').onclick=()=>solo(v,true);v.onplay=()=>{if(!together){videos.filter(x=>x!==v).forEach(x=>x.pause());selected=v}c.classList.add('active');state.textContent='Playing'};v.onpause=()=>{c.classList.remove('active');state.textContent=v.ended?'Finished':'Paused'};v.onended=()=>{state.textContent='Finished';c.classList.remove('active')};v.onerror=()=>{state.textContent='Video unavailable';state.classList.add('error')}});
 document.querySelectorAll('[data-style]').forEach(b=>b.onclick=()=>setStyle(b.dataset.style));document.querySelector('#playAll').onclick=()=>all();document.querySelector('#restartAll').onclick=()=>all(true);document.querySelector('#pauseAll').onclick=pause;document.querySelector('#hold').onclick=()=>seek(4);scrub.oninput=()=>seek(Number(scrub.value));
 function tick(){if(selected&&!seeking){const t=selected.currentTime;scrub.value=t;clock.value=`${t.toFixed(2)} / 10.00`;if(together&&!selected.paused)videos.filter(v=>v!==selected).forEach(v=>{if(v.readyState>=2&&Math.abs(v.currentTime-t)>.10)v.currentTime=t})}requestAnimationFrame(tick)}setStyle(style);tick();window.SIGILS={videos,seek,all,solo,pause,setStyle};
 </script></body></html>'''
 (O/'index.html').write_text(html,encoding='utf-8')
 if 'sigils/' not in original:
  original=original.replace('<p>Five elements. One movement.</p>','<p>Five elements. One movement.</p><p style="margin-top:14px"><a href="sigils/" style="color:#ddd">Elemental sigil videos ↗</a></p>');(P/'index.html').write_text(original,encoding='utf-8')
 print(json.dumps(dict(published=str(O),videos=len(rows),totalBytes=sum(r['bytes'] for r in rows))))
if __name__=='__main__':main()
