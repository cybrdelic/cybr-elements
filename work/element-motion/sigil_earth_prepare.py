"""Closed irregular fragments cut from the approved silhouettes, not open faces."""
from pathlib import Path
import numpy as np, json
from scipy.spatial import cKDTree
from scipy.ndimage import distance_transform_edt
from skimage.measure import marching_cubes
R=Path(__file__).resolve().parent;B=R/'sigil-v1'
for variant in ['01','02']:
 d=np.load(B/f'mark-{variant}.npz');mask=d['mask'];sdf=d['sdf'];arrival=d['arrival'];H,W=mask.shape;sx=11.4/(W-1);sz=6.4125/(H-1)
 rng=np.random.default_rng(811+int(variant));ys,xs=np.where(mask);candidates=np.column_stack((xs*sx-5.7,ys*sz+2.95-6.4125/2));seeds=[]
 for index in rng.permutation(len(candidates)):
  q=candidates[index];radius=.095+.14*rng.random()**.55
  if not seeds or min(np.linalg.norm(np.array(seeds)-q,axis=1))>radius:seeds.append(q)
  if len(seeds)>=320:break
 nearest=cKDTree(seeds).query(candidates,workers=2)[1];labels=np.full(mask.shape,-1,np.int32);labels[ys,xs]=nearest
 vertices=[];faces=[];centers=[];birth=[];volume=[];offsets=[0];faceOffsets=[0];depth=np.linspace(-.22,.22,36)
 for k in range(len(seeds)):
  py,px=np.where(labels==k)
  if len(py)<12:continue
  y0=max(0,py.min()-3);y1=min(H,py.max()+4);x0=max(0,px.min()-3);x1=min(W,px.max()+4)
  local=labels[y0:y1,x0:x1]==k;inside=(distance_transform_edt(local)-distance_transform_edt(~local))*sx-.005
  wx=np.arange(x0,x1)*sx-5.7;wz=np.arange(y0,y1)*sz+2.95-6.4125/2;zz,yy,xx=np.meshgrid(wz,depth,wx,indexing='ij')
  phase=k*1.813;thickness=.105+.022*np.sin(xx*10+phase)*np.cos(zz*12-phase)
  centerline=.018*np.sin(xx*8+zz*6+phase)
  slab=thickness-np.abs(yy-centerline)
  field=np.minimum(inside[:,None,:],slab)
  field+=.003*np.sin(xx*87+zz*63+phase)*np.cos(yy*83+zz*71)
  if field.max()<=0:continue
  v,f,n,_=marching_cubes(field.astype('f'),0,spacing=(sz,depth[1]-depth[0],sx));v=v[:,[2,1,0]];v+=np.array([wx[0],depth[0],wz[0]])
  # Restore outward winding after the coordinate permutation.
  f=f[:,[0,2,1]];center=v.mean(0);verts=(v-center).astype('f')
  vertices.append(verts);faces.append(f.astype('i'));centers.append(center);birth.append(float(np.median(arrival[labels==k])));volume.append(float(local.sum()*sx*sz*.21));offsets.append(offsets[-1]+len(v));faceOffsets.append(faceOffsets[-1]+len(f))
 np.savez_compressed(B/f'earth-{variant}-geometry.npz',verts=np.concatenate(vertices),faces=np.concatenate(faces),centers=centers,birth=birth,volume=volume,offsets=offsets,faceOffsets=faceOffsets)
 (B/f'earth-{variant}-geometry.json').write_text(json.dumps(dict(pieces=len(centers),vertices=offsets[-1],triangles=faceOffsets[-1],source='Closed Voronoi-style fragments of the exact mark; independent shaded fracture faces and true thickness'),indent=2),encoding='utf-8')
 print(variant,len(centers),'closed fragments',offsets[-1],'vertices',flush=True)
