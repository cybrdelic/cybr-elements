"""CPU or CUDA Mitsuba proof using a unique triangle atlas and native plugins.

The atlas bakes solved temperature and material-coordinate optical pores.
It does not generate cracks, alter the simulation surface, or fake emission.
Unique UVs avoid the overlapping parameterization of the old planar UVs.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import argparse,hashlib,json,time
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter,map_coordinates
from PIL import Image
import mitsuba as mi
import drjit as dr
mi.set_variant('scalar_rgb');dr.set_thread_count(2)
ROOT=Path(__file__).resolve().parent/'lava-focus'/'mpm'
from lava_emission_io import ply
from lava_radiation import radiance
from cpu_oidn import denoise


def atlas(a,folder,tile=14):
    f=a['f'];count=len(f);side=int(np.ceil(np.sqrt(count)));size=side*tile
    if size>4096:raise ValueError('Atlas exceeds bounded CPU proof size')
    emission=np.zeros((size,size,3),dtype='f4');height=np.zeros((size,size),dtype='f4')
    uv=np.empty((count,3,2))
    q=np.arange(tile)+.5;yy,xx=np.meshgrid(q,q,indexing='ij')
    b=np.stack([1-(xx-2)/(tile-4)-(yy-2)/(tile-4),(xx-2)/(tile-4),(yy-2)/(tile-4)],axis=-1)
    # Extension outside a triangle is only a bilinear-filter gutter. These
    # texels have no surface preimage and cannot emit into the physical scene.
    b=np.maximum(b,0);b/=b.sum(-1,keepdims=True)
    rng=np.random.default_rng(79832);raw=rng.normal(size=(64,64,64)).astype('f4')
    broad=gaussian_filter(raw,2.2,mode='wrap');broad/=broad.std()
    fine=gaussian_filter(raw,.7,mode='wrap');fine/=fine.std()
    pores=np.clip(.64-.12*np.maximum(-broad-.4,0)**1.45+.020*fine,.02,.98).astype('f4')
    lo=np.floor(float(a['temperature'].min()))-1;hi=np.ceil(float(a['temperature'].max()))+1
    table_t=np.arange(lo,hi+1);table=np.array([radiance(t) for t in table_t])*.94
    for begin in range(0,count,128):
        end=min(begin+128,count);face=f[begin:end]
        t=np.einsum('hwk,nk->nhw',b,a['temperature'][face])
        rgb=np.stack([np.interp(t,table_t,table[:,c]) for c in range(3)],axis=-1).astype('f4')
        rest=np.einsum('hwk,nkj->nhwj',b,a['rest'][face])
        p=map_coordinates(pores,np.moveaxis(rest[...,::-1]*64/.008-.5,-1,0),order=1,mode='grid-wrap')
        for j,i in enumerate(range(begin,end)):
            y=(i//side)*tile;x=(i%side)*tile
            emission[y:y+tile,x:x+tile]=rgb[j];height[y:y+tile,x:x+tile]=p[j]
            uv[i]=(np.array([[2,2],[tile-2,2],[2,tile-2]])+[x,y])/size
    mi.Bitmap(emission).write(str(folder/'emission.exr'))
    mi.Bitmap(height).write(str(folder/'pores.exr'))
    index=np.arange(count*3).reshape(-1,3);flat=f.ravel()
    path=folder/'surface.ply'
    ply(path,a['v'][flat],index,a['normal'][flat],uv.reshape(-1,2),np.zeros((len(flat),3)),{'solid':a['solid'][flat]})
    return path,dict(size=[size,size],triangles=count,pixelsPerTriangleTile=tile,method='Unique per-triangle atlas; interpolated solved temperature evaluated through Planck radiance. Optical pores sampled in advected reference coordinates. Native Mitsuba bitmap emitters and bump maps.')


def tonemap(x):
    x=np.maximum(x,0);x=np.clip(x*(2.51*x+.03)/(x*(2.43*x+.59)+.14),0,1)
    return np.where(x<=.0031308,12.92*x,1.055*x**(1/2.4)-.055)


def render(name,frame='state',width=640,spp=16,exposure=6.,wall=60.,device='cpu'):
    if device not in ('cpu','cuda'):raise ValueError('Unknown rendering device')
    start=time.monotonic();source=ROOT/name/(frame+'-surface.npz');a=dict(np.load(source))
    folder=source.parent/('native-optical-proof' if device=='cpu' else 'cuda-optical-proof');folder.mkdir(exist_ok=True)
    path,baking=atlas(a,folder)
    mi.set_variant('scalar_rgb' if device=='cpu' else 'cuda_ad_rgb')
    T=mi.ScalarTransform4f;v=a['v'];target=a['camera_target'];eye=a['camera_eye'];fov=float(a['camera_fov']);height=round(width*.625)
    forward=(target-eye)/np.linalg.norm(target-eye);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    q=(v-target)@np.array([right,up,forward]).T;tangent=np.tan(np.deg2rad(fov)*.5)
    distance=max(np.max(abs(q[:,0])/(tangent*.86)-q[:,2]),np.max(abs(q[:,1])/(tangent*height/width*.84)-q[:,2]));eye=target-forward*distance
    def dielectric(alpha):return dict(type='roughplastic',distribution='ggx',alpha=alpha,int_ior=1.57,nonlinear=True,diffuse_reflectance=dict(type='rgb',value=[.019,.017,.015]))
    scene=dict(type='scene',integrator=dict(type='aov',aovs='albedo:albedo,normal:geo_normal,depth:depth',beauty=dict(type='path',max_depth=10,rr_depth=5)),
        sensor=dict(type='perspective',to_world=T().look_at(origin=eye.tolist(),target=target.tolist(),up=[0,0,1]),fov=fov,
            sampler=dict(type='independent',sample_count=spp),film=dict(type='hdrfilm',width=width,height=height,pixel_format='rgba',rfilter=dict(type='tent'))))
    extent=float(np.max(np.ptp(v,axis=0)));scale=extent/.020
    for label,relative,size,color in [('key',[-.065,-.025,.14],[.055,.014],[3.,3.2,3.5]),('rim',[.06,.07,.075],[.03,.012],[1.2,1.15,1.1])]:
        location=target+np.array(relative)*scale
        scene[label]=dict(type='rectangle',to_world=T().look_at(origin=location.tolist(),target=target.tolist(),up=[0,0,1])@T().scale([size[0]*scale,size[1]*scale,1]),emitter=dict(type='area',radiance=dict(type='rgb',value=color)))
    scene['ground']=dict(type='rectangle',to_world=T().scale(max(.4,extent*4)),bsdf=dict(type='diffuse',reflectance=0.))
    material=dict(type='blendbsdf',weight=dict(type='mesh_attribute',name='vertex_solid'),
        bsdf_0=dielectric(.055),bsdf_1=dict(type='bumpmap',scale=.00006,texture=dict(type='bitmap',filename=str(folder/'pores.exr'),raw=True,wrap_mode='clamp'),material=dielectric(.48)))
    scene['lava']=dict(type='ply',filename=str(path),bsdf=material,
        emitter=dict(type='area',radiance=dict(type='bitmap',filename=str(folder/'emission.exr'),raw=True,wrap_mode='clamp')))
    scene=mi.load_dict(scene);done=0;parts={};render_start=time.monotonic()
    while done<spp:
        count=min(4,spp-done);mi.render(scene,spp=count,seed=1926+done)
        current={k:np.array(b) for k,b in scene.sensors()[0].film().bitmap(raw=False).split()}
        parts={k:(parts[k]*done+v*count)/(done+count) if k in parts else v for k,v in current.items()};done+=count
        print(json.dumps(dict(samples=done,seconds=time.monotonic()-start)),flush=True)
        if time.monotonic()-start>wall:break
    raw=parts['beauty'][...,:3];clean=denoise(raw,parts['albedo'],parts['normal']);clean[np.max(raw,axis=-1)==0]=0
    image_path=folder/(frame+'.png');Image.fromarray((tonemap(clean*exposure)*255).astype('u1')).save(image_path)
    Image.fromarray((tonemap(raw*exposure)*255).astype('u1')).save(folder/(frame+'-raw.png'))
    mi.Bitmap(np.ascontiguousarray(raw)).write(str(folder/(frame+'.exr')))
    np.savez_compressed(folder/(frame+'-aov.npz'),color=raw,albedo=parts['albedo'],normal=parts['normal'],depth=parts['depth'])
    report=dict(status='unreviewed optical proof',device='CPU' if device=='cpu' else 'CUDA GPU',variant=mi.variant(),denoiser='OIDN CPU',width=width,height=height,samples=done,seconds=time.monotonic()-start,renderAndDenoiseSeconds=time.monotonic()-render_start,atlas=baking,
        source=str(source),sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),image=str(image_path),imageSha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
        background='Exact black; no environment, bloom or overlays',limitations='Nominal basalt/melt BRDF and unresolved optical pores. Baking has finite texture resolution. Geometry and physics acceptance are independent; this is not a production approval.')
    (folder/(frame+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--frame',default='state');p.add_argument('--width',type=int,default=640);p.add_argument('--spp',type=int,default=16);p.add_argument('--wall',type=float,default=60.);p.add_argument('--device',choices=['cpu','cuda'],default='cpu');a=p.parse_args()
    if a.width>1600 or a.spp>128:raise ValueError('CPU proof bounds exceeded')
    render(a.name,a.frame,a.width,a.spp,wall=a.wall,device=a.device)
