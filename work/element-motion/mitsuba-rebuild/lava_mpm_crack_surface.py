"""CPU material-domain surface preserving local broken-bond boundaries.

No geometric aperture multiplier, invented fracture map, or painted hot seams.
This is a coarse Lagrangian material-domain reconstruction, not extra physical
resolution. Kernel surfaces are retained separately for comparison.
"""
import argparse,json,hashlib
from pathlib import Path
from itertools import product
import numpy as np
from scipy.sparse import coo_matrix
from lava_mpm import ROOT
from lava_mpm_fracture import _support_components
from lava_skin import normals
from lava_mpm_surface import image_surface


def geometry(s,spacing):
    n=len(s['x']); rest=s['rest']; x=s['x']; cold=s['bond_frozen']
    lattice=np.rint((rest-rest.min(0))/spacing).astype(int)
    if np.max(abs((rest-rest.min(0))/spacing-lattice))>1e-5:raise ValueError('This reconstruction requires the cached regular initial material quadrature')
    corners=np.array(list(product((0,1),repeat=3)),dtype=int)
    coord=lattice[:,None,:]+corners[None,:,:]
    unique,ci=np.unique(coord.reshape(-1,3),axis=0,return_inverse=True)
    ci=ci.reshape(n,8);order=np.argsort(ci.ravel(),kind='stable');sid=ci.ravel()[order]
    starts=np.r_[0,np.flatnonzero(np.diff(sid))+1,len(sid)]
    intact=s['bond_edges'][~s['bond_broken']];a,b=intact.T
    adj=coo_matrix((np.ones(2*len(a)),(np.r_[a,b],np.r_[b,a])),shape=(n,n)).tocsr()
    roots=_support_components(sid,(order//8).astype('int64'),starts,adj.indptr,adj.indices,cold,n)
    tags=np.empty(n*8,dtype=int);tags[order]=roots
    key=np.c_[ci.ravel(),tags];_,weld=np.unique(key,axis=0,return_inverse=True);weld=weld.reshape(n,8)
    # Corotated, volume-matched material domains. Using a fluid's accumulated
    # shear F as a display cell makes long needles; fitting its full rest-to-
    # current map can invert after mixing. Domain shape is an explicit
    # corotated approximation; translation, rotation and volume are cached
    # simulation state. Shear shape below one particle is not reconstructed.
    U,_,Vh=np.linalg.svd(s['F']);rotation=U@Vh
    if np.any(np.linalg.det(rotation)<=0):raise ValueError('Inverted material orientation')
    gradients=rotation*np.cbrt(s['volume']/spacing**3)[:,None,None]
    offset=(corners-.5)*spacing
    prediction=x[:,None,:]+np.einsum('pij,kj->pki',gradients,offset)
    count=np.bincount(weld.ravel());nv=len(count)
    v=np.array([np.bincount(weld.ravel(),weights=prediction[:,:,i].ravel(),minlength=nv)/count for i in range(3)]).T
    props={name:np.bincount(weld.ravel(),weights=np.repeat(s[name],8),minlength=nv)/count for name in ('temperature','solid','damage')}
    faces=np.array([[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]])
    quads=weld[:,faces].reshape(-1,4);_,indices,counts=np.unique(np.sort(quads,axis=1),axis=0,return_index=True,return_counts=True)
    if counts.max()>2:raise ValueError('Non-manifold domain welding')
    q=quads[indices[counts==1]];f=np.r_[q[:,[0,1,2]],q[:,[0,2,3]]]
    keep,inv=np.unique(f,return_inverse=True);v=v[keep];f=inv.reshape(-1,3);props={k:p[keep] for k,p in props.items()}
    volume=float(np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))/6)
    target=float(s['volume'].sum());error=abs(volume-target)/target
    return dict(v=v,f=f,normal=normals(v,f),uv=v[:,:2],rest=v.copy(),component=props['solid'],**props),dict(solverVolumeM3=target,reconstructedVolumeM3=volume,relativeVolumeError=error,brokenBonds=int(s['bond_broken'].sum()),vertices=len(v),triangles=len(f),numericalGate=error<.01,visualStatus='experimental; rejected on the inspected coarse cache because of boxy terraces and grid-shaped holes; do not use for final rendering')


def main(name,frame):
    folder=ROOT/name;source=folder/(frame+'.npz');s=dict(np.load(source));meta=json.loads((folder/'state.json').read_text());mesh,receipt=geometry(s,meta['spacing'])
    center=(s['x'].min(0)+s['x'].max(0))*.5;size=float(np.max(np.ptp(s['x'],axis=0)))
    mesh.update(camera_eye=center+np.array([.65,-1.55,1.25])*size,camera_target=center,camera_fov=38.,time=s['time'])
    out=folder/(frame+'-domains.npz');np.savez_compressed(out,**mesh)
    receipt.update(source=str(source),sourceSha256=hashlib.sha256(source.read_bytes()).hexdigest(),time=float(s['time']),method='Corotated material-domain reconstruction with local fracture connectivity; no aperture scaling',limits='Particle-domain shear shape is approximated by rotation and volume. Coarse quadrature remains visible. Neighbor-domain welding changes reconstructed volume; thermal values are interpolated from actual particles. This is not a finer simulation.')
    out.with_suffix('.json').write_text(json.dumps(receipt,indent=2));image=image_surface(out)
    print(json.dumps(dict(surface=str(out),image=str(image),**receipt)))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',required=True);p.add_argument('--frame',default='state');a=p.parse_args();main(a.name,a.frame)
