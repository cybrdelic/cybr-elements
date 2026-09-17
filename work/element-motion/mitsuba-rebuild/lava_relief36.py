"""Bounded basalt render relief on the existing MPM / rigid motion cache.

The coarse collision hull and its motion are unchanged. Vesicles and rough
fracture relief are subcollision geometry, not a claim of simulated cracking.
No atlases: native vertex attributes keep this proof within the disk budget.
"""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import argparse,json,time,shutil
from pathlib import Path
import numpy as np
from scipy.ndimage import gaussian_filter,map_coordinates
from scipy.spatial import ConvexHull,cKDTree
from scipy.spatial.transform import Rotation
from skimage.measure import marching_cubes
from lava_mpm_surface import fields
from lava_skin import normals
os.environ['CUDA_VISIBLE_DEVICES']='0'
import mitsuba as mi
import drjit as dr
mi.set_variant('scalar_rgb');dr.set_thread_count(2)
from lava_radiation import radiance
from lava_display34 import display
from cpu_oidn import denoise
from PIL import Image


def write_mesh(path,v,f,n,rgb,solid):
    names=['x','y','z','nx','ny','nz','heat_r','heat_g','heat_b','solid_0']
    header='ply\nformat binary_little_endian 1.0\nelement vertex '+str(len(v))+'\n'+''.join('property float '+name+'\n' for name in names)+'element face '+str(len(f))+'\nproperty list uchar int vertex_indices\nend_header\n'
    with path.open('wb') as out:
        out.write(header.encode())
        for first in range(0,len(v),65536):
            sl=slice(first,first+65536)
            np.ascontiguousarray(np.c_[v[sl],n[sl],rgb[sl],solid[sl]],dtype='<f4').tofile(out)
        for first in range(0,len(f),65536):
            fs=f[first:first+65536];data=np.empty(len(fs),dtype=[('size','u1'),('index','<i4',(3,))]);data['size']=3;data['index']=fs;data.tofile(out)


def register_emitter():
    # Shape sampling is required: this mesh has no surface UV atlas.
    # The sampled point is recovered on the shape, with visibility handled
    # by the path integrator. There is no RGB texture or fake light source.
    class VertexArea(mi.Emitter):
        def __init__(self,props):
            super().__init__(props);self.m_flags=mi.EmitterFlags.Surface
        def set_scene(self,scene):self.scene=scene
        def eval(self,si,active=True):
            active=active & si.is_valid() & (mi.Frame3f.cos_theta(si.wi)>0)
            value=self.get_shape().eval_attribute_3('vertex_heat_color',si,active)
            return dr.select(active,value,0.)
        def _interaction(self,it,ds,active):
            active=active & (ds.pdf>0) & (dr.dot(ds.d,ds.n)<0)
            ray=it.spawn_ray(ds.d)
            ray.d=dr.normalize(ds.p-ray.o)
            si=self.scene.ray_intersect(ray,active=active)
            active=active & si.is_valid() & (si.shape==mi.ShapePtr(self.get_shape())) & (dr.norm(si.p-ds.p)<1e-5)
            return si,active
        def sample_direction(self,it,sample,active=True):
            ds=self.get_shape().sample_direction(it,sample,active);ds.emitter=mi.EmitterPtr(self)
            si,active=self._interaction(it,ds,active)
            return ds,dr.select(active,self.eval(si,active)/dr.maximum(ds.pdf,1e-30),0.)
        def pdf_direction(self,it,ds,active=True):
            return dr.select(active & (dr.dot(ds.d,ds.n)<0),self.get_shape().pdf_direction(it,ds,active),0.)
        def eval_direction(self,it,ds,active=True):
            si,active=self._interaction(it,ds,active);return self.eval(si,active)
        def bbox(self):return self.get_shape().bbox()
        def to_string(self):return 'VertexArea[shape-sampled Planck emission]'
    mi.register_emitter('vertex_area36',lambda props:VertexArea(props))


