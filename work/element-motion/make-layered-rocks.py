import json,numpy as np
from pathlib import Path
from scipy.spatial import ConvexHull
from skimage.measure import marching_cubes
R=Path('work/element-motion');data=json.loads((R/'earth-geometry.json').read_text());grid=np.linspace(-1.03,1.03,48,dtype=np.float32);x,y,z=np.meshgrid(grid,grid,grid,indexing='ij');points=np.stack((x,y,z),axis=-1);out=[]
for i,d in enumerate(data['pieces']):
 v=np.array(d['verts']);v-=v.mean(0);v/=np.linalg.norm(v,axis=1).max();hull=ConvexHull(v);sdf=np.full(x.shape,-10.,np.float32)
 for plane in hull.equations:sdf=np.maximum(sdf,np.einsum('...k,k->...',points,plane[:3])+plane[3])
 strata=(z+.18*x-.12*y)*25+i*.73;groove=.065*np.exp(-(np.sin(strata)/.17)**2);rough=.012*np.sin(x*17+np.sin(z*9))*np.cos(y*21)+.008*np.sin(y*35+z*27)
 field=sdf+.016+groove+rough;verts,faces,_,_=marching_cubes(field,0,spacing=(grid[1]-grid[0],)*3);verts+=grid[0];tri=verts[faces];normal=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);normal/=np.linalg.norm(normal,axis=1).clip(1e-8)[:,None];centers=tri.mean(1);band=np.sin((centers[:,2]+.18*centers[:,0]-.12*centers[:,1])*25+i*.73)
 mats=np.where(np.abs(normal[:,2])>.65,1,0);mats[np.abs(band)<.23]=2;mats[(band>.992)&(np.arange(len(mats))%4==0)]=3
 out.append({'verts':np.round(verts,6).tolist(),'faces':faces.tolist(),'materials':mats.tolist()})
(R/'layered-rocks.json').write_text(json.dumps(out,separators=(',',':')));print('Layered fracture surfaces:',len(out),'triangles:',sum(len(x['faces']) for x in out))
