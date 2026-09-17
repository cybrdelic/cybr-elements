"""CPU Mitsuba close-up; only material coupons, never the rejected trail."""
from pathlib import Path
import os,time,json,argparse,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='2'
import mitsuba as mi,drjit as dr,numpy as np,psutil
from PIL import Image
mi.set_variant('scalar_spectral');dr.set_thread_count(2);process=psutil.Process();process.cpu_affinity(process.cpu_affinity()[:2])
from render import ply
R=Path(__file__).resolve().parent;T=mi.ScalarTransform4f

def main(spp=32):
 start=time.time();out=R/'coupons/lava';cam=T().look_at(origin=[.32,-.8,.67],target=[.26,0,.025],up=[0,0,1]);geo=out/'geometry';geo.mkdir(exist_ok=True)
 scene={'type':'scene','integrator':{'type':'path','max_depth':10},'sensor':{'type':'orthographic','to_world':cam@T().scale([.37,.37,1]),'sampler':{'type':'independent','sample_count':spp},'film':{'type':'hdrfilm','width':640,'height':480,'pixel_format':'rgb','rfilter':{'type':'tent'}}}}
 # Both softboxes sit behind the camera plane and cannot contaminate its
 # black background. Their reflections still reveal the folded relief.
 for name,position,scale,color in [('key',[-.3,.35,-.6],[.36,.11,1],[210,220,230]),('fill',[.6,.15,-.4],[.12,.4,1],[90,85,80])]:
  scene[name]={'type':'rectangle','to_world':cam@T().translate(position)@T().scale(scale),'emitter':{'type':'area','radiance':{'type':'rgb','value':color}}}
 for tag in ['melt','skin']:
  a=np.load(out/f'{tag}.npz');v=a['v'];f=a['f'];normal=a['normal'];uv=a['uv']*4;temperature=a['temperature'][f].mean(1);bins=np.floor(temperature/28).astype(int)
  for group in np.unique(bins):
   select=bins==group;temp=float(temperature[select].mean());path=geo/f'{tag}-{group}.ply';ply(path,v,f[select],normal,uv)
   bsdf={'type':'roughplastic','int_ior':1.58,'distribution':'ggx','alpha':.21 if tag=='skin' else .11,'diffuse_reflectance':{'type':'rgb','value':[.023,.024,.025] if tag=='skin' else [.012,.007,.004]},'nonlinear':True}
   if tag=='skin':bsdf={'type':'bumpmap','scale':.00027,'texture':{'type':'bitmap','filename':str(R.parent/'realism/assets/rock_boulder_cracked_disp_2k.jpg'),'raw':True},'material':bsdf}
   scene[f'{tag}_{group}']={'type':'ply','filename':str(path),'bsdf':bsdf}
   if temp>800:scene[f'{tag}_{group}']['emitter']={'type':'area','radiance':{'type':'blackbody','temperature':temp}}
 image=mi.render(mi.load_dict(scene),spp=spp,seed=31);hdr=np.asarray(mi.Bitmap(image));assert np.isfinite(hdr).all();path=out/f'mitsuba-{spp}spp';mi.Bitmap(image).write(str(path.with_suffix('.exr')));linear=np.maximum(0,hdr*2.5);mapped=np.clip(linear*(2.51*linear+.03)/(linear*(2.43*linear+.59)+.14),0,1);srgb=np.where(mapped<=.0031308,mapped*12.92,1.055*mapped**(1/2.4)-.055);Image.fromarray((srgb*255).astype('u1')).save(path.with_suffix('.png'));report={'renderer':'Mitsuba 3.9.1','variant':mi.variant(),'device':'CPU','threads':2,'size':[640,480],'spp':spp,'seconds':round(time.time()-start,3),'status':'requires visual review; not a final effect','png':str(path.with_suffix('.png'))};path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--spp',type=int,default=32);a=ap.parse_args();assert a.spp<=64;main(a.spp)