def relief(rv,rf,seed,step=.00065):
    rng=np.random.default_rng(seed);hull=ConvexHull(rv)
    lo=rv.min(0)-.001;hi=rv.max(0)+.001
    shape=np.ceil((hi-lo)/step).astype(int)+1
    pts=np.stack(np.meshgrid(*(lo[i]+np.arange(shape[i])*step for i in range(3)),indexing='ij'),-1).reshape(-1,3)
    sdf=np.full(len(pts),-1e3)
    for eq in hull.equations:sdf=np.maximum(sdf,pts@eq[:3]+eq[3])
    # Three physical scales of chipped relief. Carved into the collision
    # envelope so that this does not create interpenetrating silhouettes.
    noise=rng.normal(size=tuple(shape)).astype('f4')
    relief=np.zeros(shape,dtype='f4')
    for sigma,amp in [(5.,.0011),(2.,.00055),(.7,.00016)]:
        n=gaussian_filter(noise,sigma);n/=n.std();relief+=amp*n
    sdf+=np.clip(.001+relief.ravel(),0,.0032)
    # Closed pores opening at the surface; radii are skewed toward small
    # cavities. Their positions remain fixed in each body's material frame.
    centers=rng.uniform(lo,hi,(max(120,int(np.prod(hi-lo)/1e-7)),3))
    dist=np.full(len(centers),-1e3)
    for eq in hull.equations:dist=np.maximum(dist,centers@eq[:3]+eq[3])
    centers=centers[(dist>-.004)&(dist<.0001)]
    if len(centers):
        radii=np.minimum(.0017,.00035*(1+rng.pareto(2.2,len(centers))))
        dd,ii=cKDTree(centers).query(pts,k=min(4,len(centers)))
        if dd.ndim==1:dd=dd[:,None];ii=ii[:,None]
        sdf=np.maximum(sdf,np.max(radii[ii]-dd,axis=1))
    v,f,_,_=marching_cubes(sdf.reshape(shape),0,spacing=(step,)*3,gradient_direction='ascent');v+=lo
    # Marching cubes winding is checked, independent of library convention.
    if np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))<0:f=f[:,[0,2,1]]
    return v,f


