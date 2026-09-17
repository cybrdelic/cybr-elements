"""Render one actual triangle-BVH reference still; no denoising or raster substitution."""
from browser_common import *
from playwright.sync_api import sync_playwright
import argparse,time,hashlib
parser=argparse.ArgumentParser();parser.add_argument('--scene',default='impact',choices=SCENES);parser.add_argument('--frame',type=int,default=36);parser.add_argument('--samples',type=int,default=256);args=parser.parse_args()
report={'scene':args.scene,'frame':args.frame,'resolution':[1920,1080],'requestedSamples':args.samples,'errors':[],'checkpoints':[],'rawMonteCarlo':True,'fullyConvergedClaim':False}
with sync_playwright() as p:
 b=launch(p,2);page=b.new_page(viewport={'width':1920,'height':1080},device_scale_factor=1);page.set_default_timeout(300000)
 page.on('pageerror',lambda e:report['errors'].append(str(e)));page.on('console',lambda m:report['errors'].append(m.text) if m.type=='error' else None)
 load(page,args.scene);page.evaluate('(f)=>CYBR.loadFrame(f)',args.frame);page.evaluate('CYBR.setShot(0)')
 report['simulation']=page.evaluate('CYBR.inspect()');report['bvh']=page.evaluate('window.PT=new ReferencePathTracer(CYBR.renderer);PT.build()')
 print('BVH',report['bvh'],flush=True);start=time.time()
 for i in range(args.samples):
  stat=page.evaluate('(()=>{const x=PT.sample();CYBR.renderer.renderer.getContext().finish();return x})()');assert stat['glError']==0
  if (i+1)%8==0 or i==args.samples-1:
   page.evaluate('(n)=>{document.querySelector("#playbackLabel").textContent="REFERENCE PATH TRACE / "+n+" SPP";document.querySelector("#bottomNote").textContent="ACTUAL TRIANGLE BVH / 10 BOUNCES / RAW MONTE CARLO";}',i+1)
   report['checkpoints'].append({'samples':i+1,'wallSeconds':time.time()-start});print('REFERENCE',i+1,'spp',round(time.time()-start,1),'s',flush=True)
   (ROOT/'tests'/'reference-still.json').write_text(json.dumps(report,indent=2))
  if i+1 in [16,64,args.samples]:page.screenshot(path=str(ROOT/'media'/f'reference_{args.scene}_{i+1:04d}spp.png'))
 dest=ROOT.parent/'CYBR_FLIP_II_Reference_1080p.png';page.screenshot(path=str(dest));report['file']=dest.name;report['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest();report['samplesPerPixel']=args.samples;report['wallSeconds']=time.time()-start
 b.close()
assert not report['errors'],report['errors'];report['passed']=True;(ROOT/'tests'/'reference-still.json').write_text(json.dumps(report,indent=2));print('REFERENCE COMPLETE',flush=True)
