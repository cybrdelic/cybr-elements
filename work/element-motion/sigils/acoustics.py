"""Damped projected acoustic wave fields sourced by the original sigil.

Pressure and sound are rendered as amplified optical-gradient diagnostics.
The wave equation is solved in the source plane, not full 3D acoustics.
"""
from pathlib import Path
import argparse,time,json
import numpy as np
import cv2
from PIL import Image
from motion import camera
R=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('--variant',required=True);p.add_argument('--until',type=int,default=450);q=p.parse_args();d=np.load(R/f'source-{q.variant}.npz')
mask=d['mask'].astype('f4');arrival=d['arrival'];H,W=mask.shape;dx=10.5/(W-1);dz=5.8/(H-1);dt=1/120
xx,zz=np.meshgrid(np.linspace(-5.25,5.25,W),np.linspace(0,5.8,H));edge=np.minimum.reduce([np.broadcast_to(np.minimum(np.arange(W),np.arange(W)[::-1])[None,:],mask.shape),np.broadcast_to(np.minimum(np.arange(H),np.arange(H)[::-1])[:,None],mask.shape)])
sponge=np.clip(edge/24,0,1)**.15
guide=cv2.GaussianBlur(mask,(0,0),1.2)
for kind in ['sound','pressure']:
    out=R/'frames'/f'{kind}-{q.variant}';out.mkdir(parents=True,exist_ok=True);pressure=np.zeros_like(mask);velocity=np.zeros_like(mask);c=1.05 if kind=='sound' else .72;damping=.85 if kind=='sound' else 1.3;start=time.time()
    for f in range(q.until):
        for sub in range(4):
            t=(f+sub/4)/30;active=mask*(arrival<t)*(t<11)
            lap=(np.roll(pressure,1,1)+np.roll(pressure,-1,1)-2*pressure)/dx**2+(np.roll(pressure,1,0)+np.roll(pressure,-1,0)-2*pressure)/dz**2
            phase=t%( .58 if kind=='sound' else 1.25);pulse=(1-2*(phase/.075)**2)*np.exp(-(phase/.075)**2)
            confinement=max(0,1-max(0,t-11)/1.5);loss=(1-guide)*confinement
            velocity+=(c*c*lap+active*pulse*8)*dt;velocity*=np.exp(-(damping+loss*24)*dt)*sponge;pressure+=velocity*dt;pressure*=np.exp(-loss*9*dt)*sponge
        assert np.isfinite(pressure).all()
        gz,gx=np.gradient(pressure,dz,dx);gradient=np.sqrt(gx*gx+gz*gz)
        light=(1-np.exp(-gradient*gradient*18))[...,None]*np.array([.50,.65,.73],dtype='f4')
        if f in [90,240,360]:
            cache=R/'acoustic-fields';cache.mkdir(exist_ok=True);np.savez_compressed(cache/f'{kind}-{q.variant}-{f:04}.npz',pressure=pressure,velocity=velocity)
        t=f/30;cx,width=camera(d,t);height=width*9/16;vx,vz=np.meshgrid(np.linspace(cx-width/2,cx+width/2,1920),np.linspace(2.35+height/2,2.35-height/2,1080))
        sample=cv2.remap(light,((vx+5.25)/10.5*(W-1)).astype('f4'),(vz/5.8*(H-1)).astype('f4'),cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT)
        rgb=np.clip(sample,0,1)**(1/2.2);Image.fromarray(np.uint8(rgb*255)).save(out/f'{f:04}.jpg',quality=97)
        if f%90==0:print('ACOUSTIC',kind,q.variant,f,round(time.time()-start,1),flush=True)
    (R/f'acoustic-{kind}-{q.variant}.json').write_text(json.dumps({'frames':q.until,'complete':q.until==450,'method':'Damped planar acoustic wave equation in an authored sigil waveguide; amplified optical gradient view','source':'original sigil mask and arrival','seconds':time.time()-start},indent=2),encoding='utf-8')
