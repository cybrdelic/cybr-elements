"""Mitsuba CPU hero views with integrated thermal radiance."""
from pathlib import Path
import os,time,json,argparse,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='2'
import numpy as np,psutil,mitsuba as mi,drjit as dr
from PIL import Image
from scipy.ndimage import gaussian_filter
mi.set_variant('scalar_rgb');dr.set_thread_count(2);proc=psutil.Process();proc.cpu_affinity(proc.cpu_affinity()[:2])
from mesh_io import ply
from lava_radiation import radiance
from cpu_oidn import denoise
R=Path(__file__).resolve().parent/'lava-focus';T=mi.ScalarTransform4f

def mapped(hdr,exposure):
 a=np.maximum(hdr*exposure,0);a=np.clip(a*(2.51*a+.03)/(a*(2.43*a+.59)+.14),0,1);return np.where(a<=.0031308,a*12.92,1.055*a**(1/2.4)-.055)

def main(frame=59,spp=24,width=640,view='hero',revision='v2',normal_only=False,no_micro=False):
 start=time.time();source=R/f'surface-{frame:04}.npz';a=np.load(source);v=a['v'];f=a['f'];normal=a['normal'];uv=a['rest'][:,:2]*4.;temperature=a['temperature'][f].mean(1);out=R/'renders';out.mkdir(exist_ok=True);geo=R/f'geometry-{frame:04}';geo.mkdir(exist_ok=True)
 center=[-.17,0,.04];eye=[1.05,-2.5,1.75];fov=37.
 if view=='detail':center=[-.35,-.08,.045];eye=[.12,-1.2,1.15];fov=32.
 cam=T().look_at(origin=eye,target=center,up=[0,0,1]);height=round(width*.625)
 scene={'type':'scene','integrator':{'type':'aov','aovs':'albedo:albedo,normal:geo_normal,depth:depth','beauty':{'type':'path','max_depth':12,'rr_depth':6}},'sensor':{'type':'perspective','to_world':cam,'fov':fov,'sampler':{'type':'independent','sample_count':spp},'film':{'type':'hdrfilm','width':width,'height':height,'pixel_format':'rgba','rfilter':{'type':'tent'}}}}
 if normal_only:scene['integrator']={'type':'aov','aovs':'normal:geo_normal'}
 for name,position,size,color in [('key',[-1.8,1.5,.15],[1.0,.3,1],[18,19,20]),('fill',[1.0,.4,-.4],[.18,.85,1],[1.2,1.1,1])]:
  scene[name]={'type':'rectangle','to_world':cam@T().translate(position)@T().scale(size),'emitter':{'type':'area','radiance':{'type':'rgb','value':color}}}
 groups=np.floor(temperature/8).astype(int)
 for group in np.unique(groups):
  select=groups==group;temp=float(temperature[select].mean());path=geo/f'lava-{group}.ply';ply(path,v,f[select],normal,uv);solid=float(np.clip((1330-temp)/240,0,1));alpha=.13+.13*solid
  material={'type':'roughplastic','distribution':'ggx','alpha':alpha,'diffuse_reflectance':{'type':'rgb','value':[.007+.004*solid,.005+.007*solid,.003+.010*solid]},'int_ior':1.58,'nonlinear':True}
  if not no_micro:material={'type':'bumpmap','scale':.000030*solid,'texture':{'type':'bitmap','filename':str(R/'basalt-micro.png'),'raw':True},'material':material}
  scene[f'lava_{group}']={'type':'ply','filename':str(path),'bsdf':material}
  if temp>1100:scene[f'lava_{group}']['emitter']={'type':'area','radiance':{'type':'rgb','value':radiance(temp)}}
 scene=mi.load_dict(scene);render_start=time.time();mi.render(scene,spp=spp,seed=319);bitmap=scene.sensors()[0].film().bitmap(raw=False);parts={name:np.array(bmp) for name,bmp in bitmap.split()};names={name:list(value.shape) for name,value in parts.items()};print('AOV',json.dumps(names),flush=True)
 if normal_only:
  path=out/f'{revision}-{view}-{frame:04}-{width}-world-normal.npy';np.save(path,parts['normal']);print('NORMAL_ONLY',str(path),round(time.time()-start,2),flush=True);return
 beauty=parts.get('beauty',parts.get('<root>'));assert beauty is not None;hdr=np.ascontiguousarray(beauty[...,:3]);albedo=parts.get('albedo');shnormal=parts.get('normal');assert np.isfinite(hdr).all();stem=out/f'{revision}-{view}-{frame:04}-{width}-{spp}spp';mi.Bitmap(hdr).write(str(stem.with_suffix('.exr')));render_seconds=time.time()-render_start;np.savez_compressed(str(stem)+'-raw-aov.npz',color=hdr,albedo=albedo,normal=shnormal);dn_start=time.time();clean=denoise(hdr,albedo,shnormal);denoise_seconds=time.time()-dn_start
 # Preserve exact black outside the path-traced scene. No environment,
 # gradient backdrop or painted haze is added.
 background=np.max(np.abs(hdr),axis=-1)==0;clean[background]=0;exposure=7.0
 raw=mapped(hdr,exposure);final=mapped(clean,exposure);Image.fromarray((np.clip(raw,0,1)*255).astype('u1')).save(str(stem)+'-raw.png');Image.fromarray((np.clip(final,0,1)*255).astype('u1')).save(stem.with_suffix('.png'));np.savez_compressed(str(stem)+'-aov.npz',color=hdr,albedo=albedo,normal=shnormal,denoised=clean)
 receipt={'renderer':'Mitsuba '+mi.__version__,'variant':mi.variant(),'device':'CPU','threads':dr.thread_count(),'affinity':proc.cpu_affinity(),'samplesPerPixel':spp,'size':[width,height],'renderSeconds':round(render_seconds,2),'denoiseSeconds':round(denoise_seconds,2),'totalSeconds':round(time.time()-start,2),'denoiser':'OIDN, explicitly CPU; GPU backends disabled','exposure':exposure,'background':'exact black','radianceQuantiles':np.quantile(hdr,[.5,.95,.99,.999,1]).tolist(),'meshSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'imageSha256':hashlib.sha256(stem.with_suffix('.png').read_bytes()).hexdigest(),'emission':'Planck spectrum integrated against Mitsuba CIE functions, then traced in RGB','status':'candidate; direct visual review required'};stem.with_suffix('.json').write_text(json.dumps(receipt,indent=2));print('LAVA_IMAGE',json.dumps(receipt),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--frame',type=int,default=59);ap.add_argument('--spp',type=int,default=24);ap.add_argument('--width',type=int,default=640);ap.add_argument('--view',choices=['hero','detail'],default='hero');ap.add_argument('--revision',default='v2');ap.add_argument('--normal-only',action='store_true');ap.add_argument('--no-micro',action='store_true');a=ap.parse_args();assert a.width<=1600 and a.spp<=128;main(a.frame,a.spp,a.width,a.view,a.revision,a.normal_only,a.no_micro)
