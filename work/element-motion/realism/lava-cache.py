from pathlib import Path
import gzip,struct,json,time
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;P=R.parent;cache=R.parents[2]/'outputs/cybrdelic-type/elements/motion/water/cache/viscous';extent=np.array(json.loads((cache/'manifest.json').read_text(encoding='utf-8'))['config']['extent']);out=R/'lava-geometry';out.mkdir(exist_ok=True)
birth=np.full(180000,10000);seen=0;randoms=np.zeros((20000,7));start=time.time()
for pid in range(len(randoms)):
 rng=np.random.default_rng(pid+755);randoms[pid]=[rng.uniform(.032,.078),rng.uniform(0,6.28),*rng.uniform(.6,1.2,5)]
def coords(p):return np.column_stack((p[:,0]/.4-5.25,(p[:,2]-.9)/.4,p[:,1]/.4))
def project(points,triangles,faceNormals):
 ids=cKDTree(triangles.mean(1)).query(points,k=8)[1];ts=triangles[ids];q=points[:,None,:];a=ts[:,:,0];b=ts[:,:,1];c=ts[:,:,2];e0=b-a;e1=c-a;n=np.cross(e0,e1);pr=q-n*(np.sum((q-a)*n,axis=-1)/np.maximum(1e-14,np.sum(n*n,axis=-1)))[:,:,None];d00=np.sum(e0*e0,-1);d01=np.sum(e0*e1,-1);d11=np.sum(e1*e1,-1);d20=np.sum((pr-a)*e0,-1);d21=np.sum((pr-a)*e1,-1);den=np.maximum(1e-14,d00*d11-d01*d01);u=(d11*d20-d01*d21)/den;v=(d00*d21-d01*d20)/den;valid=(u>=0)&(v>=0)&(u+v<=1);candidates=[pr]
 for p0,p1 in [(a,b),(b,c),(c,a)]:
  e=p1-p0;t=np.clip(np.sum((q-p0)*e,-1)/np.maximum(1e-14,np.sum(e*e,-1)),0,1);candidates.append(p0+e*t[:,:,None])
 cp=np.stack(candidates,axis=2);dist=np.sum((cp-q[:,:,None,:])**2,-1);dist[:,:,0]=np.where(valid,dist[:,:,0],np.inf);choice=dist.reshape(len(points),-1).argmin(1);rows=np.arange(len(points));best=cp.reshape(len(points),-1,3)[rows,choice];normal=faceNormals[ids[rows,choice//4]];normal/=np.maximum(1e-12,np.linalg.norm(normal,axis=1)[:,None]);return np.sqrt(dist.reshape(len(points),-1)[rows,choice]),best,normal

for f in range(120):
 rawp=gzip.decompress((P/'viscous-cache'/f'{f:04}.gz').read_bytes());count=len(rawp)//24;pp=coords(np.frombuffer(rawp,'<f4',count*3).reshape(-1,3));birth[seen:count]=f;seen=count
 raw=gzip.decompress((cache/f'{f:04}.mesh.gz').read_bytes());nv,nf,nd=struct.unpack_from('<III',raw,4);off=32;v=coords(np.frombuffer(raw,'<u2',nv*3,off).reshape(-1,3)/65535*extent);off+=nv*13;faces=np.frombuffer(raw,'<u4',nf*3,off).reshape(-1,3)[:,[0,2,1]];off+=nf*12;drops=coords(np.frombuffer(raw,'<u2',nd*3,off).reshape(-1,3)/65535*extent)
 if not nv or not count:
  np.savez_compressed(out/f'{f:04}.npz',vertices=np.empty((0,3)),faces=np.empty((0,5),int),heat=np.zeros(nv+nd*12),strain=np.zeros(nv+nd*12));continue
 thermal=np.load(R/'lava-fields'/f'{f:04}.npz');nearest=cKDTree(pp).query(np.vstack([v,drops]))[1];heat=np.r_[thermal['heat'][nearest[:nv]],np.repeat(thermal['heat'][nearest[nv:]],12)];strain=np.r_[thermal['strain'][nearest[:nv]],np.repeat(thermal['strain'][nearest[nv:]],12)]
 normals=np.zeros_like(v);tri=v[faces];fn=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);np.add.at(normals,faces[:,0],fn);np.add.at(normals,faces[:,1],fn);np.add.at(normals,faces[:,2],fn);normals/=np.maximum(1e-10,np.linalg.norm(normals,axis=1)[:,None])
 ids=np.arange(0,count,2);dist,projected,normal=project(pp[ids],tri,fn);age=(f-birth[ids])/30;ok=(age>=.12)&(dist<.06)&(thermal['strain'][ids]<.65);ids=ids[ok];age=age[ok];projected=projected[ok];normal=normal[ok];u=np.cross(normal,[0,1,0]);bad=np.linalg.norm(u,axis=1)<.01;u[bad]=np.cross(normal[bad],[1,0,0]);u/=np.maximum(1e-8,np.linalg.norm(u,axis=1)[:,None]);w=np.cross(normal,u);par=randoms[ids];radius=par[:,0]*np.minimum(1,age/.25)*(1-.55*thermal['strain'][ids]);angles=np.arange(5)[None]*np.pi*2/5+par[:,1,None];rads=radius[:,None]*par[:,2:];center=projected+normal*.004;ring=center[:,None]+rads[:,:,None]*(np.cos(angles)[:,:,None]*u[:,None]+np.sin(angles)[:,:,None]*w[:,None]);vv=np.concatenate([ring,ring+normal[:,None]*.004],axis=1).reshape(-1,3)
 # Quads and pentagons are flattened into triangle fans for compact storage.
 pattern=[[4,3,2],[4,2,1],[4,1,0],[5,6,7],[5,7,8],[5,8,9]]
 for j in range(5):a=j;b=(j+1)%5;pattern.extend([[a,b,b+5],[a,b+5,a+5]])
 ff=(np.array(pattern)[None]+np.arange(len(ids))[:,None,None]*10).reshape(-1,3);np.savez_compressed(out/f'{f:04}.npz',vertices=vv.astype('f4'),faces=ff.astype('i4'),heat=heat.astype('f4'),strain=strain.astype('f4'))
print('120 cached crust meshes',round(time.time()-start,1),'seconds')
p=R/'lava.py';s=p.read_text(encoding='utf-8')
if '# Persistent FLIP' not in s:raise SystemExit(0)
a=s.index(" if KIND=='lava':\n  # Persistent FLIP");b=s.index(" if KIND=='foam':",a)
s=s[:a]+''' if KIND=='lava':
  if crustObj:
   old=crustObj.data;bpy.data.objects.remove(crustObj,do_unlink=True);bpy.data.meshes.remove(old)
  cached=np.load(R/'realism/lava-geometry'/f'{f:04}.npz');assert len(cached['heat'])==len(me.vertices)
  at=me.attributes.new('Temperature','FLOAT','POINT');at.data.foreach_set('value',cached['heat']);at=me.attributes.new('Stretch','FLOAT','POINT');at.data.foreach_set('value',cached['strain'])
  cm=bpy.data.meshes.new('Advected basalt skin');cm.from_pydata(cached['vertices'].tolist(),[],cached['faces'].tolist());cm.materials.append(crust);crustObj=bpy.data.objects.new('Cooling basalt skin',cm);bpy.context.collection.objects.link(crustObj)
''' +s[b:];p.write_text(s,encoding='utf-8')
print('Lava renderer consumes the cached geometry and thermal fields')
