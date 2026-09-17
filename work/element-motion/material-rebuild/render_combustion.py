"""Depth-integrated hot soot radiation and self-shadowed smoke from saved fields."""
from pathlib import Path
import sys,os,time,numpy as np
from scipy.ndimage import gaussian_filter,zoom
from PIL import Image
R=Path(__file__).resolve().parent;D=R.parent/'dynamics';out=R/'frames/combustion';out.mkdir(parents=True,exist_ok=True)
frames=range(120) if '--full' in sys.argv else map(int,sys.argv[sys.argv.index('--frames')+1].split(','))
for f in frames:
 started=time.time()
 fields=np.load(D/'cache/combustion'/f'{f:04}.npz')['fields'];Z,Y,X=fields.shape[1:];trans=np.ones((Z,X),dtype='f4');rgb=np.zeros((Z,X,3),dtype='f4');dy=3/(Y-1);dz=4.2/(Z-1)
 for j in range(Y):
  temp,soot,reaction=fields[:,:,j,:].astype('f4');hot=np.clip((temp-.13)/1.8,0,1.3);sigma=np.clip(soot*9+reaction*.045,0,20)
  color=np.stack([np.ones_like(hot),.025+.70*np.clip(hot,0,1)**1.9,.001+.27*np.clip(hot,0,1)**5],axis=-1)
  irradiance=np.exp(-np.cumsum(soot[::-1],axis=0)[::-1]*dz*7)
  source=color*(reaction*3.0+soot*hot**3.5*48)[...,None]+soot[...,None]*irradiance[...,None]*np.array([.038,.040,.046],dtype='f4')
  alpha=1-np.exp(-sigma*dy);rgb+=trans[...,None]*source*(alpha/np.maximum(sigma,1e-6))[...,None];trans*=1-alpha
 # Reconstruct radiance before display mapping. Upscaling a clipped LDR image
 # was smearing the bright thin reaction front into pale orange blobs.
 rgb=zoom(rgb,(2,2,1),order=3);rgb=np.maximum(0,rgb);bloom=gaussian_filter(np.maximum(0,rgb-.7),(2.5,2.5,0))*.065;rgb+=bloom
 mapped=np.clip(rgb*(2.51*rgb+.03)/(rgb*(2.43*rgb+.59)+.14),0,1);mapped=np.where(mapped<=.0031308,mapped*12.92,1.055*mapped**(1/2.4)-.055)
 im=Image.fromarray(np.uint8(np.clip(mapped[::-1]*255,0,255))).resize((1920,768),Image.Resampling.LANCZOS);canvas=Image.new('RGB',(1920,1080));canvas.paste(im,(0,120))
 if os.environ.get('CYBR_CPU_PROOF')=='1':
  from cpu_image_io import save_image
  save_image(canvas,'combustion',f,time.time()-started)
 else:
  assert not (R/'cpu-only-hold.json').exists(),'CPU stills only; movie generation is paused'
  canvas.save(out/f'{f:04}.jpg',quality=97)
 print('COMBUSTION',f,flush=True)
