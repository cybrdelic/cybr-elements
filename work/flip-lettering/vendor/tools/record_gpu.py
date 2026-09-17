"""Record genuine sparse GPU primary evolution through the delivered offline studio."""
from browser_common import *
from record import Encoder,W,H
from playwright.sync_api import sync_playwright
import time,json,hashlib
report={'sourceSha256':hashlib.sha256((ROOT/'standalone.html').read_bytes()).hexdigest(),'kind':'live sparse GPU primary simulation with CPU preview meshing and one-way whitewater','sourceResolution':[W,H],'videoFPS':24,'physicalPlaybackSpeed':.5,'frames':[],'clips':[],'javascriptErrors':[]}
with sync_playwright() as p:
 b=launch(p,2);page=b.new_page(viewport={'width':W,'height':H},device_scale_factor=1);page.set_default_timeout(180000)
 page.on('pageerror',lambda e:report['javascriptErrors'].append(str(e)));page.on('console',lambda m:report['javascriptErrors'].append(m.text) if m.type=='error' else None)
 html=(ROOT/'standalone.html').read_text().replace('<head>','<head><script>window.__CAPTURE__=true;window.__CAPTURE_LIVE__=true;window.__CAPTURE_GPU__=true;</script>',1)
 page.set_content(html,wait_until='load');page.wait_for_function('CYBR?.ready||window.CYBR_ERROR');cdp=page.context.new_cdp_session(page)
 for scene in ['breach','paddle']:
  if page.evaluate('CYBR.inspect().scene')!=scene:page.evaluate('(s)=>CYBR.selectGPU(s)',scene);page.wait_for_function('CYBR.ready||window.CYBR_ERROR')
  if page.evaluate('!!window.CYBR_ERROR'):raise RuntimeError(page.evaluate('window.CYBR_ERROR'))
  page.evaluate("CYBR.setMode('water');CYBR.setShot(0)");encoder=Encoder('live_sparse_gpu_'+scene);start=time.time()
  for f in range(96):
   if f:page.evaluate('CYBR.stepLive(1/48)')
   if f==48:page.evaluate("CYBR.setMode('particles')")
   info=page.evaluate('CYBR.inspect()');m=info['metrics'];assert info['execution']=='gpu' and info['glError']==0
   assert m['finite'] and m['solidViolations']==0 and m['primaryCPUAdvectionSteps']==0 and m['pressure']['converged'],m
   page.evaluate('''(m)=>{document.querySelector('#playbackLabel').textContent='LIVE / SPARSE GPU PHYSICS';document.querySelector('#bottomNote').textContent='GPU TRANSFER / PRESSURE / ADVECTION · CPU PREVIEW MESH';document.querySelector('#tag').textContent=m.activeBricks+' ACTIVE BRICKS / '+m.particles.toLocaleString()+' GPU PARTICLES';}''',m)
   image=page.screenshot(type='jpeg',quality=95,animations='disabled');encoder.add(image);report['frames'].append(info)
   if f in [24,66]:(ROOT/'media'/f'gpu_{scene}_frame{f:03d}.jpg').write_bytes(image)
   if f%12==0:cdp.send('HeapProfiler.collectGarbage');print('GPU RECORD',scene,f,'time',m['time'],'wall',round(time.time()-start,1),'pressure',m['pressure']['relativeResidual'],flush=True)
  report['clips'].append(encoder.close());(ROOT/'tests'/'captures'/'gpu.json').write_text(json.dumps(report,indent=2))
 b.close()
assert not report['javascriptErrors'],report['javascriptErrors'];report['passed']=True;(ROOT/'tests'/'captures'/'gpu.json').write_text(json.dumps(report,indent=2));print('GPU RECORDING COMPLETE',flush=True)
