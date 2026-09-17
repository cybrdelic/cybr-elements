"""Bounded Mitsuba CPU optical proof from an actual saved MPM surface.

No imported stage geometry, painted temperature, glow overlay or mesh cuts.
Roughness and unresolved pores are declared optical approximations.
"""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import argparse,json,time,hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import mitsuba as mi
import drjit as dr
mi.set_variant('scalar_rgb');dr.set_thread_count(2)
from lava_mpm import ROOT,Material
from lava_emission_io import ply,LavaEmitter
from lava_radiation import radiance
from lava_material_texture import material_attributes,texture as material_texture
from cpu_oidn import denoise


def tonemap(x):
    x=np.maximum(x,0);x=np.clip(x*(2.51*x+.03)/(x*(2.43*x+.59)+.14),0,1)
    return np.where(x<=.0031308,12.92*x,1.055*x**(1/2.4)-.055)


def main(name,frame,width,spp,exposure,light=1.,clean_optics=False,diagnostic=False):
    start=time.time();folder=ROOT/name;source=folder/(frame+'-surface.npz');a=np.load(source)
    from lava_mpm_render_gate import inspect_surface
    gate=inspect_surface(source)
    if gate['status']!='pass' and not diagnostic:
        raise ValueError(('Lava geometry is not ready for a production render',gate['checks']))
    v=a['v'];f=a['f'];normal=a['normal'];temp=a['temperature'];uv=a['uv'];face_t=temp[f].mean(1)
    output=folder/'optical-proof';output.mkdir(exist_ok=True);geo=output/(frame+'-geometry');geo.mkdir(exist_ok=True)
    transform=mi.ScalarTransform4f
    target=a['camera_target'];eye=a['camera_eye'];fov=float(a['camera_fov']);height=round(width*.625)
    # Fit actual bounds with a fixed margin; old hard-coded framing cropped
    # the inlet and much of the cooled sample.
    forward=(target-eye)/np.linalg.norm(target-eye);right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
    projected=(v-target)@np.array([right,up,forward]).T;tangent=np.tan(np.deg2rad(fov)*.5)
    distance=max(np.max(abs(projected[:,0])/(tangent*.86)-projected[:,2]),np.max(abs(projected[:,1])/(tangent*height/width*.84)-projected[:,2]))
    eye=target-forward*distance
    scene=dict(type='scene',integrator=dict(type='aov',aovs='albedo:albedo,normal:geo_normal,depth:depth',beauty=dict(type='path',max_depth=10,rr_depth=5)),
               sensor=dict(type='perspective',to_world=transform().look_at(origin=eye.tolist(),target=target.tolist(),up=[0,0,1]),fov=fov,
                           sampler=dict(type='independent',sample_count=spp),film=dict(type='hdrfilm',width=width,height=height,pixel_format='rgba',rfilter=dict(type='tent'))))
    for label,relative,size,color in [('key',[-.065,-.025,.14],[.055,.014],[3.,3.2,3.5]),('rim',[.06,.07,.075],[.03,.012],[1.2,1.15,1.1])]:
        color=(np.asarray(color)*light).tolist();location=target+relative;area=4*size[0]*size[1];weight=float(np.dot(color,[.2126,.7152,.0722])*area)
        scene[label]=dict(type='rectangle',to_world=transform().look_at(origin=location.tolist(),target=target.tolist(),up=[0,0,1])@transform().scale([*size,1]),emitter=dict(type='area',radiance=dict(type='rgb',value=color),sampling_weight=weight))
    scene['ground']=dict(type='rectangle',to_world=transform().scale(.4),bsdf=dict(type='diffuse',reflectance=0.))
    temperatures=np.arange(750.,1550.1,1.);colors=np.array([radiance(t) for t in temperatures])*.94
    color=np.array([np.interp(temp,temperatures,colors[:,c]) for c in range(3)]).T.astype('f4')
    groups=np.floor(face_t/30).astype(int);m=Material();texture=None if clean_optics else material_texture()
    attributes={'solid':a['solid']}
    if not clean_optics:
        if 'rest' not in a:raise ValueError('Material-attached optical detail requires saved reference coordinates')
        attributes.update(material_attributes(v,a['rest'],f))
    for group in np.unique(groups):
        select=groups==group;t=float(face_t[select].mean());solid=float(m.solid(t))
        path=geo/f'{group}.ply';ply(path,v,f[select],normal,uv,color,attributes)
        def phase_material(alpha):return dict(type='roughplastic',distribution='ggx',alpha=alpha,int_ior=1.57,nonlinear=True,diffuse_reflectance=dict(type='rgb',value=[.019,.017,.015]))
        rock=phase_material(.48)
        if not clean_optics:rock=dict(type='bumpmap',scale=.00006,texture=texture,material=rock)
        # Temperature bins affect emitter sampling only. Material transitions
        # remain continuous across triangles and bin boundaries.
        material={'type':'blendbsdf','weight':{'type':'mesh_attribute','name':'vertex_solid'},'bsdf_0':phase_material(.055),'bsdf_1':rock}
        shape=dict(type='ply',filename=str(path),bsdf=material)
        rgb=np.array(radiance(t))*.94
        if rgb.max()>1e-8:
            tri=v[f[select]];area=np.linalg.norm(np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]),axis=1).sum()*.5
            shape['emitter']=dict(type='lava_vertex_area',sampling_weight=max(1e-12,float(np.dot(rgb,[.2126,.7152,.0722])*area)))
        scene[f'material_{group}']=shape
    scene=mi.load_dict(scene)
    for emitter in scene.emitters():
        if isinstance(emitter,LavaEmitter):emitter.set_scene(scene)
    done=0;parts={};render_start=time.time()
    while done<spp:
        count=min(2,spp-done);mi.render(scene,spp=count,seed=2026+done)
        current={key:np.array(bitmap) for key,bitmap in scene.sensors()[0].film().bitmap(raw=False).split()}
        parts={key:(parts[key]*done+value*count)/(done+count) if key in parts else value for key,value in current.items()};done+=count
        raw=parts['beauty'][...,:3]
        np.savez_compressed(output/(frame+'-checkpoint.npz'),color=raw,albedo=parts['albedo'],normal=parts['normal'],depth=parts['depth'],spp=done)
        Image.fromarray((tonemap(raw*exposure)*255).astype('uint8')).save(output/(frame+'-raw.png'))
        print(json.dumps(dict(samples=done,elapsed=round(time.time()-render_start,2),size=[width,height])),flush=True)
        if time.time()-start>115:break
    raw=parts['beauty'][...,:3];clean=denoise(raw,parts['albedo'],parts['normal'])
    background=np.max(raw,axis=-1)==0;clean[background]=0
    path=output/(frame+'.png');Image.fromarray((tonemap(clean*exposure)*255).astype('uint8')).save(path)
    mi.Bitmap(np.ascontiguousarray(raw)).write(str(output/(frame+'.exr')))
    receipt=dict(status='unreviewed CPU material proof; not a final shot',renderer='Mitsuba '+mi.__version__,variant=mi.variant(),device='CPU',threads=2,
                 renderGate=gate,diagnosticOverride=bool(diagnostic),
                 width=width,height=height,samples=done,exposure=exposure,lightMultiplier=light,seconds=time.time()-start,source=str(source),sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),image=str(path),
                 geometry=json.loads(source.with_suffix('.json').read_text()).get('method','Kernel reconstruction of the actual MPM volume'),temperature='Interpolated simulated enthalpy temperatures; Planck radiance with grey emissivity 0.94',
                 optics=('Continuous blend of nominal molten and solid rough dielectrics using solved vertex solid fraction; no pore bump or authored crack texture.' if clean_optics else 'Nominal rough dielectric basalt and melt. 60 micrometre optical bump is attached to advected material coordinates. It does not add geometric cracks.'),background='Exact black; black absorbing ground; no environment or bloom overlay',
                 limits='This optical frame inherits the stated simulation/render-gate limitations. It does not independently validate temporal or spatial convergence, motion, gas, or photorealism.')
    (output/(frame+'.json')).write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--frame',default='state');p.add_argument('--width',type=int,default=512);p.add_argument('--spp',type=int,default=8);p.add_argument('--exposure',type=float,default=6.);p.add_argument('--light',type=float,default=1.);p.add_argument('--clean-optics',action='store_true');p.add_argument('--diagnostic',action='store_true');a=p.parse_args();assert a.width<=1600 and a.spp<=128;main(a.name,a.frame,a.width,a.spp,a.exposure,a.light,a.clean_optics,a.diagnostic)
