from pathlib import Path
import numpy as np,json,hashlib,shutil
from PIL import Image
from scipy.ndimage import distance_transform_edt,label
R=Path(__file__).resolve().parent;R.mkdir(exist_ok=True)
S=Path('C:/Users/alexf/Documents/ChatGPT/cybrdelic-platform/flip-water-threejs')
O=R.parent.parent/'outputs/cybrdelic-type/elements/water';O.mkdir(exist_ok=True)
proof={}
for rel in ['src/renderer.js','vendor/three.global.js','LICENSE']:
 p=O/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(S/rel,p);proof[rel]=hashlib.sha256(p.read_bytes()).hexdigest()
art=np.array(Image.open(R.parent.parent/'outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png').convert('L'))
for variant,(top,bottom) in enumerate([(95,535),(585,1005)],1):
 mask=art[top:bottom,20:1005]<100;labs,n=label(mask)
 for j in range(1,n+1):
  ys,xs=np.where(labs==j)
  if len(xs)<35 or (xs.mean()<85 and ys.mean()<130):mask[labs==j]=False
 ys,xs=np.where(mask);mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
 # Full filled artwork, not a skeleton or substitute font.
 width=4.;scale=width/mask.shape[1];dist=distance_transform_edt(mask)*scale
 h=.025;s=h*.5;points=[]
 for x in np.arange(.8,4.8,s):
  for y in np.arange(1.35,1.35+mask.shape[0]*scale,s):
   ix=min(mask.shape[1]-1,int((x-.8)/scale));iy=mask.shape[0]-1-int((y-1.35)/scale)
   if iy<0 or not mask[iy,ix]:continue
   half=min(.040,dist[iy,ix]*.60)
   for z in np.arange(-half+s*.5,half,s):points.append([x,y,.86+z])
 data={'variant':f'{variant:02}','h':h,'points':points,'bounds':[.8,4.8,1.35,1.35+mask.shape[0]*scale],'artSha256':hashlib.sha256(mask.tobytes()).hexdigest(),'maskSize':list(mask.shape)}
 (R/f'source-{variant:02}.json').write_text(json.dumps(data,separators=(',',':')))
 Image.fromarray(np.uint8(~mask)*255).save(O/f'sigil-{variant:02}.png')
 print(variant,len(points),data['bounds'])
(O/'source-verification.json').write_text(json.dumps({'original':str(S),'unchangedRendererHashes':proof,'sigilSource':'../../exploration-v6/cybrdelic-brandmark-refined.png'},indent=2))
