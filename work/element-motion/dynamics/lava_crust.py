from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from cache_io import fluid_particles
out=R/'cache/lava/crust';out.mkdir(exist_ok=True);previous=np.empty((0,3));oldq=previous.copy()
for f in range(120):
    mesh=np.load(R/'surface/lava'/f'{f:04}.npz');v=mesh['v'];fa=mesh['f'];state=np.load(R/'cache/lava'/f'{f:04}.npz');phase=state['phase'];q,qv=fluid_particles(f,True);ids=np.arange(len(q))
    if len(v):
        normal=np.zeros_like(v);fn=np.cross(v[fa[:,1]]-v[fa[:,0]],v[fa[:,2]]-v[fa[:,0]])
        for j in range(3):np.add.at(normal,fa[:,j],fn)
        normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-8);dd,ii=cKDTree(v).query(q);projected=v[ii].copy();nn=normal[ii]
        old=min(len(previous),len(q))
        if old:projected[:old]=projected[:old]*.78+(previous+q[:old]-oldq)*.22
        previous=projected.copy();oldq=q.copy();projected+=nn*.010
        skin=np.clip((.98-state['heat'])/.12,0,1)
        ok=(ids%3==0)&(dd<.09)&(skin>.08)&(np.linalg.norm(nn,axis=1)>.5)
        # Crust plates grow as a local fraction freezes; all positions follow
        # persistent carrier identities and the moving surface.
        r=(.050+.042*(ids*.717%1)**2)*np.sqrt(skin)
        tangent=np.cross(nn,np.tile([0,0,1],(len(nn),1)));bad=np.linalg.norm(tangent,axis=1)<.01;tangent[bad]=np.cross(nn[bad],[1,0,0]);tangent/=np.maximum(np.linalg.norm(tangent,axis=1)[:,None],1e-8);zz=np.cross(tangent,nn);matrix=np.stack([tangent,nn,zz],axis=-1);rotation=Rotation.from_matrix(matrix[ok]).as_euler('XYZ')
        np.savez_compressed(out/f'{f:04}.npz',p=projected[ok].astype('f4'),r=r[ok].astype('f4'),rotation=rotation.astype('f4'))
    else:np.savez_compressed(out/f'{f:04}.npz',p=np.empty((0,3),'f4'),r=np.empty(0,'f4'),rotation=np.empty((0,3),'f4'))
print('Projected persistent crust: 120 frames')
