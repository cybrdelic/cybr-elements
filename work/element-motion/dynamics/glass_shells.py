"""Closed irregular plate fragments and transforms from the shared MPM carrier."""
from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation
R=Path(__file__).resolve().parent;rng=np.random.default_rng(931);seeds=rng.uniform([0,-.23],[8,.23],(75,2))
def clip(poly,n,c):
    out=[]
    for a,b in zip(poly,np.roll(poly,-1,axis=0)):
        da=np.dot(a,n)-c;db=np.dot(b,n)-c
        if da<=0:out.append(a)
        if (da<0)!=(db<0):out.append(a+(b-a)*da/(da-db))
    return np.array(out)
def sample(v,uv,side=0):
    rows=v.reshape(700,2,15,3);u=np.clip(uv[:,0]/8*699,0,698.999);w=np.clip((uv[:,1]+.23)/.46*14,0,13.999);i=u.astype(int);j=w.astype(int);a=u-i;b=w-j
    return (rows[i,side,j]*(1-b[:,None])+rows[i,side,j+1]*b[:,None])*(1-a[:,None])+(rows[i+1,side,j]*(1-b[:,None])+rows[i+1,side,j+1]*b[:,None])*a[:,None]
polys=[]
for k,a in enumerate(seeds):
    poly=np.array([[0,-.23],[8,-.23],[8,.23],[0,.23]])
    for j,b in enumerate(seeds):
        if j==k:continue
        poly=clip(poly,b-a,(np.dot(b,b)-np.dot(a,a))/2)
        if len(poly)<3:break
    if len(poly)>=3:polys.append(poly)
base=np.load(R/'surface/metal/0060.npz')['v'];parts=[];edge_owner={};connections=[]
for i,uv in enumerate(polys):
    front=sample(base,uv,0);back=sample(base,uv,1);middle=(front+back)/2;normal=front-back;normal/=np.maximum(np.linalg.norm(normal,axis=1)[:,None],1e-6);v=np.r_[middle+normal*.008,middle-normal*.008];center=v.mean(0);m=len(uv);faces=[list(range(m)),list(range(2*m-1,m-1,-1))]+[[j,(j+1)%m,(j+1)%m+m,j+m] for j in range(m)]
    parts.append({'uv':uv.tolist(),'vertices':(v-center).tolist(),'faces':faces,'center':center.tolist(),'transforms':[]})
    for a,b in zip(uv,np.roll(uv,-1,axis=0)):
        key=tuple(sorted([tuple(np.round(a,5)),tuple(np.round(b,5))]))
        if key in edge_owner:connections.append([edge_owner[key],i])
        else:edge_owner[key]=i
for f in range(61):
    v=np.load(R/'surface/metal'/f'{f:04}.npz')['v']
    for part,uv in zip(parts,polys):
        target=(sample(v,uv,0)+sample(v,uv,1))/2;center=target.mean(0);base0=np.array(part['vertices'])[:len(uv)];base0-=base0.mean(0);U,_,Vt=np.linalg.svd(base0.T@(target-center));rot=Vt.T@U.T
        if np.linalg.det(rot)<0:Vt[-1]*=-1;rot=Vt.T@U.T
        quat=Rotation.from_matrix(rot).as_quat();part['transforms'].append({'position':center.tolist(),'quaternion':[float(quat[3]),*quat[:3].tolist()]})
out=R/'cache/glass-shells.json';out.write_text(json.dumps({'parts':parts,'connections':connections,'thickness':.016,'releaseFrame':61}),encoding='utf-8');print('glass shells',len(parts),'connections',len(connections))
