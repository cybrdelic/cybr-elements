"""Density-guided exterior reconstruction with immutable measured cracks.

This is a bounded surface reconstruction, not particle displacement or a
fracture model. Crack walls and a surrounding guard band remain identical.
Global volume, local distortion and displacement are reported explicitly.
"""
import numpy as np
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
from lava_mpm_surface import fields
from lava_mpm_hybrid_surface import volumes


def reconstruct_outer(mesh,state,sample):
    sample=np.asarray(sample);original=mesh['v'];f=mesh['f'];cells=mesh['particle_cells'];target=float(state['volume'].sum())
    mobile=np.zeros(len(original),bool);mobile[np.unique(f[~mesh['crack_face']])]=True
    crack=mesh.get('crack_vertices',np.unique(f[mesh['crack_face']]))
    if len(crack):mobile&=cKDTree(original[crack]).query(original)[0]>1.25*sample.max()
    if not mobile.any():return mesh,dict(status='unchanged',mobileVertices=0,crackWallsUnchanged=True)
    dx=sample*.5;sigma=sample.max()*.5/dx;lo,dx,field=fields(state,dx,sigma,np.ones(3));density=field['density']
    left=.02;right=density.max()*.95
    for _ in range(10):
        level=(left+right)*.5;vv,ff,_,_=marching_cubes(density,level,spacing=tuple(dx));vv+=lo
        volume=abs(float(np.sum(vv[ff[:,0]]*np.cross(vv[ff[:,1]],vv[ff[:,2]]))/6))
        if volume>target:left=level
        else:right=level
    gradient=np.stack(np.gradient(density,*dx));candidate=original.copy()
    for _ in range(6):
        coords=((candidate-lo)/dx).T;value=map_coordinates(density,coords,order=1,mode='nearest')
        g=np.column_stack([map_coordinates(q,coords,order=1,mode='nearest') for q in gradient])
        delta=(level-value)[:,None]*g/np.maximum(np.sum(g*g,axis=1),1e-20)[:,None];delta[~mobile]=0
        delta/=np.maximum(1,np.linalg.norm(delta/sample,axis=1)/.2)[:,None];candidate+=delta
    change=candidate-original;change/=np.maximum(1,np.linalg.norm(change/sample,axis=1)/.65)[:,None]
    # The Jacobian transports the optical coordinates with this reconstruction.
    world=np.stack([original[f[:,1]]-original[f[:,0]],original[f[:,2]]-original[f[:,0]]],axis=2)
    rest=mesh['rest'];reference=np.stack([rest[f[:,1]]-rest[f[:,0]],rest[f[:,2]]-rest[f[:,0]]],axis=2)
    jac=reference@np.linalg.pinv(world,rcond=1e-10);area=np.linalg.norm(np.cross(world[:,:,0],world[:,:,1]),axis=1)
    pullback=np.zeros((len(original),3,3));weight=np.zeros(len(original))
    for corner in range(3):np.add.at(pullback,f[:,corner],jac*area[:,None,None]);np.add.at(weight,f[:,corner],area)
    pullback/=np.maximum(weight,1e-30)[:,None,None]
    # All cell faces are included in the volume derivative. Shared internal
    # faces cancel; duplicated crack walls retain their separate derivatives.
    from lava_mpm_material_surface import QUADS
    q=cells[:,QUADS].reshape(-1,4);vf=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]]
    for trial in range(12):
        v=original+change
        for _ in range(16):
            volume=volumes(v,cells);error=target-volume.sum()
            if abs(error)<target*1e-9:break
            g=np.zeros_like(v)
            for corner in range(3):np.add.at(g,vf[:,corner],np.cross(v[vf[:,(corner+1)%3]],v[vf[:,(corner+2)%3]])/6)
            g[~mobile]=0;denominator=float(np.sum(g*g))
            if denominator<1e-30:break
            v+=error/denominator*g
        volume=volumes(v,cells);relative=abs(volume-state['volume'])/state['volume']
        if np.min(volume)>0 and np.quantile(relative,.95)<.35 and np.max(np.linalg.norm((v-original)/sample,axis=1))<.85 and abs(volume.sum()-target)<target*1e-7:break
        change*=.5
    else:raise ValueError('Exterior reconstruction could not preserve volume/distortion bounds')
    assert np.array_equal(v[~mobile],original[~mobile]) and np.array_equal(v[crack],original[crack])
    out=dict(mesh);out['v']=v;out['cell_volume']=volume;out['rest']=rest+np.einsum('vij,vj->vi',pullback,v-original);out['uv']=out['rest'][:,:2]
    report=dict(status='pass',method='density-guided outer surface, measured crack walls and guard band fixed',mobileVertices=int(mobile.sum()),crackWallsUnchanged=True,maximumDisplacementM=float(np.linalg.norm(v-original,axis=1).max()),relativeVolumeDifference=float(abs(volume.sum()-target)/target),cellVolumeRelativeErrorP95=float(np.quantile(relative,.95)),minimumCellVolumeM3=float(volume.min()),
        limits='Bounded subcell reconstruction, not geometric refinement or a converged fracture surface. Local volume deviations are reported and do not relax the production gate.')
    return out,report
