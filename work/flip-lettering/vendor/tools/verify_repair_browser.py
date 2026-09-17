"""Exercise the shipped standalone HTML, repaired CPU profile and browser replay."""
from pathlib import Path
import hashlib,json,time
from playwright.sync_api import sync_playwright
from browser_common import ROOT,launch
OUT=ROOT/'tests/repair';OUT.mkdir(exist_ok=True,parents=True)
with sync_playwright() as p:
 b=launch(p,threads=1);page=b.new_page(viewport={'width':1280,'height':720},device_scale_factor=1)
 page.set_default_timeout(120000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
 html=(ROOT/'standalone.html').read_text()
 html=html.replace('<head>','<head><script>window.__CAPTURE__=true;window.__CAPTURE_LIVE__=true;window.__SCENE__="impact";</script>',1)
 page.set_content(html,wait_until='load',timeout=120000)
 page.wait_for_function('window.CYBR?.ready||window.CYBR_ERROR',timeout=120000)
 assert not page.evaluate('!!window.CYBR_ERROR'),page.evaluate('window.CYBR_ERROR')
 config=page.evaluate('CYBR.config');assert config['flip']==.93 and config['separation'] is True
 assert config['surfaceOptions']['temporalBlend']==0
 initial=page.evaluate('CYBR.inspect()');assert initial['execution']=='live' and initial['rasterProfile']=='repair' and initial['glError']==0
 frames=[]
 for i in range(4):
  m=page.evaluate('CYBR.stepLive(1/48)');assert m['finite'] and m['pressure']['converged'] and m['solidViolations']==0;frames.append(m)
 count=page.evaluate('async()=>{window.savedCP=await CYBR.saveCheckpoint();return savedCP.byteLength}')
 page.evaluate('async()=>{for(let i=0;i<3;i++)await CYBR.stepLive(1/48);window.afterA=CYBR.renderer.geometry.attributes.position.array.slice();window.afterTime=CYBR.inspect().metrics.time;}')
 replay=page.evaluate('''async()=>{
 await CYBR.loadCheckpoint(savedCP.slice(0));for(let i=0;i<3;i++)await CYBR.stepLive(1/48);
 const q=CYBR.renderer.geometry.attributes.position.array;return {sameLength:q.length===afterA.length,
 everyPositionEqual:q.length===afterA.length&&q.every((x,i)=>x===afterA[i]),sameTime:CYBR.inspect().metrics.time===afterTime,
 continuedFrames:3,vertices:q.length/3};}''')
 assert replay['sameLength'] and replay['everyPositionEqual'] and replay['sameTime'],replay
 profiles=[]
 for profile in ['ii','iii','repair']:
  page.evaluate('(p)=>{CYBR.renderer.setRasterProfile(p);CYBR.setMode("water");CYBR.setShot(0);}',profile)
  info=page.evaluate('CYBR.inspect()');assert info['glError']==0 and info['rasterProfile']==profile;profiles.append(info)
 page.screenshot(path=str(OUT/'live-browser.png'))
 result={'passed':not errors,'standaloneSha256':hashlib.sha256((ROOT/'standalone.html').read_bytes()).hexdigest(),
  'config':config,'initial':initial,'liveFrames':frames,'checkpointBytes':count,'checkpointReplay':replay,'shaderProfiles':profiles,
  'javascriptErrors':errors,'qualification':'Live CPU preview is exercised here. High-resolution films use the offline PCA mesher; no new GPU performance or numerical-parity claim.'}
 assert not errors,errors
 (OUT/'browser.json').write_text(json.dumps(result,indent=2));print('REPAIR STANDALONE BROWSER PASS',replay,flush=True);b.close()
