"""Relight cached thermal fields without changing the simulation."""
from pathlib import Path
import argparse
import numpy as np
from PIL import Image,ImageFilter
R=Path(__file__).resolve().parent
a=argparse.ArgumentParser();a.add_argument('--frames',default='45,52,56,60');a.add_argument('--gain',type=float,default=5);a.add_argument('--exposure',type=float,default=1.0);a.add_argument('--output',default='combustion-look');a.add_argument('--cache',default='combustion');q=a.parse_args()
out=R/'frames'/q.output;out.mkdir(parents=True,exist_ok=True)
if q.frames=='all':
    # Independent cached frames need no shared GPU state. Keep the CPU pool
    # bounded so the final optical pass does not monopolize the workstation.
    import subprocess,sys
    from concurrent.futures import ThreadPoolExecutor
    def group(offset):
        subprocess.run([sys.executable,__file__,'--frames',','.join(str(f) for f in range(offset,120,3)),'--gain',str(q.gain),'--exposure',str(q.exposure),'--output',q.output,'--cache',q.cache],check=True)
    with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(group,range(3)))
    raise SystemExit(0)
frames=range(120) if q.frames=='all' else list(map(int,q.frames.split(',')))
for f in frames:
    fields=np.load(R/'cache'/q.cache/f'{f:04}.npz')['fields'];Z,Y,X=fields.shape[1:];trans=np.ones((Z,X),dtype='f4');rgb=np.zeros((Z,X,3),dtype='f4');dy=3/(Y-1);dz=4.2/(Z-1)
    for j in range(Y):
        temp,soot,reaction=fields[:,:,j,:].astype('f4');hot=np.clip((temp-.10)/1.55,0,1);sigma=np.clip(soot*4.4+reaction*.02,0,16)
        color=np.stack([np.ones_like(hot),.045+.78*hot**1.15,.002+.25*hot**4],axis=-1)
        light=np.exp(-np.cumsum(soot[::-1],axis=0)[::-1]*dz*4.4)
        source=color*(reaction*.70+soot*hot**3*q.gain)[...,None]+soot[...,None]*light[...,None]*np.array([.04,.045,.055],dtype='f4')
        alpha=1-np.exp(-sigma*dy);rgb+=trans[...,None]*source*(alpha/np.maximum(sigma,1e-6))[...,None];trans*=1-alpha
    rgb=np.maximum(0,rgb[::-1]*q.exposure);mapped=np.clip(rgb*(2.51*rgb+.03)/(rgb*(2.43*rgb+.59)+.14),0,1);mapped=np.where(mapped<=.0031308,mapped*12.92,1.055*mapped**(1/2.4)-.055)
    image=Image.fromarray(np.uint8(np.clip(mapped*255,0,255))).resize((1920,768),Image.Resampling.LANCZOS);canvas=Image.new('RGB',(1920,1080));canvas.paste(image,(0,120));canvas.save(out/f'{f:04}.jpg',quality=97)
    print('RELIT',f,flush=True)
