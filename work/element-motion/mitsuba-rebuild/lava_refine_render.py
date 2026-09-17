"""Mitsuba CPU hero views with integrated thermal radiance."""
from pathlib import Path
import os,time,json,argparse,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='2'
import numpy as np,psutil,mitsuba as mi,drjit as dr
from PIL import Image
from scipy.ndimage import gaussian_filter
from scipy.sparse import coo_matrix,diags
mi.set_variant('scalar_rgb');dr.set_thread_count(2);proc=psutil.Process();proc.cpu_affinity(proc.cpu_affinity()[:2])
from mesh_io import ply
from lava_radiation import radiance
from cpu_oidn import denoise
R=Path(__file__).resolve().parent/'lava-focus';T=mi.ScalarTransform4f

def light_weight(rgb,area):
 # Mitsuba's default is equal weight per emitter. Splitting this surface
 # into temperature bins must not starve the main lights of samples.
 return max(1e-8,float(np.dot(rgb,[.2126,.7152,.0722]))*float(area))

def mapped(hdr,exposure):
 a=np.maximum(hdr*exposure,0);a=np.clip(a*(2.51*a+.03)/(a*(2.43*a+.59)+.14),0,1);return np.where(a<=.0031308,a*12.92,1.055*a**(1/2.4)-.055)

