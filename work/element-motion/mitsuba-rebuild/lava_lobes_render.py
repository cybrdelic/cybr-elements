"""CPU Mitsuba material studies of the reference-led folded lava lobes."""
from pathlib import Path
import os,time,json,argparse,hashlib
os.environ['CUDA_VISIBLE_DEVICES']='-1';os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='2'
import numpy as np,psutil,mitsuba as mi,drjit as dr
from PIL import Image
from scipy.ndimage import gaussian_filter
from scipy.sparse import coo_matrix,diags
mi.set_variant('scalar_rgb');dr.set_thread_count(2);proc=psutil.Process();proc.cpu_affinity(proc.cpu_affinity()[:2])
from lava_emission_io import ply,LavaEmitter
from lava_radiation import radiance
from cpu_oidn import denoise
R=Path(__file__).resolve().parent/'lava-focus';T=mi.ScalarTransform4f

def light_weight(rgb,area):
 # Mitsuba's default is equal weight per emitter. Splitting this surface
 # into temperature bins must not starve the main lights of samples.
 return max(1e-8,float(np.dot(rgb,[.2126,.7152,.0722]))*float(area))

def mapped(hdr,exposure):
 a=np.maximum(hdr*exposure,0);a=np.clip(a*(2.51*a+.03)/(a*(2.43*a+.59)+.14),0,1);return np.where(a<=.0031308,a*12.92,1.055*a**(1/2.4)-.055)

