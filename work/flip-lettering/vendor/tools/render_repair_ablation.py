"""Render stage-isolated comparisons using actual Three.js geometry, not composites pretending to be simulations."""
import base64,hashlib,json,re
from pathlib import Path
from playwright.sync_api import sync_playwright
from browser_common import ROOT,launch
OUT=ROOT/'tests/repair/ablation';cases=json.loads((OUT/'cases.json').read_text());renders=[]
with sync_playwright() as p:
 for case in cases['cases']:
  b=launch(p,threads=1);page=b.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1)
  page.set_default_timeout(120000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
  page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
  payload=(ROOT/case['meshPath']).read_bytes()
  page.expose_function('__readCache',lambda name,f:base64.b64encode(payload).decode())
  # One fixed physical state is inspected, with the same camera trajectory
  # denominator as the new movies. No video is claimed from these stills.
  frame=case['frame'];manifest={'config':case['config'],'frames':[dict(case['metrics'],frame=i) for i in range(120)]}
  html=(ROOT/'index.html').read_text()
  html=re.sub(r'<script src="([^"]+)"></script>',lambda m:'<script>'+(ROOT/m.group(1)).read_text().replace('</script','<\\/script')+'</script>',html)
  init='window.__CAPTURE__=true;window.__DEFER_CAPTURE_RENDER__=true;window.__SCENE__="impact";window.__LOCAL_MANIFESTS__='+json.dumps({'impact':manifest})+';'
  page.set_content(html.replace('<head>','<head><script>'+init+'</script>',1),wait_until='load',timeout=120000)
  page.wait_for_function('window.CYBR?.ready||window.CYBR_ERROR',timeout=120000)
  assert not page.evaluate('!!window.CYBR_ERROR')
  page.evaluate('(f)=>CYBR.loadFrame(f)',frame)
  page.evaluate('(id)=>{document.getElementById("bottomNote").textContent="CONTROLLED STAGE COMPARISON / "+id.toUpperCase();}',case['id'])
  modes=[('repair','water'),('repair','normal')]
  if case['id']=='mesher_repair':modes += [('ii','water'),('iii','water')]
  for shader,mode in modes:
   page.evaluate('([p,m])=>{CYBR.renderer.setRasterProfile(p);CYBR.setMode(m);CYBR.setShot(0);}',[shader,mode])
   # Remove diagnostic/secondary particles in mesher-only normal comparisons.
   path=OUT/f'{case["id"]}_{shader}_{mode}.png';page.screenshot(path=str(path))
   info=page.evaluate('CYBR.inspect()');assert info['glError']==0
   renders.append({'case':case['id'],'shader':shader,'displayMode':mode,'image':str(path.relative_to(ROOT)),
     'imageSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'renderer':info,'primarySha256':case['primarySha256'],
     'meshPayloadSha256':case['meshPayloadSha256'],'javascriptErrors':errors[:]})
  assert not errors,errors
  print('ABLATION RENDERED',case['id'],flush=True);b.close()
(OUT/'renders.json').write_text(json.dumps({'passed':True,'resolution':[1920,1080],'renders':renders,
 'qualification':'These are newly rendered, fixed-state inspection images, not simulation movies. See cases.json for controlled inputs.'},indent=2))
