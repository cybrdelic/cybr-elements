"""Density reconstruction with a fixed particle kernel and temporal identity.
Metal uses the APIC deformation gradient on a persistent rest-space sheet.
"""
from pathlib import Path
import sys,json
import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree
from skimage.measure import marching_cubes
R=Path(__file__).resolve().parent
sys.path.insert(0,str(R.parent));from shared_motion import pose

def density_surface(p,spacing=.022,radius=.027,level=.21):
    if len(p)<10:return np.zeros((0,3),'f4'),np.zeros((0,3),'i4')
    low=np.floor((p.min(0)-radius*3)/spacing)*spacing;high=p.max(0)+radius*3
    dims=np.ceil((high-low)/spacing).astype(int)+1
    assert np.prod(dims)<45000000,('surface allocation',dims.tolist())
    grid=np.zeros(dims,dtype='f4');q=(p-low)/spacing;base=np.floor(q).astype(int);frac=q-base
    for i in [0,1]:
        for j in [0,1]:
            for k in [0,1]:
                idx=base+[i,j,k];w=(frac[:,0] if i else 1-frac[:,0])*(frac[:,1] if j else 1-frac[:,1])*(frac[:,2] if k else 1-frac[:,2]);np.add.at(grid,(idx[:,0],idx[:,1],idx[:,2]),w)
    grid=gaussian_filter(grid,radius/spacing,mode='constant')
    if grid.max()<level:return np.zeros((0,3),'f4'),np.zeros((0,3),'i4')
    v,f,_,_=marching_cubes(grid,level=level,spacing=(spacing,)*3);return (v+low).astype('f4'),f.astype('i4')

def metal_surface(folder,frames):
    static=np.load(folder/'static.npz');rest=static['rest'];birth=static['birth'];tree=cKDTree(rest)
    ts=np.linspace(.08,1.68,700);width=np.linspace(-.23,.23,15)
    vertices=[];vb=[]
    for t in ts:
        p,d,_,_=pose(float(t))
        for side in [-1,1]:
            for w in width:
                vertices.append([p[0]-d[1]*w,side*.020+.035*np.sin(t*12)*np.cos(w*8),p[1]+d[0]*w]);vb.append(t)
    vertices=np.array(vertices);vb=np.array(vb);dist,idx=tree.query(vertices,k=6);weights=1/np.maximum(dist,.003)**3;weights/=weights.sum(1)[:,None]
    offsets=vertices[:,None]-rest[idx];faces=[];strip=30
    for i in range(len(ts)-1):
        for side in range(2):
            for j in range(14):
                a=i*strip+side*15+j;b=a+strip;faces.append([a,b,b+1,a+1] if side==0 else [a,a+1,b+1,b])
        for j in [0,14]:
            a=i*strip+j;b=a+strip;faces.append([a,a+15,b+15,b])
    faces=np.array(faces);facebirth=vb[faces].max(1)
    out=R/'surface/metal';out.mkdir(parents=True,exist_ok=True)
    for f in frames:
        a=np.load(folder/f'{f:04}.npz');F=a['F'].astype('f4');p=a['p'];v=np.sum((p[idx]+np.einsum('nkij,nkj->nki',F[idx],offsets))*weights[:,:,None],axis=1)
        alive=facebirth<=float(a['t'])-.025
        np.savez_compressed(out/f'{f:04}.npz',v=v.astype('f4'),f=faces[alive])
    print('metal surfaces',len(frames),flush=True)

if __name__=='__main__':
    k=sys.argv[1];folder=R/'cache'/k;frames=[int(x.stem) for x in sorted(folder.glob('[0-9]*.npz'))]
    if k=='metal':metal_surface(folder,frames)
    else:
        birth=np.load(folder/'static.npz')['birth'];out=R/'surface'/k;out.mkdir(parents=True,exist_ok=True)
        for f in frames:
            a=np.load(folder/f'{f:04}.npz');v,fa=density_surface(a['p'][birth<=float(a['t'])]);np.savez_compressed(out/f'{f:04}.npz',v=v,f=fa)
            if f%30==0:print(k,f,len(v),flush=True)