def main(frame=59,spp=24,width=640,view='hero',revision='restored-clean',normal_only=False,no_micro=False):
 start=time.time();source=R/(os.environ.get('LAVA_SOURCE') or 'iterations/01/surface-0059.npz');a=np.load(source);v=a['v'];f=a['f'];normal=a['normal'];uv=a['rest'][:,:2]*4.;temperature=a['temperature'][f].mean(1);out=R/'renders';out.mkdir(exist_ok=True);geo=R/f'geometry-{revision}';geo.mkdir(exist_ok=True)
 # Filter shading normals at the mesh sampling scale. The silhouettes,
 # cracks and occlusion remain geometric; subpixel slope variance belongs
 # in the roughness instead of aliased bright pinpoints.
 edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);rows=np.concatenate([edges[:,0],edges[:,1]]);cols=np.concatenate([edges[:,1],edges[:,0]]);adj=coo_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(v),len(v))).tocsr();average=diags(1/np.maximum(np.asarray(adj.sum(1)).ravel(),1))@adj
 for _ in range(int(os.environ.get('LAVA_NORMAL_SMOOTH','0'))):normal=.4*normal+.6*(average@normal)
 normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-8)
 center=[-.17,0,.04];eye=[1.1,-2.9,2.25];fov=35.
 if view=='detail':center=[-.10,0,.06];eye=[.55,-1.08,.90];fov=42.
 
 if os.environ.get('LAVA_SOURCE'):
  center=[-.17,0,.12];eye=[.82,-2.43,1.58];fov=35.
 cam=T().look_at(origin=eye,target=center,up=[0,0,1]);height=round(width*.75)
 scene={'type':'scene','integrator':{'type':'aov','aovs':'albedo:albedo,normal:geo_normal,depth:depth','beauty':{'type':'path','max_depth':12,'rr_depth':6}},'sensor':{'type':'perspective','to_world':cam,'fov':fov,'sampler':{'type':'independent','sample_count':spp},'film':{'type':'hdrfilm','width':width,'height':height,'pixel_format':'rgba','rfilter':{'type':'tent'}}}}
 if normal_only:scene['integrator']={'type':'aov','aovs':'normal:geo_normal'}
 if view=='detail':scene['sensor'].update(type='thinlens',aperture_radius=.003,focus_distance=float(np.linalg.norm(np.array(eye)-center)))
 weights={}
 for name,position,size,color in [('key',[-1.1,.75,-.6],[1.0,.3,1],[60.,62.,65.]),('fill',[1.0,.4,-.4],[.18,.85,1],[12.,11.,10.])]:
  color=(np.array(color)*float(os.environ.get('LAVA_LIGHT_GAIN','1'))).tolist();weights[name]=light_weight(color,4*size[0]*size[1])
  scene[name]={'type':'rectangle','to_world':cam@T().translate(position)@T().scale(size),'emitter':{'type':'area','sampling_weight':weights[name],'radiance':{'type':'rgb','value':color}}}
 groups=np.floor(temperature/16).astype(int)
 for group in np.unique(groups):
  select=groups==group;temp=float(temperature[select].mean());path=geo/f'lava-{group}.ply';ply(path,v,f[select],normal,uv);solid=float(np.clip((1330-temp)/240,0,1));alpha=.13+.31*solid
  material={'type':'roughplastic','distribution':'ggx','alpha':alpha,'diffuse_reflectance':{'type':'rgb','value':[.013+.008*solid,.009+.013*solid,.006+.018*solid]},'int_ior':1.58,'nonlinear':True}
  if solid>.45 and os.environ.get('LAVA_SURFACE_MIX'):
   matte=dict(material,alpha=.50);glassy=dict(material,alpha=.16)
   material={'type':'blendbsdf','weight':{'type':'bitmap','filename':str(R/'basalt-roughness-mix.png'),'raw':True},'bsdf_0':glassy,'bsdf_1':matte}
  if not no_micro:material={'type':'bumpmap','scale':float(os.environ.get('LAVA_BUMP_SCALE','.00045'))*solid,'texture':{'type':'bitmap','filename':str(R/os.environ.get('LAVA_BUMP_TEXTURE','basalt-micro.png')),'raw':True},'material':material}
  scene[f'lava_{group}']={'type':'ply','filename':str(path),'bsdf':material}
  if temp>1100:
   rgb=radiance(temp);triangles=v[f[select]];area=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1).sum()*.5;weights[f'lava_{group}']=light_weight(rgb,area)
   scene[f'lava_{group}']['emitter']={'type':'area','sampling_weight':weights[f'lava_{group}'],'radiance':{'type':'rgb','value':rgb}}
 print('LIGHT_SAMPLING',json.dumps({'emitters':len(weights),'keyProbability':weights['key']/sum(weights.values()),'mode':'luminance times emitter area'}),flush=True)
 scene=mi.load_dict(scene);render_start=time.time();parts={};done=0
 checkpoint=out/f'{revision}-{view}-{frame:04}-{width}-checkpoint'
 while done<spp:
  batch=min(8,spp-done);mi.render(scene,spp=batch,seed=319+done)
  bitmap=scene.sensors()[0].film().bitmap(raw=False)
  current={name:np.array(bmp) for name,bmp in bitmap.split()}
  parts={name:(parts[name]*done+value*batch)/(done+batch) if name in parts else value for name,value in current.items()};done+=batch
  if not normal_only:
   mi.Bitmap(np.ascontiguousarray(parts['beauty'][...,:3])).write(str(checkpoint.with_suffix('.exr')))
   np.savez_compressed(str(checkpoint)+'-raw-aov.npz',color=parts['beauty'][...,:3],albedo=parts['albedo'],normal=parts['normal'])
   checkpoint.with_suffix('.json').write_text(json.dumps({'samplesPerPixel':done,'width':width,'height':height,'device':'CPU','frame':frame,'view':view,'seconds':time.time()-render_start},indent=2))
  print('SAMPLES',done,'of',spp,'seconds',round(time.time()-render_start,2),flush=True)
 names={name:list(value.shape) for name,value in parts.items()};print('AOV',json.dumps(names),flush=True)
 if normal_only:
  path=out/f'{revision}-{view}-{frame:04}-{width}-world-normal.npy';np.save(path,parts['normal']);print('NORMAL_ONLY',str(path),round(time.time()-start,2),flush=True);return
 beauty=parts.get('beauty',parts.get('<root>'));assert beauty is not None;hdr=np.ascontiguousarray(beauty[...,:3]);albedo=parts.get('albedo');shnormal=parts.get('normal');assert np.isfinite(hdr).all();stem=out/f'{revision}-{view}-{frame:04}-{width}-{spp}spp';mi.Bitmap(hdr).write(str(stem.with_suffix('.exr')));render_seconds=time.time()-render_start;np.savez_compressed(str(stem)+'-raw-aov.npz',color=hdr,albedo=albedo,normal=shnormal);dn_start=time.time();clean=denoise(hdr,albedo,shnormal);denoise_seconds=time.time()-dn_start
 # Preserve exact black outside the path-traced scene. No environment,
 # gradient backdrop or painted haze is added.
 background=np.max(np.abs(hdr),axis=-1)==0;clean[background]=0;exposure=float(os.environ.get('LAVA_EXPOSURE','5.0'))
 raw=mapped(hdr,exposure);final=mapped(clean,exposure);Image.fromarray((np.clip(raw,0,1)*255).astype('u1')).save(str(stem)+'-raw.png');Image.fromarray((np.clip(final,0,1)*255).astype('u1')).save(stem.with_suffix('.png'));np.savez_compressed(str(stem)+'-aov.npz',color=hdr,albedo=albedo,normal=shnormal,denoised=clean)
 receipt={'renderer':'Mitsuba '+mi.__version__,'variant':mi.variant(),'device':'CPU','threads':dr.thread_count(),'affinity':proc.cpu_affinity(),'samplesPerPixel':spp,'size':[width,height],'renderSeconds':round(render_seconds,2),'denoiseSeconds':round(denoise_seconds,2),'totalSeconds':round(time.time()-start,2),'denoiser':'OIDN, explicitly CPU; GPU backends disabled','exposure':exposure,'background':'exact black','radianceQuantiles':np.quantile(hdr,[.5,.95,.99,.999,1]).tolist(),'meshSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'imageSha256':hashlib.sha256(stem.with_suffix('.png').read_bytes()).hexdigest(),'emission':'Planck spectrum integrated against Mitsuba CIE functions, then traced in RGB','normalAov':'world geometric normal','lightSampling':{'mode':'luminance times emitter area','emitters':len(weights),'keyProbability':weights['key']/sum(weights.values())},'source':str(source),'normalSmoothingIterations':int(os.environ.get('LAVA_NORMAL_SMOOTH','0')),'lightGain':float(os.environ.get('LAVA_LIGHT_GAIN','1')),'surfaceMix':bool(os.environ.get('LAVA_SURFACE_MIX')),'bumpTexture':os.environ.get('LAVA_BUMP_TEXTURE','basalt-micro.png'),'bumpScale':float(os.environ.get('LAVA_BUMP_SCALE','.00045')),'camera':{'eye':eye,'target':center,'fov':fov},'status':'candidate; direct visual review required'};stem.with_suffix('.json').write_text(json.dumps(receipt,indent=2));print('LAVA_IMAGE',json.dumps(receipt),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--frame',type=int,default=59);ap.add_argument('--spp',type=int,default=24);ap.add_argument('--width',type=int,default=640);ap.add_argument('--view',choices=['hero','detail'],default='hero');ap.add_argument('--revision',default='restored-clean');ap.add_argument('--normal-only',action='store_true');ap.add_argument('--no-micro',action='store_true');a=ap.parse_args();assert a.width<=1600 and a.spp<=128;main(a.frame,a.spp,a.width,a.view,a.revision,a.normal_only,a.no_micro)

