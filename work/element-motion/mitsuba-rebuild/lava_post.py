"""Recover or retone an existing HDR render without tracing it again."""
from pathlib import Path
import os,time,json,argparse
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np,mitsuba as mi,psutil
from PIL import Image
mi.set_variant('scalar_spectral');process=psutil.Process();process.cpu_affinity(process.cpu_affinity()[:2])
from cpu_oidn import denoise
from lava_render import mapped
R=Path(__file__).resolve().parent/'lava-focus/renders'
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--stem',default='hero-0059-640-24spp');ap.add_argument('--exposure',type=float,default=5.);a=ap.parse_args();start=time.time();path=R/a.stem;hdr=np.array(mi.Bitmap(str(path.with_suffix('.exr'))));aux=Path(str(path)+'-raw-aov.npz');args={}
 if aux.exists():b=np.load(aux);args={'albedo':b['albedo'],'normal':b['normal']}
 clean=denoise(hdr,**args);clean[np.max(np.abs(hdr),axis=-1)==0]=0;mi.Bitmap(clean).write(str(path)+'-clean.exr')
 for name,im in [('-raw',hdr),('',clean)]:Image.fromarray((np.clip(mapped(im,a.exposure),0,1)*255).astype('u1')).save(str(path)+name+'.png')
 (R/(a.stem+'-post.json')).write_text(json.dumps({'operation':'CPU OIDN and exposure only; original Mitsuba HDR reused','seconds':round(time.time()-start,2),'exposure':a.exposure,'auxiliaryInputs':list(args),'gpu':False},indent=2));print('CPU post complete',round(time.time()-start,2),str(path.with_suffix('.png')))
