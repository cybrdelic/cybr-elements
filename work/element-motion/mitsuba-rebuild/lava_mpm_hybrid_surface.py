"""Bounded liquid-only surface fairing on persistent material topology.

Crust, crack walls and melt/crust attachment vertices are immutable. Liquid
boundary vertices use a volume-constrained Taubin pass; no global rescaling.
This supports moderately deformed structured domains, not arbitrary remeshing.
"""
import numpy as np
from scipy.sparse import coo_matrix,diags
from lava_mpm_material_surface import QUADS
from lava_skin import normals


def volumes(v,cells):
    q=cells[:,QUADS];a=v[q[:,:,0]];b=v[q[:,:,1]];c=v[q[:,:,2]];d=v[q[:,:,3]]
    return (np.einsum('psi,psi->ps',a,np.cross(b,c))+np.einsum('psi,psi->ps',a,np.cross(c,d))).sum(1)/6


def fair_liquid(mesh,cold,sample,passes=4):
    v=mesh['v'].copy();f=mesh['f'];cells=mesh['particle_cells'];original=v.copy()
    fixed=np.ones(len(v),bool);fixed[np.unique(f)]=False
    fixed[np.unique(cells[np.asarray(cold,dtype=bool)])]=True
    fixed[np.unique(f[mesh['crack_face']])]=True
    fixed|=mesh['solid']>.05
    mobile=~fixed;baseline=volumes(v,cells);target=float(baseline.sum())
    if not mobile.any():return mesh,dict(method='liquid-only volume constrained fairing',mobileVertices=0,maximumDisplacementM=0.,crustUnchanged=True)
    edges=np.unique(np.sort(np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]),axis=1),axis=0)
    a,b=edges.T;length=np.linalg.norm(v[a]-v[b],axis=1);w=1/np.maximum(length,1e-30)
    adjacency=coo_matrix((np.r_[w,w],(np.r_[a,b],np.r_[b,a])),shape=(len(v),len(v))).tocsr()
    average=diags(1/np.maximum(np.asarray(adjacency.sum(1)).ravel(),1e-30))@adjacency
    for _ in range(passes):
        for amount in (.35,-.36):
            delta=amount*(average@v-v);delta[fixed]=0;v+=delta
    displacement=v-original;cap=.22*float(np.min(sample));size=np.linalg.norm(displacement,axis=1)
    displacement*=np.minimum(1,cap/np.maximum(size,1e-30))[:,None]
    for trial in range(10):
        candidate=original+displacement
        # Project onto the original volume using the boundary-volume gradient.
        for _ in range(12):
            value=float(volumes(candidate,cells).sum());error=target-value
            if abs(error)<target*1e-10:break
            grad=np.zeros_like(v)
            for corner in range(3):
                np.add.at(grad,f[:,corner],np.cross(candidate[f[:,(corner+1)%3]],candidate[f[:,(corner+2)%3]])/6)
            grad[fixed]=0;denom=float(np.sum(grad*grad))
            if denom<1e-30:raise ValueError('No liquid boundary volume degree of freedom')
            candidate+=error/denom*grad
        cell_volume=volumes(candidate,cells);relative=abs(cell_volume-baseline)/baseline
        if (cell_volume>0).all() and np.quantile(relative,.95)<.05 and np.max(np.linalg.norm(candidate-original,axis=1))<=cap*1.5:break
        displacement*=.5
    else:raise ValueError('Liquid fairing exceeded local volume/distortion bounds')
    if not np.array_equal(candidate[fixed],original[fixed]):raise AssertionError('Crust or crack geometry changed')
    out=dict(mesh);out['v']=candidate;out['normal']=normals(candidate,f);out['cell_volume']=cell_volume
    return out,dict(method='liquid-only volume constrained fairing',mobileVertices=int(mobile.sum()),crustUnchanged=True,
        maximumDisplacementM=float(np.linalg.norm(candidate-original,axis=1).max()),relativeVolumeError=float(abs(cell_volume.sum()-target)/target),
        cellVolumeChangeP95=float(np.quantile(relative,.95)),minimumCellVolumeM3=float(cell_volume.min()),
        topologyUnchanged=bool(np.array_equal(out['f'],f)),limit='Surface reconstruction only; no capillary force or subgrid basalt fracture is claimed.')
