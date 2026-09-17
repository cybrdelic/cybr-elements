"""Retarded spherical pressure pulses, integrated through a black optical stage.
An authored slow-motion acoustic visualization, not calibrated real-time sound.
"""
from pathlib import Path
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent));from shared_motion import pose
kind=sys.argv[sys.argv.index('--kind')+1];selected=list(range(120)) if '--full' in sys.argv else list(map(int,sys.argv[sys.argv.index('--frames')+1].split(',')))
X,Z=480,256;x=np.linspace(-5.25,5.25,X,dtype='f4')[None,:];z=np.linspace(0,4.2,Z,dtype='f4')[:,None]
yy=np.linspace(-3.0,3.0,96,dtype='f4');out=R/'frames'/kind;out.mkdir(exist_ok=True)
events=np.arange(.1,1.69,.16 if kind=='sound' else .48);centers=[pose(float(t))[0] for t in events]
for f in selected:
    t=(f+1)/30;path=np.zeros((Z,X),dtype='f4')
    for at,p in zip(events,centers):
        age=t-at
        if age<=0 or age>1.65:continue
        c=3.5 if kind=='sound' else 2.7;radius=c*age;width=.050 if kind=='sound' else .10
        radial=(x-p[0])**2+(z-p[1])**2;amplitude=np.exp(-age*(3.1 if kind=='sound' else 2.0))/(radius+.25)
        # Bipolar compression/rarefaction waves with geometric spreading.
        for y in yy:
            r=np.sqrt(radial+y*y);u=(r-radius)/width;pulse=u*np.exp(-.5*u*u)
            if kind=='pressure':pulse=-pulse+.38*((r-radius*.65)/width)*np.exp(-.5*((r-radius*.65)/width)**2)
            path+=pulse*(amplitude*.00008*(6/len(yy)))
    path=gaussian_filter(path,.8);gz,gx=np.gradient(path,4.2/(Z-1),10.5/(X-1));angle=np.sqrt(gx*gx+gz*gz)
    signal=(1-np.exp(-np.maximum(0,angle-.000002)*3600))**1.25
    rgb=(np.clip(signal[...,None]*np.array([.80,.87,.94])[None,None],0,1)*255).astype('u1')[::-1]
    im=Image.fromarray(rgb).resize((1920,768),Image.Resampling.LANCZOS);canvas=Image.new('RGB',(1920,1080));canvas.paste(im,(0,120));canvas.save(out/f'{f:04}.jpg',quality=97)
    if f%20==0:print(kind,f,flush=True)
(R/f'{kind}-mechanism.json').write_text(json.dumps({'method':'retarded radial pressure pulses with 1/r spreading and exponential attenuation; depth-integrated index gradients','depthQuadrature':96,'outputFrames':selected,'limits':'Slow-motion wave speed and amplified optical sensitivity are authored; no claim of calibrated acoustics or naked-eye visibility'},indent=2),encoding='utf-8')
