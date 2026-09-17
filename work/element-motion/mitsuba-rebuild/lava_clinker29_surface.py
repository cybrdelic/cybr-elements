"""Surface real MPM/rigid caches. Basalt detail is rigid material-space detail."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
from pathlib import Path
import argparse,json
import numpy as np
from scipy.ndimage import gaussian_filter,map_coordinates
from scipy.spatial.transform import Rotation
from skimage.measure import marching_cubes
import trimesh
from scipy.spatial import cKDTree
from PIL import Image,ImageDraw
from lava_mpm_surface import fields
from lava_geometry_preview import raster
from lava_skin import normals

def build(path):
    s=dict(np.load(path));rocks=np.load(path.parent/'rocks.npz');pitch=float(s['pitch']);dx=np.full(3,pitch*.55)
    if 'surface_temperature' in s:s['temperature']=s['surface_temperature']
    s.update(volume=np.full(len(s['x']),pitch**3),solid=np.zeros(len(s['x'])),damage=np.zeros(len(s['x'])))
    lo,step,field=fields(s,dx,np.full(3,pitch*.70)/dx,attribute_sigma=np.full(3,1.2))
    density=field['density'];left=.015;right=.9;target=float(s['volume'].sum())
    for _ in range(12):
        level=(left+right)/2;v,f,_,_=marching_cubes(density,level,spacing=tuple(step));v+=lo
        volume=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)
        if volume<0:f=f[:,[0,2,1]];volume=-volume
        if volume>target:left=level
        else:right=level
    temp=map_coordinates(field['temperature'],((v-lo)/step).T,order=1,mode='nearest')
    distances,neighbors=cKDTree(s['x']).query(v,k=8);weights=1/np.maximum(distances,pitch*.1)**3;weights/=weights.sum(1)[:,None]
    material=v+np.sum(weights[:,:,None]*(s['rest'][neighbors]-s['x'][neighbors]),axis=1)
    verts=[v];faces=[f];temps=[temp];solids=[np.clip((1423.15-temp)/250,0,1)];rests=[material];ns=[normals(v,f)];component=[np.zeros(len(v),dtype='i4')]
    rng=np.random.default_rng(2991);raw=rng.normal(size=(96,96,96)).astype('f4')
    fine=gaussian_filter(raw,.7,mode='wrap');fine/=fine.std()
    broad=gaussian_filter(raw,2.4,mode='wrap');broad/=broad.std()
    for i,q in enumerate(s['body_q']):
        rv=rocks[f'v{i}'];rf=rocks[f'f{i}'];base=rv[:,2].min()
        rv,rf=trimesh.remesh.subdivide_to_size(rv,rf,max_edge=.004,max_iter=6)
        rn=normals(rv,rf)
        sample=(rv+rocks['initial_q'][i,:3])[:,::-1]*96/.085
        coarse=map_coordinates(broad,sample.T,order=1,mode='grid-wrap')
        grain=map_coordinates(fine,(sample*2.4).T,order=1,mode='grid-wrap')
        # Sub-millimeter roughness, attached to each rigid body's coordinates.
        displacement=np.clip(.00070*coarse+.00025*grain-.0006,-.0015,0.)
        rv=rv+rn*displacement[:,None];rn=normals(rv,rf)
        base_t=rocks['base_temperature'][i] if 'base_temperature' in rocks else 1420.
        rt=600+(base_t-600)*np.exp(-np.maximum(rv[:,2]-base,0)/.0085)
        # Initial conductive gradient is declared scene data, not a solved
        # heat-exchange claim. Subsequent exposed rock radiation is lumped.
        rt=(rt**-3+3*.94*5.670374419e-8*float(s['time'])/(2450*1200*.008))**(-1/3)
        transform=Rotation.from_quat(q[3:]).as_matrix();world=rv@transform.T+q[:3]
        offset=sum(len(a) for a in verts);verts.append(world);faces.append(rf+offset);temps.append(rt);solids.append(np.ones(len(rv)));rests.append(rv+rocks['initial_q'][i,:3]);ns.append(rn@transform.T);component.append(np.full(len(rv),i+1,dtype='i4'))
    v=np.concatenate(verts);f=np.concatenate(faces);center=np.array([.025,0,.033]);eye=center+np.array([.50,-1.40,1.12])*.40
    out=path.with_name(path.stem+'-surface.npz')
    np.savez_compressed(out,v=v,f=f,normal=np.concatenate(ns),temperature=np.concatenate(temps),solid=np.concatenate(solids),rest=np.concatenate(rests),damage=np.zeros(len(v)),component=np.concatenate(component),camera_eye=eye,camera_target=center,camera_fov=37.,time=s['time'])
    receipt=dict(source=str(path),vertices=len(v),triangles=len(f),fluidVolumeError=abs(volume-target)/target,rocks=len(s['body_q']),geometricDetailDisplacementM=.0015,limitations='Rigid initial fragments with bounded render roughness. Rock starting temperature is an authored conductive profile; rock-fluid heat exchange is not solved. Fluid temperature is simulated.')
    out.with_suffix('.json').write_text(json.dumps(receipt,indent=2));diagnostic(out);print(json.dumps(receipt))

def diagnostic(path):
    a=np.load(path);v=a['v'];f=a['f'];center=a['camera_target'];eye=a['camera_eye'];forward=center-eye;forward/=np.linalg.norm(forward)
    right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward);basis=np.array([right,up,forward])
    w=720;h=430;fl=w/(2*np.tan(np.deg2rad(37)/2));q=(v-center)@basis.T
    d=max(np.max(abs(q[:,0])*fl/(w*.43)-q[:,2]),np.max(abs(q[:,1])*fl/(h*.42)-q[:,2]));q[:,2]+=d
    p=np.c_[w/2+fl*q[:,0]/q[:,2],h/2-fl*q[:,1]/q[:,2],q[:,2]]
    n=a['normal'][f].mean(1);shade=.12+.88*np.maximum(0,n@np.array([-.4,-.4,.8246]));gray=np.tile([.4,.41,.43],(len(f),1))*shade[:,None]
    heat=np.clip((a['temperature'][f].mean(1)-900)/550,0,1);thermal=np.c_[heat,heat**3*.65,heat**8*.1]
    canvas=Image.new('RGB',(1440,490));draw=ImageDraw.Draw(canvas)
    for i,(label,color) in enumerate([('Geometry: MPM surface + moving initial fragments',gray),('Surface heat: subgrid melt / prepared basalt profile',thermal)]):
        pixels=raster(p,f,(np.clip(color,0,1)**(1/2.2)*255).astype('u1'),w,h);canvas.paste(Image.fromarray(pixels),(i*w,30));draw.text((i*w+16,8),label,fill='#b8b8b8')
    draw.text((16,474),f"Mechanical time {float(a['time']):.3f} s. Diagnostic colors. This does not claim emergent fracture.",fill='#999')
    canvas.save(path.with_name(path.stem+'-diagnostic.png'))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);build(p.parse_args().path)