def surface(path,folder):
    s=dict(np.load(path));rocks=np.load(path.parent/'rocks.npz');pitch=float(s['pitch'])
    s['temperature']=s.get('surface_temperature',s['temperature'])
    s.update(volume=np.full(len(s['x']),pitch**3),solid=np.zeros(len(s['x'])),damage=np.zeros(len(s['x'])))
    lo,step,field=fields(s,np.full(3,pitch*.55),np.full(3,.70/.55),attribute_sigma=np.full(3,1.2))
    density=field['density'];left=.015;right=.9;target=float(s['volume'].sum())
    for _ in range(12):
        level=(left+right)/2;v,f,_,_=marching_cubes(density,level,spacing=tuple(step));v+=lo
        volume=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)
        if volume<0:f=f[:,[0,2,1]];volume=-volume
        if volume>target:left=level
        else:right=level
    temp=map_coordinates(field['temperature'],((v-lo)/step).T,order=1,mode='nearest')
    del field,density
    verts=[v];faces=[f];temps=[temp];ns=[normals(v,f)];solid=[np.clip((1423.15-temp)/250,0,1)]
    offsets=[0];count=len(v)
    for i,q in enumerate(s['body_q']):
        rv=rocks[f'v{i}'];base=rv[:,2].min();rv,rf=relief(rv,rocks[f'f{i}'],36000+i)
        rn=normals(rv,rf);base_t=rocks['base_temperature'][i] if 'base_temperature' in rocks else 1420.
        rt=600+(base_t-600)*np.exp(-np.maximum(rv[:,2]-base,0)/.0085)
        rt=(rt**-3+3*.94*5.670374419e-8*float(s['time'])/(2450*1200*.008))**(-1/3)
        rot=Rotation.from_quat(q[3:]).as_matrix();verts.append(rv@rot.T+q[:3]);faces.append(rf+count)
        temps.append(rt);ns.append(rn@rot.T);solid.append(np.ones(len(rv)));count+=len(rv)
    v=np.concatenate(verts);f=np.concatenate(faces);t=np.concatenate(temps);n=np.concatenate(ns);sol=np.concatenate(solid)
    table_t=np.arange(np.floor(t.min())-1,np.ceil(t.max())+2);table=np.array([radiance(tt) for tt in table_t])*.94
    rgb=np.stack([np.interp(t,table_t,table[:,j]) for j in range(3)],axis=-1)
    out=folder/'surface.ply';pending=folder/'surface.pending.ply'
    estimated=len(v)*48+len(f)*13+30*1024**2
    if shutil.disk_usage(folder).free<estimated:raise RuntimeError('Insufficient disk for mesh and render; leave source caches intact')
    write_mesh(pending,v,f,n,rgb,sol);pending.replace(out)
    report=dict(vertices=len(v),triangles=len(f),fluidVolumeError=abs(volume-target)/target,rocks=len(s['body_q']),time=float(s['time']),source=str(path),reliefMaximumM=.0032,limitations='Cached MPM / XPBD initial fragments. Render relief is authored in material coordinates; it is not simulated new fracture. Original prepared basalt temperature profile retained; rock-fluid heat exchange remains unsolved.')
    (folder/'geometry.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
    return out


def render(path,folder,width=800,spp=32):
    start=time.monotonic();mi.set_variant('cuda_ad_rgb');register_emitter();T=mi.ScalarTransform4f
    center=np.array([.055,0,.045]);eye=np.array([.13,-.28,.18]);height=round(width*.625)
    material=dict(type='blendbsdf',weight=dict(type='mesh_attribute',name='vertex_solid'),
        bsdf_0=dict(type='roughplastic',distribution='ggx',alpha=.09,int_ior=1.57,nonlinear=True,diffuse_reflectance=dict(type='rgb',value=[.01,.008,.006])),
        bsdf_1=dict(type='roughplastic',distribution='ggx',alpha=.5,int_ior=1.55,nonlinear=True,diffuse_reflectance=dict(type='rgb',value=[.022,.020,.018])))
    scene=dict(type='scene',integrator=dict(type='aov',aovs='albedo:albedo,normal:geo_normal',beauty=dict(type='path',max_depth=10,rr_depth=5)),
        sensor=dict(type='perspective',to_world=T().look_at(origin=eye.tolist(),target=center.tolist(),up=[0,0,1]),fov=40.,sampler=dict(type='independent',sample_count=spp),film=dict(type='hdrfilm',width=width,height=height,pixel_format='rgba',rfilter=dict(type='tent'))),
        lava=dict(type='ply',filename=str(path),bsdf=material,emitter=dict(type='vertex_area36')),
        ground=dict(type='rectangle',to_world=T().translate([0,0,-.006])@T().scale(2),bsdf=dict(type='diffuse',reflectance=0.)))
    scene['key']=dict(type='rectangle',to_world=T().look_at(origin=[-.15,-.3,.6],target=center.tolist(),up=[0,0,1])@T().scale([.25,.10,1]),emitter=dict(type='area',radiance=dict(type='rgb',value=[.11,.12,.14])))
    scene=mi.load_dict(scene);parts={};done=0
    for emitter in scene.emitters():
        if hasattr(emitter,'set_scene'):emitter.set_scene(scene)
    while done<spp:
        count=min(8,spp-done);mi.render(scene,spp=count,seed=3631+done)
        current={k:np.array(b) for k,b in scene.sensors()[0].film().bitmap(raw=False).split()}
        parts={k:(parts[k]*done+v*count)/(done+count) if k in parts else v for k,v in current.items()};done+=count
        print(json.dumps(dict(samples=done,seconds=time.monotonic()-start)),flush=True)
    raw=parts['beauty'][...,:3];clean=denoise(raw,parts['albedo'],parts['normal']);clean[np.max(raw,axis=-1)==0]=0
    # Write small reviewable images before the optional linear cache.
    for e in [100.,200.,320.]:Image.fromarray((display(clean,e)*255).astype('u1')).save(folder/f'beauty-{e:g}.png')
    np.savez_compressed(folder/'linear.npz',raw=raw,clean=clean)
    report=dict(image=str(folder/'beauty-200.png'),seconds=time.monotonic()-start,width=width,height=height,spp=spp,renderer='Mitsuba CUDA path tracing with geometry-sampled vertex Planck emission',denoiser='OIDN CPU',blackBackground=True,bloom=False,geometry=str(path),status='Material study, not a completed coupled fracture simulation')
    (folder/'render.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('--width',type=int,default=800);p.add_argument('--spp',type=int,default=32);a=p.parse_args()
    folder=a.source.parent/(a.source.stem+'-relief36');folder.mkdir(exist_ok=True)
    mesh=folder/'surface.ply'
    if not mesh.exists():mesh=surface(a.source,folder)
    render(mesh,folder,a.width,a.spp)
