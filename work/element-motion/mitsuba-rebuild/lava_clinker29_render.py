"""Native GPU Mitsuba render of cached two-phase geometry on black."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import argparse,json,time
from pathlib import Path
import numpy as np
from PIL import Image
import mitsuba as mi
import drjit as dr
mi.set_variant('scalar_rgb');dr.set_thread_count(2)
from lava_mpm_native_optics26 import atlas,tonemap
from cpu_oidn import denoise

def render(path,width,spp):
    start=time.monotonic();a=dict(np.load(path));folder=path.parent/(path.stem+'-optics');folder.mkdir(exist_ok=True)
    tile=min(10,max(4,int(4090/np.ceil(np.sqrt(len(a['f']))))))
    if tile<=4:raise ValueError('Split this mesh atlas before rendering')
    mesh,info=atlas(a,folder,tile=tile)
    mi.set_variant('cuda_ad_rgb');T=mi.ScalarTransform4f
    center=a['camera_target'];eye=a['camera_eye'];height=round(width*.625)
    forward=(center-eye)/np.linalg.norm(center-eye);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    # Frame the principal lava front. All debris remains in the scene;
    # outlying small chips do not drive the camera farther away.
    core=a['v'][a['component']<=33]
    q=(core-center)@np.array([right,up,forward]).T;tangent=np.tan(np.deg2rad(37)*.5)
    distance=max(np.max(abs(q[:,0])/(tangent*.9)-q[:,2]),np.max(abs(q[:,1])/(tangent*height/width*.85)-q[:,2]));eye=center-forward*distance
    material=dict(type='blendbsdf',weight=dict(type='mesh_attribute',name='vertex_solid'),
      bsdf_0=dict(type='roughplastic',distribution='ggx',alpha=.12,int_ior=1.57,nonlinear=True,diffuse_reflectance=dict(type='rgb',value=[.012,.009,.007])),
      bsdf_1=dict(type='bumpmap',scale=.00055,texture=dict(type='bitmap',filename=str(folder/'pores.exr'),raw=True,wrap_mode='clamp'),material=dict(type='roughplastic',distribution='ggx',alpha=.78,int_ior=1.55,nonlinear=True,diffuse_reflectance=dict(type='rgb',value=[.012,.011,.010]))))
    scene=dict(type='scene',integrator=dict(type='aov',aovs='albedo:albedo,normal:geo_normal',beauty=dict(type='path',max_depth=10,rr_depth=5)),
      sensor=dict(type='perspective',to_world=T().look_at(origin=eye.tolist(),target=center.tolist(),up=[0,0,1]),fov=37.,sampler=dict(type='independent',sample_count=spp),film=dict(type='hdrfilm',width=width,height=height,pixel_format='rgba',rfilter=dict(type='tent'))),
      lava=dict(type='ply',filename=str(mesh),bsdf=material,emitter=dict(type='area',radiance=dict(type='bitmap',filename=str(folder/'emission.exr'),raw=True,wrap_mode='clamp'))),
      ground=dict(type='rectangle',to_world=T().translate([0,0,-.006])@T().scale(2),bsdf=dict(type='diffuse',reflectance=0.)))
    scene['key']=dict(type='rectangle',to_world=T().look_at(origin=[-.15,-.3,.6],target=center.tolist(),up=[0,0,1])@T().scale([.25,.10,1]),emitter=dict(type='area',radiance=dict(type='rgb',value=[3.,2.9,2.8])))
    scene=mi.load_dict(scene);parts={};done=0
    while done<spp:
        count=min(8,spp-done);mi.render(scene,spp=count,seed=2931+done)
        current={k:np.array(b) for k,b in scene.sensors()[0].film().bitmap(raw=False).split()}
        parts={k:(parts[k]*done+v*count)/(done+count) if k in parts else v for k,v in current.items()};done+=count
        print(json.dumps(dict(samples=done,seconds=time.monotonic()-start)),flush=True)
    raw=parts['beauty'][...,:3];clean=denoise(raw,parts['albedo'],parts['normal']);clean[np.max(raw,axis=-1)==0]=0
    np.savez_compressed(folder/'linear.npz',raw=raw,clean=clean)
    for exposure in [3.,6.,10.]:Image.fromarray((tonemap(clean*exposure)*255).astype('u1')).save(folder/f'beauty-{exposure:g}.png')
    report=dict(image=str(folder/'beauty-6.png'),width=width,spp=spp,seconds=time.monotonic()-start,atlas=info,renderer='Mitsuba CUDA path tracing; CPU OIDN',source=str(path),background='black, no environment',status='unreviewed')
    (folder/'receipt.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);p.add_argument('--width',type=int,default=960);p.add_argument('--spp',type=int,default=48);a=p.parse_args();render(a.path,a.width,a.spp)
