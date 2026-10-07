"""Fuel/collision proxy from the SAME full mesh used for display."""
from pathlib import Path
import numpy as np,json
from scipy.ndimage import distance_transform_edt,binary_fill_holes
P=Path(__file__).resolve().parents[2]/'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/objects'
d=np.load(P/'forest-tree/source-mesh.npz');v=d['vertices'];f=d['faces'];H=3/64
fields=[]
for leaf in [False,True]:
    take=v[:,8]>7.5 if leaf else v[:,8]<7.5
    mask=np.zeros((64,64,64),bool)
    # Source bark is already densely tessellated; all triangle edge midpoints
    # and centroids additionally cover the thin laminae and larger root faces.
    faces=f[take[f[:,0]]]
    for start in range(0,len(faces),50000):
        t=v[faces[start:start+50000],:3]
        points=np.concatenate([t[:,0],t[:,1],t[:,2],t.mean(1),(t[:,0]+t[:,1])*.5,(t[:,1]+t[:,2])*.5,(t[:,2]+t[:,0])*.5])
        q=np.clip(((points+1.5)/H).astype(int),0,63)
        mask[q[:,2],q[:,1],q[:,0]]=True
    if not leaf:mask=binary_fill_holes(mask)
    distance=distance_transform_edt(~mask)*H-H*.5
    if not leaf:distance[mask]=-distance_transform_edt(mask)[mask]*H
    fields.append(distance)
wood,leaf=fields;foliage=(leaf<wood)&(wood>H)
a=np.zeros((64,64,64,4),np.float32)
a[...,0]=np.where(foliage,np.maximum(leaf,.025),wood)
a[...,1]=np.where(foliage,.22,1.5)
a[...,2]=np.where(foliage,1.8,.65)
a[...,3]=np.where(foliage,8,1)
a.astype('<f2').tofile(P/'cybr-tree.rgba16.bin')
print(json.dumps({'woodVoxels':int((wood<0).sum()),'leafVoxels':int((leaf<0).sum()),'bytes':a.size*2}))
