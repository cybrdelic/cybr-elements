from pathlib import Path
R=Path(__file__).resolve().parent;p=R/'lava-cache.py';s=p.read_text(encoding='utf-8')
function='''def project(points,triangles,faceNormals):
 ids=cKDTree(triangles.mean(1)).query(points,k=8)[1];ts=triangles[ids];q=points[:,None,:];a=ts[:,:,0];b=ts[:,:,1];c=ts[:,:,2];e0=b-a;e1=c-a;n=np.cross(e0,e1);pr=q-n*(np.sum((q-a)*n,axis=-1)/np.maximum(1e-14,np.sum(n*n,axis=-1)))[:,:,None];d00=np.sum(e0*e0,-1);d01=np.sum(e0*e1,-1);d11=np.sum(e1*e1,-1);d20=np.sum((pr-a)*e0,-1);d21=np.sum((pr-a)*e1,-1);den=np.maximum(1e-14,d00*d11-d01*d01);u=(d11*d20-d01*d21)/den;v=(d00*d21-d01*d20)/den;valid=(u>=0)&(v>=0)&(u+v<=1);candidates=[pr]
 for p0,p1 in [(a,b),(b,c),(c,a)]:
  e=p1-p0;t=np.clip(np.sum((q-p0)*e,-1)/np.maximum(1e-14,np.sum(e*e,-1)),0,1);candidates.append(p0+e*t[:,:,None])
 cp=np.stack(candidates,axis=2);dist=np.sum((cp-q[:,:,None,:])**2,-1);dist[:,:,0]=np.where(valid,dist[:,:,0],np.inf);choice=dist.reshape(len(points),-1).argmin(1);rows=np.arange(len(points));best=cp.reshape(len(points),-1,3)[rows,choice];normal=faceNormals[ids[rows,choice//4]];normal/=np.maximum(1e-12,np.linalg.norm(normal,axis=1)[:,None]);return np.sqrt(dist.reshape(len(points),-1)[rows,choice]),best,normal
'''
s=s.replace('for f in range(120):',function+'\nfor f in range(120):',1)
s=s.replace('dist,near=cKDTree(v).query(pp[ids])','dist,projected,normal=project(pp[ids],tri,fn)')
s=s.replace('ids=ids[ok];age=age[ok];near=near[ok];normal=normals[near]','ids=ids[ok];age=age[ok];projected=projected[ok];normal=normal[ok]')
s=s.replace('center=v[near]+normal*.004','center=projected+normal*.004')
s=s.replace("p=R/'lava.py';s=p.read_text(encoding='utf-8');a=s.index", "p=R/'lava.py';s=p.read_text(encoding='utf-8')\nif '# Persistent FLIP' not in s:raise SystemExit(0)\na=s.index")
p.write_text(s,encoding='utf-8');print('Closest-triangle projection keeps crust attachment continuous')
