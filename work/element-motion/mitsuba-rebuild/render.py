"""Mitsuba spectral CPU images from newly solved geometry and volume fields."""
from pathlib import Path
import os,sys,json,time,hashlib,argparse
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='2'
import psutil,numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter
import mitsuba as mi,drjit as dr
mi.set_variant('scalar_spectral');dr.set_thread_count(2);proc=psutil.Process();proc.cpu_affinity(proc.cpu_affinity()[:2])
R=Path(__file__).resolve().parent;T=mi.ScalarTransform4f
assert mi.variant().startswith('scalar_')

def ply(path,v,f,normal,uv):
 unique,inverse=np.unique(f,return_inverse=True);v=v[unique];normal=normal[unique];uv=uv[unique];f=inverse.reshape(-1,3)
 vertices=np.zeros(len(v),dtype=[(name,'<f4') for name in ['x','y','z','nx','ny','nz','u','v']])
 for i,name in enumerate(['x','y','z']):vertices[name]=v[:,i]
 for i,name in enumerate(['nx','ny','nz']):vertices[name]=normal[:,i]
 vertices['u']=uv[:,0];vertices['v']=uv[:,1];faces=np.zeros(len(f),dtype=[('size','u1'),('index','<i4',(3,))]);faces['size']=3;faces['index']=f
 header='ply\nformat binary_little_endian 1.0\nelement vertex '+str(len(v))+'\n'+''.join('property float '+name+'\n' for name in vertices.dtype.names)+'element face '+str(len(f))+'\nproperty list uchar int vertex_indices\nend_header\n'
 with path.open('wb') as file:file.write(header.encode());vertices.tofile(file);faces.tofile(file)

def light(origin,target,size,radiance):
 return {'type':'rectangle','to_world':T().look_at(origin=origin,target=target,up=[0,0,1])@T().scale([size[0],size[1],1]),'emitter':{'type':'area','radiance':{'type':'rgb','value':radiance}}}

