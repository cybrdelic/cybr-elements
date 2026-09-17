"""CPU surface of actual Newton particle positions; no damage-based cutting."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
from pathlib import Path
import argparse,json,hashlib
import numpy as np
from scipy.ndimage import map_coordinates
from skimage.measure import marching_cubes
from lava_mpm_surface import fields,reference_coordinates,image_surface
from lava_skin import normals


def build(path):
    s=dict(np.load(path));pitch=float(s['pitch']);dx=np.full(3,pitch*.45)
    s['volume']=np.full(len(s['x']),pitch**3)
    s['solid']=np.clip((1423.15-s['temperature'])/250,0,1)
    s['F']=s['particle_transform']
    determinants=np.linalg.det(s['F'])
    if np.any(determinants<=0):raise ValueError('Inverted material deformation; reconstruction rejected')
    sigma=np.full(3,pitch*.60)/dx
    lo,step,field=fields(s,dx,sigma,attribute_sigma=np.full(3,1.1))
    density=field['density'];target=float(s['volume'].sum());left=.03;right=min(.90,float(density.max())*.94)
    for _ in range(12):
        level=(left+right)/2
        v,f,_,_=marching_cubes(density,level,spacing=tuple(step));v+=lo
        volume=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)
        if volume<0:f=f[:,[0,2,1]];volume=-volume
        if volume>target:left=level
        else:right=level
    values={key:map_coordinates(field[key],((v-lo)/step).T,order=1,mode='nearest') for key in ['temperature','solid','damage']}
    rest,near=reference_coordinates(v,s,dx)
    center=(v.min(0)+v.max(0))*.5;size=float(np.max(np.ptp(v,axis=0)))
    eye=center+np.array([.45,-1.4,1.05])*size
    out=path.with_name(path.stem+'-surface.npz')
    np.savez_compressed(out,v=v,f=f,normal=normals(v,f),uv=rest[:,:2],rest=rest,**values,component=np.zeros(len(v),dtype='i4'),camera_eye=eye,camera_target=center,camera_fov=38.,time=s['time'])
    receipt=dict(source=str(path),sourceSha256=hashlib.sha256(path.read_bytes()).hexdigest(),time=float(s['time']),vertices=len(v),triangles=len(f),particleCount=len(s['x']),particleSpacingM=pitch,renderGridSpacingM=dx.tolist(),surfaceLevel=level,volumeRelativeError=abs(volume-target)/target,method='Volume-matched density surface. Identical kernel for all phases. No cracks painted, no damage-based carving, no authored fragments.',minimumMaterialJacobian=float(determinants.min()),maximumMaterialJacobian=float(determinants.max()))
    out.with_suffix('.json').write_text(json.dumps(receipt,indent=2));diagnostic=image_surface(out)
    print(json.dumps(dict(surface=str(out),diagnostic=str(diagnostic),triangles=len(f),volumeRelativeError=receipt['volumeRelativeError'])),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',type=Path);build(p.parse_args().path)
