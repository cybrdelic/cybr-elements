from browser_common import *
from playwright.sync_api import sync_playwright
import time,subprocess,hashlib
out={'sourceSha256':hashlib.sha256((ROOT/'standalone.html').read_bytes()).hexdigest(),'build':'CYBR FLIP II','errors':[],'warnings':[],'scenes':[],'exports':{}}
with sync_playwright() as p:
 b=launch(p,1);page=b.new_page(viewport={'width':640,'height':480},device_scale_factor=1,accept_downloads=True);page.set_default_timeout(120000)
 page.on('pageerror',lambda e:out['errors'].append(str(e)));page.on('console',lambda m:out['errors'].append(m.text) if m.type=='error' else out['warnings'].append(m.text) if m.type=='warning' else None)
 html=(ROOT/'standalone.html').read_text().replace('<head>','<head><script>window.__CAPTURE__=true;window.__CAPTURE_LIVE__=true;</script>',1)
 requests=[];page.on('request',lambda r:requests.append(r.url));page.set_content(html,wait_until='load');page.wait_for_function('CYBR?.ready||window.CYBR_ERROR')
 cdp=page.context.new_cdp_session(page)
 for name in SCENES:
  page.evaluate('(name)=>CYBR.selectLive(name)',name);page.wait_for_function('CYBR.ready||window.CYBR_ERROR')
  if page.evaluate('!!window.CYBR_ERROR'):raise RuntimeError(page.evaluate('window.CYBR_ERROR'))
  a=page.evaluate('CYBR.inspect()');page.evaluate('CYBR.stepLive(1/48)');c=page.evaluate('CYBR.inspect()')
  assert c['metrics']['time']>a['metrics']['time'] and c['metrics']['finite'] and c['glError']==0
  assert c['metrics']['solidViolations']==0
  out['scenes'].append({'name':name,'time':c['metrics']['time'],'particles':c['metrics']['particles'],'surface':c['metrics']['surface'],'pressure':c['metrics']['pressure'],'glError':c['glError']});print('LIVE',name,c['metrics']['particles'],flush=True);cdp.send('HeapProfiler.collectGarbage')
 # Explicit physical controls apply in the actual worker, not just labels.
 page.evaluate("CYBR.restoreSettings({schema:'cybr-flip-settings/2',scene:'capillary',quality:'live',flip:.6,parameters:{surfaceTension:0,kinematicViscosity:0,pressureTolerance:.00001,affine:false}})")
 page.wait_for_function('CYBR.ready');c=page.evaluate('CYBR.inspect()');config=page.evaluate('CYBR.config');assert config['surfaceTension']==0 and not config['affine'];out['parameterRoundTrip']={'config':config,'metrics':c['metrics']}
 for mode in ['normal','wire','whitewater','thickness','particles','water']:
  page.evaluate('(m)=>CYBR.setMode(m)',mode);assert page.evaluate('CYBR.inspect().glError')==0
 page.evaluate('CYBR.setShot(1)');page.screenshot(path=str(ROOT/'media'/'live_capillary.png'))
 for method,filename in [('exportOBJ','browser-test.obj'),('exportPLY','browser-test.ply')]:
  with page.expect_download() as d:stats=page.evaluate(f'CYBR.{method}()')
  target=ROOT/'tests'/filename;d.value.save_as(target);out['exports'][method]={'bytes':target.stat().st_size,**stats};assert target.stat().st_size>100
 with page.expect_download() as d:page.evaluate("document.querySelector('#saveProject').click()")
 dest=ROOT/'tests'/'browser-settings.json';d.value.save_as(dest);assert json.loads(dest.read_text())['schema']=='cybr-flip-settings/2';out['exports']['settings']=True
 with page.expect_download() as d:page.evaluate("document.querySelector('#savePng').click()")
 d.value.save_as(ROOT/'tests'/'browser-frame.png');out['exports']['png']=True
 # Exercise start/stop of native MediaRecorder, then decode the returned WebM.
 page.evaluate("document.querySelector('#record').click()");page.wait_for_timeout(1100);page.evaluate('CYBR.stepLive(1/48)');page.screenshot();page.wait_for_timeout(1100)
 with page.expect_download() as d:page.evaluate("document.querySelector('#record').click()")
 dest=ROOT/'tests'/'browser-recording.webm';d.value.save_as(dest);subprocess.run(['ffmpeg','-v','error','-i',str(dest),'-vsync','0','-f','framemd5','-'],stdout=subprocess.DEVNULL,check=True);out['exports']['webmBytes']=dest.stat().st_size
 # Small reference integrator test on actual moving liquid; source supports full resolution.
 page.evaluate('CYBR.resize(320,240)');page.evaluate('window.PT=new ReferencePathTracer(CYBR.renderer);PT.build()');r=page.evaluate('PT.sample(4)');assert r['glError']==0 and r['samples']==4;out['pathTracer']=r
 page.screenshot(path=str(ROOT/'media'/'live_reference_test.png'));out['networkRequests']=requests;out['externalNetworkRequests']=[u for u in requests if not u.startswith(('blob:','data:'))];print('REQUESTS',requests,flush=True);assert not out['externalNetworkRequests']
 b.close()
assert not out['errors'],out['errors']
(ROOT/'tests'/'browser-ii.json').write_text(json.dumps(out,indent=2));print('BROWSER VERIFIED',len(out['scenes']),flush=True)
