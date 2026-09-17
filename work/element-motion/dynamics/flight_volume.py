"""Rasterize the solved wake into a volume and use the accepted air light model."""
from pathlib import Path
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
from PIL import Image
R=Path(__file__).resolve().parent;a=np.load(R/'cache/flight/tracers.npz');P=a['p'];E=a['energy']
selected=list(range(120)) if '--full' in sys.argv else list(map(int,sys.argv[sys.argv.index('--frames')+1].split(',')))
name=sys.argv[sys.argv.index('--output')+1] if '--output' in sys.argv else 'flight-volume'
out=R/'frames'/name;out.mkdir(exist_ok=True);X,Y,Z=480,64,224;spacing=np.array([10.5/(X-1),3/(Y-1),4.2/(Z-1)],dtype='f4');origin=np.array([-5.25,-1.5,0]);x=np.linspace(-5.25,5.25,X)[None,:];z=np.linspace(0,4.2,Z)[:,None]
for f in selected:
    grid=np.zeros((Z,Y,X),'f4');p=P[f];q=(p-origin)/spacing;b=np.floor(q).astype(int);frac=q-b;ok=(E[f]>.005)&np.all(b>=0,axis=1)&np.all(b<np.array([X,Y,Z])-1,axis=1);b=b[ok];frac=frac[ok];mass=E[f,ok]*.30
    for i in [0,1]:
        for j in [0,1]:
            for k in [0,1]:
                ijk=b+[i,j,k];w=(frac[:,0] if i else 1-frac[:,0])*(frac[:,1] if j else 1-frac[:,1])*(frac[:,2] if k else 1-frac[:,2]);np.add.at(grid,(ijk[:,2],ijk[:,1],ijk[:,0]),w*mass)
    density=gaussian_filter(grid,(.9,.65,.9),mode='constant');sigma=density**1.45*3.0;top=np.cumsum(sigma[::-1],axis=0)[::-1]*spacing[2];back=np.cumsum(sigma[:,::-1],axis=1)[:,::-1]*spacing[1]
    transmission=np.ones((Z,X),'f4');linear=np.zeros((Z,X,3),'f4')
    for j,y in enumerate(np.linspace(-1.5,1.5,Y)):
        lit=np.exp(-top[:,j]*1.7-back[:,j]*.8);cosine=(2-y)/np.sqrt((x+2)**2+(2-y)**2+(z-4)**2);phase=(1-.45**2)/np.maximum(.05,1+.45**2-2*.45*cosine)**1.5
        alpha=1-np.exp(-sigma[:,j]*spacing[1]);linear+=transmission[...,None]*alpha[...,None]*(lit*phase*4.2+.18)[...,None]*np.array([.66,.76,.83]);transmission*=1-alpha
    linear=np.maximum(0,linear[::-1]*.72);mapped=np.clip(linear*(2.51*linear+.03)/(linear*(2.43*linear+.59)+.14),0,1);mapped=np.where(mapped<=.0031308,mapped*12.92,1.055*mapped**(1/2.4)-.055)
    im=Image.fromarray(np.uint8(mapped*255)).resize((1920,768),Image.Resampling.LANCZOS);canvas=Image.new('RGB',(1920,1080));canvas.paste(im,(0,120));canvas.save(out/f'{f:04}.jpg',quality=97)
    if f%20==0:print('WAKE VOLUME',f,flush=True)
(R/'flight-volume-mechanism.json').write_text(json.dumps({'source':'integrated counter-rotating wake particles','rasterization':'trilinear particle-to-volume transfer and fixed reconstruction kernel','lighting':'accepted air model: directional phase function, Beer-Lambert transmission, approximate top/back self-shadowing','frames':selected,'limits':'One-way tracer-density reconstruction with approximate single scattering; not a fully pressure-projected flight solve'},indent=2),encoding='utf-8')