def main(kind,frame,spp,width):
 hold=R/'quality-hold.json'
 if hold.exists() and json.loads(hold.read_text()).get('status')=='rejected':raise RuntimeError('Full trail rendering is held after visual rejection. Validate a separate material coupon first.')
 start=time.time();source=R/'mesh'/kind/f'{frame:04}.npz';a=np.load(source);v=a['v'];f=a['f'];normal=a['normal'];uv=a['rest'][:,[0,2]]*.85;out=R/'renders'/kind;out.mkdir(parents=True,exist_ok=True);geo=out/'geometry';geo.mkdir(exist_ok=True)
 center=[-.2,0,1.9];scene={'type':'scene','integrator':{'type':'volpathmis','max_depth':16,'rr_depth':6,'hide_emitters':True},'sensor':{'type':'orthographic','to_world':T().look_at(origin=[-.05,-15,2.15],target=center,up=[0,0,1])@T().scale([3.8,3.8,1]),'film':{'type':'hdrfilm','width':width,'height':int(width*.75),'pixel_format':'rgb','rfilter':{'type':'tent'}},'sampler':{'type':'independent','sample_count':spp}},'key':light([-1.3,-3,5.6],center,[2.3,.55],[8,7.7,7.3]),'rim':light([3.8,1.4,3.3],center,[.25,1.8],[16,17,18]),'edge':light([-3.7,1.1,2.6],center,[.24,1.7],[8,9,10])}
 if kind=='ice':
  scene['transmission']=light([.8,3,4.4],center,[3.5,.36],[.9,1.0,1.1])
  scene['ice_fill']=light([-2.8,2,1.2],center,[.36,1.6],[.4,.48,.53])
  path=geo/f'ice-{frame:04}.ply';ply(path,v,f,normal,uv);scene['ice_medium']={'type':'homogeneous','sigma_t':{'type':'rgb','value':[.18,.065,.04]},'albedo':{'type':'rgb','value':[.12,.16,.20]},'sample_emitters':False};scene['ice']={'type':'ply','filename':str(path),'bsdf':{'type':'roughdielectric','distribution':'ggx','alpha':.011,'int_ior':1.31,'ext_ior':1.000277},'interior':{'type':'ref','id':'ice_medium'}}
  from ice_optics import add_cavities
  add_cavities(scene,mi,R,frame,v,ply)
  fog_path=R/'cache/ice'/f'vapor-{frame:04}.npz'
  if fog_path.exists():
   fog=np.load(fog_path);sigma=np.ascontiguousarray(fog['sigma'].transpose(2,1,0));origin=fog['origin'];size=np.array(fog['sigma'].shape)*float(fog['dx']);scene['cold_fog']={'type':'heterogeneous','sigma_t':{'type':'gridvolume','grid':mi.VolumeGrid(sigma),'to_world':T().translate(origin)@T().scale(size)},'albedo':.998,'phase':{'type':'hg','g':.65}};scene['fog_bounds']={'type':'cube','to_world':T().translate(origin+size*.5)@T().scale(size*.5),'bsdf':{'type':'null'},'interior':{'type':'ref','id':'cold_fog'}};scene['ice']['exterior']={'type':'ref','id':'cold_fog'}
 elif kind=='lava':
  scene['integrator']['hide_emitters']=False
  scene['key']=light([-1.3,-3,7.4],center,[2.3,.55],[8,7.7,7.3])
  scene['rim']=light([5.8,1.4,3.3],center,[.25,1.8],[16,17,18])
  scene['edge']=light([-5.7,1.1,2.6],center,[.24,1.7],[8,9,10])
  surfaces=[('melt',a)]
  skin_path=R/'mesh/lava'/f'skin-{frame:04}.npz'
  if skin_path.exists():surfaces.append(('skin',np.load(skin_path)))
  for tag,material in surfaces:
   mv=material['v'];mf=material['f'];mn=material['normal'];muv=material['rest'][:,[0,2]]*2.3;temperatures=material['temperature'][mf].mean(1);bins=np.floor(temperatures/35).astype(int)
   for group in np.unique(bins):
    select=bins==group;path=geo/f'lava-{tag}-{frame:04}-{group}.ply';ply(path,mv,mf[select],mn,muv);temp=float(temperatures[select].mean());name=f'lava_{tag}_{group}';is_crust=tag=='skin'
    bsdf={'type':'roughplastic','distribution':'ggx','alpha':.42 if is_crust else .12,'diffuse_reflectance':{'type':'rgb','value':[.023,.022,.020] if is_crust else [.013,.009,.006]},'int_ior':1.5,'nonlinear':True}
    if is_crust:
     bsdf={'type':'bumpmap','scale':.0012,'texture':{'type':'bitmap','filename':str(R.parent/'realism/assets/rock_boulder_cracked_disp_2k.jpg'),'raw':True},'material':bsdf}
    scene[name]={'type':'ply','filename':str(path),'bsdf':bsdf}
    if temp>800:scene[name]['emitter']={'type':'area','radiance':{'type':'blackbody','temperature':temp}}
 else:raise ValueError(kind)
 scene=mi.load_dict(scene);load_seconds=time.time()-start;render_start=time.time();image=mi.render(scene,spp=spp,seed=188);hdr=np.asarray(mi.Bitmap(image)).copy();assert np.isfinite(hdr).all();mi.Bitmap(image).write(str(out/f'{frame:04}-{spp}spp.exr'))
 exposure=.42 if kind=='ice' else 4.0;linear=np.maximum(0,hdr*exposure);linear+=gaussian_filter(np.maximum(0,linear-1),(1.4,1.4,0))*.025;mapped=np.clip(linear*(2.51*linear+.03)/(linear*(2.43*linear+.59)+.14),0,1);srgb=np.where(mapped<=.0031308,mapped*12.92,1.055*mapped**(1/2.4)-.055);path=out/f'{frame:04}-{spp}spp.png';Image.fromarray((np.clip(srgb,0,1)*255).astype('u1')).save(path)
 report={'renderer':'Mitsuba','version':mi.__version__,'variant':mi.variant(),'device':'CPU','threads':dr.thread_count(),'affinity':proc.cpu_affinity(),'samplesPerPixel':spp,'size':[width,int(width*.75)],'frame':frame,'kind':kind,'sceneLoadSeconds':round(load_seconds,3),'renderSeconds':round(time.time()-render_start,3),'totalSeconds':round(time.time()-start,3),'exposure':exposure,'radianceQuantiles':np.quantile(hdr,[.5,.95,.999,1]).tolist(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'meshHash':hashlib.sha256(source.read_bytes()).hexdigest(),'cameraBackground':'black; no environment emitter','status':'diagnostic; visual and dynamics review required'};path.with_suffix('.json').write_text(json.dumps(report,indent=2));print('MITSUBA_CPU',json.dumps(report),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--kind',choices=['ice','lava'],required=True);ap.add_argument('--frame',type=int,default=61);ap.add_argument('--spp',type=int,default=32);ap.add_argument('--width',type=int,default=512);args=ap.parse_args();assert args.width<=1024 and args.spp<=128;main(args.kind,args.frame,args.spp,args.width)
