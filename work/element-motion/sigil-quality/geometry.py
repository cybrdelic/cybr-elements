"""Reconstruct the approved full-size source, not the 512-pixel simulation mask."""
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
from PIL import Image
from scipy.ndimage import label,distance_transform_edt,gaussian_filter,map_coordinates
from skimage.measure import marching_cubes
from scipy.sparse import coo_matrix
from scipy.sparse.linalg import cg
R=Path(__file__).resolve().parent;ROOT=R.parents[2]
V=sys.argv[1] if len(sys.argv)>1 else '01'
artpath=ROOT/'outputs/cybrdelic-type/exploration-v6/cybrdelic-brandmark-refined.png'
art=np.asarray(Image.open(artpath).convert('L'));top,bottom={'01':(95,535),'02':(585,1005)}[V]
mask=art[top:bottom,20:1005]<100;labs,n=label(mask)
for j in range(1,n+1):
    z,x=np.where(labs==j)
    if len(x)<35 or (x.mean()<85 and z.mean()<130):mask[labs==j]=False
z,x=np.where(mask);mask=mask[z.min():z.max()+1,x.min():x.max()+1]
scale=8.05/mask.shape[1];dx=10.5/1535;dz=5.8/863
xx,zz=np.meshgrid(np.linspace(-5.25,5.25,1536),np.linspace(0,5.8,864))
uv=np.array([mask.shape[0]-(zz-.43)/scale,xx/scale+mask.shape[1]/2])
coverage=map_coordinates(mask.astype('f4'),uv,order=1,mode='constant',cval=0)
sdf=distance_transform_edt(coverage>.5,sampling=(dz,dx))-distance_transform_edt(coverage<=.5,sampling=(dz,dx))
sdf=gaussian_filter(sdf,.85).astype('f4')
# A nearest-edge distance extrusion creates medial-axis creases, visible as
# balloon seams. Solve the pressure membrane over the pinned silhouette instead.
inside=sdf>0;iz,ix=np.where(inside);count=len(iz);index=np.full(inside.shape,-1,'i4');index[iz,ix]=np.arange(count)
rows=[np.arange(count)];cols=[np.arange(count)];values=[np.full(count,2/dx**2+2/dz**2)]
for oz,ox,weight in [(0,1,1/dx**2),(0,-1,1/dx**2),(1,0,1/dz**2),(-1,0,1/dz**2)]:
    other=index[iz+oz,ix+ox];valid=other>=0;rows.append(np.flatnonzero(valid));cols.append(other[valid]);values.append(np.full(valid.sum(),-weight))
A=coo_matrix((np.concatenate(values),(np.concatenate(rows),np.concatenate(cols))),shape=(count,count)).tocsr()
solution,info=cg(A,np.ones(count),rtol=2e-7,maxiter=3000)
assert info==0,('Pressure membrane did not converge',info)
residual=float(np.linalg.norm(A@solution-1)/np.sqrt(count));pressure=-np.maximum(-sdf,0)**2
pressure[iz,ix]=solution;pressure=gaussian_filter(pressure,.45).astype('f4')
yy=np.linspace(-.38,.38,113,dtype='f4');volume=pressure[:,None,:]-yy[None,:,None]**2/2
v,faces,_,_=marching_cubes(volume,0,spacing=(dz,float(yy[1]-yy[0]),dx));del volume
v=v[:,[2,1,0]];v[:,0]-=5.25;v[:,1]-=.38
signed=np.einsum('ij,ij->i',v[faces[:,0]],np.cross(v[faces[:,1]],v[faces[:,2]])).sum()/6
if signed<0:faces=faces[:,[0,2,1]]
normal=np.zeros_like(v);fn=np.cross(v[faces[:,1]]-v[faces[:,0]],v[faces[:,2]]-v[faces[:,0]])
for j in range(3):np.add.at(normal,faces[:,j],fn)
normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-8)
old=np.load(R.parent/'sigils'/f'source-{V}.npz');born=map_coordinates(old['arrival'],[v[:,2]/5.8*319,(v[:,0]+5.25)/10.5*511],order=1,mode='nearest')
assert np.isfinite(v).all() and abs(signed)>0
np.savez_compressed(R/f'geometry-{V}.npz',v=v.astype('f4'),faces=faces.astype('i4'),normal=normal.astype('f4'),born=born.astype('f4'))
report={'variant':V,'artworkSha256':hashlib.sha256(artpath.read_bytes()).hexdigest(),'vertices':len(v),'faces':len(faces),'closedVolume':abs(float(signed)),'spacing':[dx,float(yy[1]-yy[0]),dz],'source':'Unchanged approved full-size study artwork','crossSection':'Poisson pressure membrane with fixed silhouette boundary','relativeResidual':residual}
(R/f'geometry-{V}.json').write_text(json.dumps(report,indent=2));print(report)
