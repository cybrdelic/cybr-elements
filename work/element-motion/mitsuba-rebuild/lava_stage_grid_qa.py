"""Cheap CPU timestep convergence and height-field stability checks."""
import os,json,time
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
import numpy as np
from PIL import Image,ImageDraw
from lava_stage_flow import Flow,O
start=time.time();results=[]
for dt in [.01,.005]:
    f=Flow()
    for i in range(round(3/dt)):f.step(dt,i*dt)
    results.append(f.h)
relative=float(np.linalg.norm(results[0]-results[1])/np.linalg.norm(results[1]));assert relative<.03,relative
last=np.load(O/'field-031.npz');h=last['height'];lap=h[2:,1:-1]+h[:-2,1:-1]+h[1:-1,2:]+h[1:-1,:-2]-4*h[1:-1,1:-1];interior=h[1:-1,1:-1]>.08
curvature=float(np.sqrt(np.mean(lap[interior]**2))/h.max());assert curvature<.06,curvature
sheet=Image.new('RGB',(1152,408),'black');draw=ImageDraw.Draw(sheet)
for i,(name,field) in enumerate([('Initial height',Flow().h0),('12 seconds / implicit flow',h),('Temperature',last['temperature'])]):
    scaled=np.clip(field/(.5 if i<2 else 1500),0,1);rgb=np.stack([scaled,scaled**1.4,scaled**2.2],-1)*255;image=Image.fromarray(rgb.astype('u1')).transpose(Image.Transpose.FLIP_TOP_BOTTOM);image=image.resize((384,384),Image.Resampling.NEAREST);sheet.paste(image,(i*384,0));draw.text((i*384+8,389),name,fill='white')
sheet.save(O/'grid-qa.png');report={'device':'CPU','timestepComparisonSeconds':3,'dtSeconds':[.01,.005],'relativeHeightL2Difference':relative,'normalizedInteriorLaplacianRMS':curvature,'seconds':round(time.time()-start,2),'limits':'Numerical stability and timestep sensitivity checks, not material realism or validation against measured lava'};(O/'grid-qa.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
