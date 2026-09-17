"""Branched mass/spring rods with length, bending and attachment constraints.
Leaves are transported by the solved branch spines in render_botanical.py.
Growth is authored; lag, bending and release are integrated dynamics.
"""
import sys,json
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R.parent));from shared_motion import pose
rng=np.random.default_rng(217);rest=[];birth=[];chains=[];radii=[];main=330
for i,t in enumerate(np.linspace(.08,1.68,main)):
    p,d,_,_=pose(float(t));rest.append([p[0],.012*np.sin(t*8),p[1]]);birth.append(t);radii.append(.014*(1-.35*i/main))
chains.append(np.arange(main));shoots=[]
for i,root in enumerate(np.linspace(24,312,16).astype(int)):
    t=birth[root];p,d,_,_=pose(float(t));normal=np.array([-d[1],0,d[0]])*(-1 if i%2 else 1);direction=normal*.65+np.array([d[0]*.3,.28*np.sin(i*1.9),.35+d[1]*.3]);direction/=np.linalg.norm(direction)
    length=rng.uniform(.36,.68);chain=[int(root)]
    for j in range(1,13):
        u=j/12;chain.append(len(rest));rest.append(np.array(rest[root])+direction*length*u+np.array([0,.055*np.sin(np.pi*u),-.09*u*u]));birth.append(t+.035+j*.013);radii.append(.006*(1-.7*u))
    chains.append(np.array(chain));shoots.append({'root':int(root),'chain':chain,'length':length,'variant':i%5})
rest=np.array(rest);birth=np.array(birth);rad=np.array(radii);edges=[];stiff=[]
for ch in chains:
    for a,b in zip(ch[:-1],ch[1:]):edges.append([a,b]);stiff.append(.95)
    for a,b in zip(ch[:-2],ch[2:]):edges.append([a,b]);stiff.append(.50)
edges=np.array(edges);stiff=np.array(stiff);length=np.linalg.norm(rest[edges[:,0]]-rest[edges[:,1]],axis=1)
# Edge coloring avoids race/overlap in constraint projection.
colors=[];used=[set() for _ in rest]
for k,(a,b) in enumerate(edges):
    c=0
    while c in used[a] or c in used[b]:c+=1
    while len(colors)<=c:colors.append([])
    colors[c].append(k);used[a].add(c);used[b].add(c)
x=rest.copy();v=np.zeros_like(x);history=[];speeds=[]
for f in range(120):
    for sub in range(8):
        dt=1/240;t=(f+sub/8)/30;active=birth<=t;young=active&((t-birth)<.06);support=1-np.clip((t-2.0)/.65,0,1)
        v[active,2]-=9.81*(1-support*.96)*dt;v[active]*=np.exp(-dt*1.25)
        # Aerodynamic force varies spatially; it is integrated into velocity.
        v[active,1]+=dt*.45*(np.sin(x[active,0]*2+t*3)+np.cos(x[active,2]*5-t*2))
        old=x.copy();x[active]+=v[active]*dt
        inv=active.astype(float);inv[young]=0;x[young]=rest[young]
        for it in range(10):
            for color in colors:
                ix=np.array(color);a,b=edges[ix].T;ok=active[a]&active[b];a,b,ix=a[ok],b[ok],ix[ok];delta=x[b]-x[a];dist=np.linalg.norm(delta,axis=1);denom=np.maximum(inv[a]+inv[b],1e-8)
                correction=delta*((dist-length[ix])/np.maximum(dist,1e-8)*stiff[ix]/denom)[:,None];x[a]+=correction*inv[a,None];x[b]-=correction*inv[b,None]
        v[active]=(x[active]-old[active])/dt;x[~active]=rest[~active]
    assert np.isfinite(x).all();history.append(x.astype('f4'));speeds.append(float(np.linalg.norm(v[active],axis=1).max(initial=0)))
out=R/'cache/plants';out.mkdir(parents=True,exist_ok=True);np.savez_compressed(out/'rods.npz',p=history,rest=rest,birth=birth,radii=rad,edges=edges,length=length)
(out/'structure.json').write_text(json.dumps({'chains':[a.tolist() for a in chains],'shoots':shoots,'solver':'colored length and bending constraint rods, 8 substeps, 10 iterations','growth':'authored activation; dynamics after formation','maxSpeed':speeds},indent=2),encoding='utf-8');print('plants: 120 frames,',len(rest),'rod nodes,',len(edges),'constraints')
