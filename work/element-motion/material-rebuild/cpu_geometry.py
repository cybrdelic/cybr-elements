"""CPU geometry repairs shared by diagnostics and the render recipes."""
import numpy as np

def orient_faces(f):
 """Orient each connected component without assuming source winding."""
 f=np.asarray(f,dtype='i4').copy();edges={};adj=[[] for _ in range(len(f))]
 for i,tri in enumerate(f):
  for a,b in zip(tri,np.roll(tri,-1)):
   key=(min(int(a),int(b)),max(int(a),int(b)));direction=a<b
   if key in edges:
    j,other=edges.pop(key);same=bool(direction==other);adj[i].append((j,same));adj[j].append((i,same))
   else:edges[key]=(i,direction)
 flip=np.full(len(f),-1,dtype='i1')
 for root in range(len(f)):
  if flip[root]>=0:continue
  flip[root]=0;stack=[root]
  while stack:
   i=stack.pop()
   for j,same in adj[i]:
    target=int(flip[i])^int(same)
    if flip[j]<0:flip[j]=target;stack.append(j)
    else:assert flip[j]==target,'Nonorientable mesh'
 f[flip==1]=f[flip==1][:,[0,2,1]];return f

def seal_boundaries(v,f,uv=None):
 v=np.asarray(v);f=orient_faces(f);edges=np.concatenate([f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]);keys=np.sort(edges,axis=1);_,inverse,count=np.unique(keys,axis=0,return_inverse=True,return_counts=True);boundary=edges[count[inverse]==1]
 if not len(boundary):return v,f,uv,0
 nxt={int(a):int(b) for a,b in boundary};assert len(nxt)==len(boundary),'Branched boundary cannot be capped safely';caps=[];centers=[];tex=[];loops=0
 while nxt:
  first=next(iter(nxt));loop=[first];p=nxt.pop(first)
  while p!=first:
   loop.append(p);assert p in nxt,'Open boundary chain';p=nxt.pop(p)
  center=len(v)+len(centers);centers.append(v[loop].mean(0));loops+=1
  if uv is not None:tex.append(uv[loop].mean(0))
  for a,b in zip(loop,loop[1:]+loop[:1]):caps.append((b,a,center))
 v=np.concatenate([v,np.asarray(centers)]);f=np.concatenate([f,np.asarray(caps,dtype='i4')]);uv=np.concatenate([uv,np.asarray(tex)]) if uv is not None else None
 if np.sum(v[f[:,0]]*np.cross(v[f[:,1]],v[f[:,2]]))<0:f=f[:,[0,2,1]]
 return v,f,uv,loops

def packed_surface_cells(p,r,ids):
 """Stable-priority exclusion of coincident gas cells in a diagnostic frame.

 This fixes duplicate projected cells. It is a reconstruction, not temporal
 foam dynamics. The remaining connected microfoam represents unresolved gas.
 """
 from itertools import product
 priority=np.argsort((ids.astype('i8')*2654435761)%4294967291);keep=[];grid={};width=float(r.max()*2);cells=np.floor(p/width).astype(int);offsets=list(product([-1,0,1],repeat=3))
 for i in priority:
  key=cells[i];near=[]
  for offset in offsets:near.extend(grid.get(tuple(key+offset),[]))
  if near:
   near=np.asarray(near,dtype=int)
   if np.any(np.linalg.norm(p[near]-p[i],axis=1)<(r[near]+r[i])*.94):continue
  keep.append(i);grid.setdefault(tuple(key),[]).append(int(i))
 return np.asarray(keep,dtype=int)
