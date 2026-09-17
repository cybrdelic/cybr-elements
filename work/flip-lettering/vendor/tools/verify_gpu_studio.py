"""Exercise sparse GPU primary physics through the actual offline studio and worker preview."""
from browser_common import *
from playwright.sync_api import sync_playwright
import hashlib,time
report={'sourceSha256':hashlib.sha256((ROOT/'standalone.html').read_bytes()).hexdigest(),'build':'CYBR FLIP II','backend':'Sparse WebGL2 GPU physics / CPU meshing and whitewater','scenes':[],'errors':[],'externalRequests':[]}
with sync_playwright() as p:
 b=launch(p,2);page=b.new_page(viewport={'width':640,'height':480},device_scale_factor=1);page.set_default_timeout(180000)
 page.on('pageerror',lambda e:report['errors'].append(str(e)))
 page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' else None)
 page.on('request',lambda r:report['externalRequests'].append(r.url) if not r.url.startswith(('blob:','data:')) else None)
 html=(ROOT/'standalone.html').read_text().replace('<head>','<head><script>window.__CAPTURE__=true;window.__CAPTURE_LIVE__=true;window.__CAPTURE_GPU__=true;</script>',1)
 page.set_content(html,wait_until='load');page.wait_for_function('CYBR?.ready||window.CYBR_ERROR');cdp=page.context.new_cdp_session(page)
 for scene in SCENES:
  started=time.time()
  if page.evaluate('CYBR.inspect().scene')!=scene:page.evaluate('(s)=>CYBR.selectGPU(s)',scene);page.wait_for_function('CYBR.ready||window.CYBR_ERROR')
  if page.evaluate('!!window.CYBR_ERROR'):raise RuntimeError(page.evaluate('window.CYBR_ERROR'))
  records=[];hashes=[]
  for f in range(5):
   if f:page.evaluate('CYBR.stepLive(1/48)')
   info=page.evaluate('CYBR.inspect()');m=info['metrics']
   assert info['execution']=='gpu' and info['glError']==0
   assert m['primaryCPUAdvectionSteps']==0 and m['finite'] and m['solidViolations']==0
   assert m['pressure']['converged'],m['pressure']
   assert m['particles']==m['initialParticles']+m['spawned']-m['deleted']
   records.append(m);hashes.append(hashlib.sha256(page.screenshot(type='jpeg')).hexdigest())
  assert len(set(hashes))==len(hashes)
  for mode in ['water','particles','whitewater','normal','thickness','wire']:
   page.evaluate('(mode)=>CYBR.setMode(mode)',mode);assert page.evaluate('CYBR.inspect().glError')==0
  page.evaluate("CYBR.setMode('water')");page.screenshot(path=str(ROOT/'media'/f'gpu_live_{scene}.png'))
  report['scenes'].append({'name':scene,'records':records,'hashes':hashes,'uniqueFrames':len(set(hashes)),'wallSeconds':time.time()-started})
  (ROOT/'tests'/'gpu-studio.json').write_text(json.dumps(report,indent=2));print('GPU STUDIO PASS',scene,records[-1]['particles'],records[-1]['pressure'],flush=True);cdp.send('HeapProfiler.collectGarbage')
 # Backend is retained by saved settings and an actual reset.
 settings=page.evaluate('CYBR.settings()');assert settings['backend']=='gpu'
 page.evaluate('(s)=>CYBR.restoreSettings(s)',settings);page.wait_for_function('CYBR.ready||window.CYBR_ERROR');assert page.evaluate('CYBR.inspect().execution')=='gpu'
 # Switching GPU -> CPU -> GPU must restore GL state without losing the renderer.
 page.evaluate("CYBR.selectLive('capillary')");page.wait_for_function('CYBR.ready||window.CYBR_ERROR');assert page.evaluate('CYBR.inspect().execution')=='live'
 page.evaluate("CYBR.selectGPU('capillary')");page.wait_for_function('CYBR.ready||window.CYBR_ERROR');assert page.evaluate('CYBR.inspect().execution')=='gpu'
 report['settingsRoundTrip']=True;report['backendSwitching']=True;report['renderer']=page.evaluate('CYBR.inspect()');b.close()
assert not report['errors'],report['errors'];assert not report['externalRequests']
report['passed']=True;(ROOT/'tests'/'gpu-studio.json').write_text(json.dumps(report,indent=2));print('GPU STUDIO ALL VERIFIED',flush=True)
