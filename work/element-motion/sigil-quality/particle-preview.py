"""Early surface diagnostic from actual cached FLIP particles, before final meshing.

Uses a density isosurface; this is explicitly not the final Mantaflow mesh.
"""
from pathlib import Path
import gzip,struct,json,sys
import numpy as np
from scipy.ndimage import gaussian_filter
from skimage.measure import marching_cubes
R=Path(__file__).resolve().parent
frame=int(sys.argv[1]) if len(sys.argv)>1 else 20
folder=R/'native-liquid-01-v2'
b=gzip.decompress((folder/f'cache/data/pp_{frame:04}.uni').read_bytes())
n,nx,ny,nz,_,stride=struct.unpack_from('<6i',b,4)
assert stride==16 and b[:4]==b'PB02'
a=np.frombuffer(b,dtype=np.dtype([('p','<f4',(3,)),('flag','<i4')]),offset=len(b)-n*16)
p=a['p'][a['flag']==0].copy()-.5
base=np.floor(p).astype('i4');fraction=p-base
density=np.zeros((nx,ny,nz),dtype='f4')
for dx in [0,1]:
 for dy in [0,1]:
  for dz in [0,1]:
   ix=base+np.array([dx,dy,dz]);weight=np.prod(np.where(np.array([dx,dy,dz]),fraction,1-fraction),axis=1)
   valid=((ix>=0)&(ix<np.array([nx,ny,nz]))).all(axis=1)
   np.add.at(density,tuple(ix[valid].T),weight[valid])
density=gaussian_filter(density,.7)
v,faces,normal,_=marching_cubes(density,1.6)
v=(v+.5)*10.8/384+np.array([-5.4,-.9,-1])
np.savez_compressed(folder/f'particle-surface-{frame:04}.npz',v=v.astype('f4'),faces=faces.astype('i4'),normal=normal.astype('f4'),born=np.zeros(len(v),dtype='f4'))
print(json.dumps({'frame':frame,'activeParticles':len(p),'vertices':len(v),'faces':len(faces),'status':'Early density-surface diagnostic from FLIP particle cache; final meshing remains pending'}))