def main(frame=59,spp=24,width=640,view='hero',revision='lava-folded',normal_only=False,no_micro=False):
 start=time.time();source=R/(os.environ.get('LAVA_SOURCE') or 'lobes/lobes-05.npz');a=np.load(source);v=a['v'];f=a['f'];normal=a['normal'];uv=a['uv'];temperature=a['temperature'][f].mean(1);out=R/'renders';out.mkdir(exist_ok=True);geo=R/f'geometry-{revision}';geo.mkdir(exist_ok=True)
 # Filter shading normals at the mesh sampling scale. The silhouettes,
 # cracks and occlusion remain geometric; subpixel slope variance belongs
 # in the roughness instead of aliased bright pinpoints.
 edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);rows=np.concatenate([edges[:,0],edges[:,1]]);cols=np.concatenate([edges[:,1],edges[:,0]]);adj=coo_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(v),len(v))).tocsr();average=diags(1/np.maximum(np.asarray(adj.sum(1)).ravel(),1))@adj
 for _ in range(int(os.environ.get('LAVA_NORMAL_SMOOTH','0'))):normal=.4*normal+.6*(average@normal)
 normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-8)
 center=[-.17,0,.04];eye=[1.1,-2.9,2.25];fov=35.
 if view=='detail':center=[-.10,0,.06];eye=[.55,-1.08,.90];fov=42.
 
 center=a['camera_target'].tolist();eye=a['camera_eye'].tolist();fov=float(a['camera_fov'])
 if view=='hero':center=[.11,.06,.13];fov=35.
 if view=='detail':center=[.43,.02,.15];eye=[1.12,-1.18,.83];fov=38.
 if os.environ.get('LAVA_SOURCE_CAMERA'):
  center=a['camera_target'].tolist();eye=a['camera_eye'].tolist();fov=float(a['camera_fov'])
  if view=='detail':center=[.18,-.055,.09];eye=[.85,-1.05,.64];fov=36.
 if os.environ.get('LAVA_BASELINE_MATERIAL') and view=='detail':
  center=[-.06,-.035,.235];eye=[.37,-1.07,.83];fov=37.
 cam=T().look_at(origin=eye,target=center,up=[0,0,1]);height=round(width*(.5625 if view=='hero' else .7))
 scene={'type':'scene','integrator':{'type':'aov','aovs':'albedo:albedo,normal:geo_normal,depth:depth','beauty':{'type':'path','max_depth':12,'rr_depth':6}},'sensor':{'type':'perspective','to_world':cam,'fov':fov,'sampler':{'type':'independent','sample_count':spp},'film':{'type':'hdrfilm','width':width,'height':height,'pixel_format':'rgba','rfilter':{'type':'tent'}}}}
 if normal_only:scene['integrator']={'type':'aov','aovs':'normal:geo_normal'}
 if view=='detail':scene['sensor'].update(type='thinlens',aperture_radius=.003,focus_distance=float(np.linalg.norm(np.array(eye)-center)))
 weights={}
 for name,position,size,color in [('key',[-1.1,.75,-.6],[1.0,.3,1],[60.,62.,65.]),('fill',[1.0,.4,-.4],[.18,.85,1],[12.,11.,10.])]:
  color=(np.array(color)*float(os.environ.get('LAVA_LIGHT_GAIN','.07'))).tolist();weights[name]=light_weight(color,4*size[0]*size[1])
  transform=cam@T().translate(position)@T().scale(size)
  if os.environ.get('LAVA_BACK_LIGHT'):
   location=[-1.1,.55,1.85] if name=='key' else [1.3,-.8,1.3]
   size=[.8,.30,1] if name=='key' else [.45,.6,1]
   transform=T().look_at(origin=location,target=[-.1,.02,.12],up=[0,0,1])@T().scale(size)
   if name=='fill':color=(np.array(color)*.18).tolist()
   weights[name]=light_weight(color,4*size[0]*size[1])
  if os.environ.get('LAVA_RAKING_LIGHT'):
   location=[-1.3,-1.05,.68] if name=='key' else [.6,.7,1.2]
   transform=T().look_at(origin=location,target=[-.15,0,.1],up=[0,0,1])@T().scale([.65,.28,1] if name=='key' else [.4,.6,1])
   if name=='fill':color=(np.array(color)*.12).tolist()
   weights[name]=light_weight(color,4*(.65*.28 if name=='key' else .4*.6))
  scene[name]={'type':'rectangle','to_world':transform,'emitter':{'type':'area','sampling_weight':weights[name],'radiance':{'type':'rgb','value':color}}}
 groups=np.floor(temperature/20).astype(int)
 stage=os.environ.get('LAVA_STAGE','')
 if stage=='obsidian':
  for i,(loc,size) in enumerate([([-1.2,-.45,.9],[.45,.75,1]),([1.0,-.2,1.0],[.28,.75,1]),([-.1,.6,1.2],[.65,.45,1])]):
   color=[.9,1.,1.05];weight=light_weight(color,4*size[0]*size[1]);weights['glass_box_'+str(i)]=weight
   scene['glass_box_'+str(i)]={'type':'rectangle','to_world':T().look_at(origin=loc,target=[-.1,0,.18],up=[0,0,1])@T().scale(size),'emitter':{'type':'area','radiance':{'type':'rgb','value':color},'sampling_weight':weight}}
 if (stage=='obsidian' and os.environ.get('LAVA_TRANSMISSIVE_OBSIDIAN')) or os.environ.get('LAVA_NATIVE_VOLUME'):
  scene['integrator']['beauty'].update(type='volpath',max_depth=16)
 if os.environ.get('LAVA_PLUME') and os.environ.get('LAVA_NATIVE_VOLUME'):
  plume=np.load(os.environ['LAVA_PLUME']);density=plume['density'].astype('f4')
  # VolumeGrid storage is z/y/x. Cache is x/y/z, with world-space bounds.
  grid=mi.VolumeGrid(np.ascontiguousarray(density.transpose(2,1,0)))
  lo=plume['origin'];extent=plume['extent'];transform=T().translate(lo.tolist())@T().scale(extent.tolist())
  scene['plume']={'type':'cube','to_world':transform@T().translate([.5,.5,.5])@T().scale(.5),'bsdf':{'type':'null'},'interior':{'type':'heterogeneous','sigma_t':{'type':'gridvolume','grid':grid,'raw':True,'to_world':transform},'albedo':.94,'phase':{'type':'hg','g':.35}}}
 temp_grid=np.arange(900.,1500.1,.5);rgb_grid=np.array([radiance(t) for t in temp_grid]);vertex_radiance=np.c_[tuple(np.interp(a['temperature'],temp_grid,rgb_grid[:,channel]) for channel in range(3))].astype('f4')
 for group in np.unique(groups):
  select=groups==group;temp=float(temperature[select].mean());path=geo/f'lava-{group}.ply';ply(path,v,f[select],normal,uv,vertex_radiance);solid=float(np.clip((1330-temp)/240,0,1));alpha=.32+.12*solid
  material={'type':'roughplastic','distribution':'ggx','alpha':alpha,'diffuse_reflectance':{'type':'rgb','value':[.013+.008*solid,.009+.013*solid,.006+.018*solid]},'int_ior':1.58,'nonlinear':True}
  if os.environ.get('LAVA_RUPTURE_MATERIAL'):
   # The exposed liquid has a smoother dielectric interface than the
   # quenched, vesicular skin. Keep older presets byte-for-byte unchanged.
   material['alpha']=.055+.39*solid**1.25
   material['diffuse_reflectance']={'type':'rgb','value':[.010+.004*solid,.008+.005*solid,.006+.006*solid]}
  if os.environ.get('LAVA_VOLUME_PORE'):
   material['alpha']=.13+.31*solid
   material['diffuse_reflectance']={'type':'rgb','value':[.015,.013,.012]}
  if stage in ['magma','lava'] and temp>1250:
   material['alpha']=.10
  if stage=='obsidian':
   material={'type':'roughplastic','distribution':'ggx','alpha':.09,'int_ior':1.51,'diffuse_reflectance':{'type':'rgb','value':[.0025,.002,.0015]},'nonlinear':True}
   if os.environ.get('LAVA_TRANSMISSIVE_OBSIDIAN'):
    material={'type':'roughdielectric','distribution':'ggx','alpha':.09,'int_ior':1.51,'ext_ior':1.0}
  if os.environ.get('LAVA_MATTE'):
   material['alpha']=.34+.30*solid
   material['nonlinear']=False
  if solid>.45 and os.environ.get('LAVA_SURFACE_MIX') and not os.environ.get('LAVA_MATTE') and not os.environ.get('LAVA_VOLUME_PORE'):
   matte=dict(material,alpha=.50);glassy=dict(material,alpha=.16)
   material={'type':'blendbsdf','weight':{'type':'bitmap','filename':str(R/'basalt-roughness-mix.png'),'raw':True},'bsdf_0':glassy,'bsdf_1':matte}
  if not no_micro and stage!='obsidian':
   texture={'type':'bitmap','filename':str(R/os.environ.get('LAVA_BUMP_TEXTURE','basalt-vesicles.png')),'raw':True}
   if os.environ.get('LAVA_VOLUME_PORE'):
    from lava_volume_texture import make_texture
    texture=make_texture()
   material={'type':'bumpmap','scale':float(os.environ.get('LAVA_BUMP_SCALE','.0014'))*solid,'texture':texture,'material':material}
  scene[f'lava_{group}']={'type':'ply','filename':str(path),'bsdf':material}
  if stage=='obsidian' and os.environ.get('LAVA_TRANSMISSIVE_OBSIDIAN'):
   scene[f'lava_{group}']['interior']={'type':'homogeneous','sigma_t':{'type':'rgb','value':[.6,.8,1.]},'scale':40.,'albedo':0.}
  if temp>1100:
   rgb=radiance(temp);triangles=v[f[select]];area=np.linalg.norm(np.cross(triangles[:,1]-triangles[:,0],triangles[:,2]-triangles[:,0]),axis=1).sum()*.5;weights[f'lava_{group}']=light_weight(rgb,area)
   scene[f'lava_{group}']['emitter']={'type':'lava_vertex_area','sampling_weight':weights[f'lava_{group}']}
 print('LIGHT_SAMPLING',json.dumps({'emitters':len(weights),'keyProbability':weights['key']/sum(weights.values()),'mode':'luminance times emitter area'}),flush=True)
 scene=mi.load_dict(scene);render_start=time.time();parts={};done=0
 for emitter in scene.emitters():
  if isinstance(emitter,LavaEmitter):emitter.set_scene(scene)
 checkpoint=out/f'{revision}-{view}-{frame:04}-{width}-checkpoint'
 while done<spp:
  batch=min(int(os.environ.get('LAVA_RENDER_BATCH','8')),spp-done);mi.render(scene,spp=batch,seed=319+done)
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
 background=(parts['depth']==0) if stage else (np.max(np.abs(hdr),axis=-1)==0);clean[background]=0;exposure=float(os.environ.get('LAVA_EXPOSURE','8.0'))
 volume_receipt=None
 if os.environ.get('LAVA_PLUME') and not os.environ.get('LAVA_NATIVE_VOLUME'):
  from lava_plume_integrate import integrate
  clean,volume_receipt=integrate(clean,parts['depth'],os.environ['LAVA_PLUME'],eye,center,fov,float(os.environ.get('LAVA_LIGHT_GAIN','.14')))
 raw=mapped(hdr,exposure);final=mapped(clean,exposure);Image.fromarray((np.clip(raw,0,1)*255).astype('u1')).save(str(stem)+'-raw.png');Image.fromarray((np.clip(final,0,1)*255).astype('u1')).save(stem.with_suffix('.png'));np.savez_compressed(str(stem)+'-aov.npz',color=hdr,albedo=albedo,normal=shnormal,denoised=clean)
 receipt={'renderer':'Mitsuba '+mi.__version__,'variant':mi.variant(),'device':'CPU','threads':dr.thread_count(),'affinity':proc.cpu_affinity(),'samplesPerPixel':spp,'size':[width,height],'renderSeconds':round(render_seconds,2),'denoiseSeconds':round(denoise_seconds,2),'totalSeconds':round(time.time()-start,2),'denoiser':'OIDN, explicitly CPU; GPU backends disabled','exposure':exposure,'background':'exact black','radianceQuantiles':np.quantile(hdr,[.5,.95,.99,.999,1]).tolist(),'meshSha256':hashlib.sha256(source.read_bytes()).hexdigest(),'imageSha256':hashlib.sha256(stem.with_suffix('.png').read_bytes()).hexdigest(),'emission':'Planck spectrum integrated against Mitsuba CIE functions, then traced in RGB','normalAov':'world geometric normal','lightSampling':{'mode':'luminance times emitter area','emitters':len(weights),'keyProbability':weights['key']/sum(weights.values())},'source':str(source),'matteCrust':bool(os.environ.get('LAVA_MATTE')),'rakingLight':bool(os.environ.get('LAVA_RAKING_LIGHT')),'geometryModel':'Separate molten foundation and cohesive crust shells','normalSmoothingIterations':int(os.environ.get('LAVA_NORMAL_SMOOTH','0')),'lightGain':float(os.environ.get('LAVA_LIGHT_GAIN','1')),'surfaceMix':bool(os.environ.get('LAVA_SURFACE_MIX')),'bumpTexture':os.environ.get('LAVA_BUMP_TEXTURE','basalt-micro.png'),'bumpScale':float(os.environ.get('LAVA_BUMP_SCALE','.00045')),'camera':{'eye':eye,'target':center,'fov':fov},'status':'candidate; direct visual review required'};stem.with_suffix('.json').write_text(json.dumps(receipt,indent=2));print('LAVA_IMAGE',json.dumps(receipt),flush=True)
 receipt.update(geometryModel='Authored overlapping lava lobes and compressed crust folds; separate closed hot core and crust',backLight=bool(os.environ.get('LAVA_BACK_LIGHT')),lightGain=float(os.environ.get('LAVA_LIGHT_GAIN','.07')),bumpTexture=os.environ.get('LAVA_BUMP_TEXTURE','basalt-vesicles.png'),bumpScale=float(os.environ.get('LAVA_BUMP_SCALE','.0014')),geometryLimits='Material still; no new fluid dynamics or animation acceptance is claimed')
 receipt['emission']='Continuous barycentric interpolation of per-vertex integrated Planck radiance; geometric emitter sampling independent of repeated UVs'
 if os.environ.get('LAVA_SOURCE_CAMERA'):
  receipt['geometryModel']='One connected implicit lava volume with an authored rupture, raised crust and carried fragments'
 if os.environ.get('LAVA_RUPTURE_MATERIAL'):
  receipt['surfaceModel']='Temperature-dependent rough dielectric melt and basalt; optical roughness is an authored approximation'
 if os.environ.get('LAVA_BASELINE_MATERIAL'):
  receipt['geometryModel']='Preserved rough-basalt mesh, with an authored thicker coarse volume and curved underside'
  receipt['temperatureModel']='Original authored temperature field preserved from the rough-basalt baseline; no new cooling solve is claimed for this mesh'
 elif source.stem.startswith('clinker'):
  receipt['geometryModel']='Connected molten volume carrying authored solid basalt rubble; no rigid-body/fluid coupling'
 if os.environ.get('LAVA_CRUST_VOLUME'):
  receipt['geometryModel']='Retained smooth coarse lava volume with independent closed basalt crust and molten core; authored fracture apertures'
  receipt['temperatureModel']='Natural 1D enthalpy cooling for the core surface, authored cold crust and underside temperatures; no coupled 3D energy solve'
 if os.environ.get('LAVA_VOLUME_PORE'):
  receipt['surfaceModel']='CPU 3D volume gradient pores; independent of UV stretch, filtered bump approximation'
 if source.stem.startswith('blocks'):
  receipt['geometryModel']='Solid packed basalt fracture blocks with individual thickness, tilt and relief over a smooth molten core; authored snapshot'
 if stage:
  receipt['stage']=stage
  receipt['geometryModel']='Matched authored material stage; fitted crust fragments, coherent melt, or separate conchoidal glass geometry'
  receipt['temperatureModel']='Authored stage temperatures; these stills are not a coupled cooling/crystallization simulation'
  if stage=='obsidian':receipt['surfaceModel']='Opaque optical limit of a thick absorbing glass specimen: GGX dielectric reflection, IOR 1.51, weak residual diffuse scattering. No transmitted light through this thick piece; transmissive comparison available as an optional preset.'
 if os.environ.get('LAVA_PLUME'):
  receipt['plumeSource']=os.environ['LAVA_PLUME']
  receipt['geometryModel']='One-way crust surface following of a conservative depth-averaged flow field'
  receipt['temperatureModel']='Conservative depth-averaged thermal transport and radiative/convective cooling; pre-existing crust cooling is authored'
  receipt['plumeModel']='MAC buoyant heat/moisture transport with approximate condensate optics'
  receipt['volumeRender']=volume_receipt or 'Mitsuba volpath'
 stem.with_suffix('.json').write_text(json.dumps(receipt,indent=2))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--frame',type=int,default=59);ap.add_argument('--spp',type=int,default=24);ap.add_argument('--width',type=int,default=640);ap.add_argument('--view',choices=['hero','detail'],default='hero');ap.add_argument('--revision',default='restored-clean');ap.add_argument('--normal-only',action='store_true');ap.add_argument('--no-micro',action='store_true');a=ap.parse_args();assert a.width<=1600 and a.spp<=128;main(a.frame,a.spp,a.width,a.view,a.revision,a.normal_only,a.no_micro)

