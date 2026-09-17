"""Advected cooling plus brittle distance constraints on a FLIP carrier.
The cached FLIP supplies unfrozen motion; the solid phase integrates separately.
Heat exchange is a neighbor diffusion approximation with a latent-heat interval.
This is a split, one-way carrier coupling, not a full multiphase pressure solve.
"""
from pathlib import Path
import sys,json,time
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from cache_io import fluid_particles,fluid_mesh
from surface import density_surface
K=sys.argv[1];out=R/'cache'/K;out.mkdir(parents=True,exist_ok=True);surf=R/'surface'/K;surf.mkdir(parents=True,exist_ok=True)
x=np.empty((0,3));v=x.copy();enthalpy=np.empty(0);phase=np.empty(0);born=np.empty(0);frozen=np.empty(0,dtype=bool)
edges=np.empty((0,2),dtype=int);length=np.empty(0);alive=np.empty(0,dtype=bool);report=[];start=time.time()
for frame in range(120):
    t=(frame+1)/30;q,qv=fluid_particles(frame,K=='lava');mv,mf,_,_=fluid_mesh(frame,K=='lava');old=len(x);n=len(q);new=n-old
    if new:
        x=np.concatenate([x,q[old:]]);v=np.concatenate([v,qv[old:]]);enthalpy=np.r_[enthalpy,np.ones(new)];phase=np.r_[phase,np.zeros(new)];born=np.r_[born,np.full(new,t)];frozen=np.r_[frozen,np.zeros(new,dtype=bool)]
    if n>12:
        tree=cKDTree(q);dist,idx=tree.query(q,k=9,workers=2);stree=cKDTree(mv);ds,_=stree.query(q)
        exposure=np.clip(1-ds/.085,0,1)
        enthalpy+=(enthalpy[idx[:,1:]].mean(1)-enthalpy)*.14
        cool={'ice':.8,'glass':2.4,'lava':.34}[K]
        enthalpy=np.maximum(0,enthalpy-(.2+.8*exposure)*cool/30)
        newphase=np.clip((.83-enthalpy)/(.35 if K!='lava' else .30),0,1)
        just=(newphase>.68)&(~frozen);frozen|=just;phase=newphase
        free=~frozen;x[free]=q[free];v[free]=qv[free]
        if np.any(just):
            ids=np.flatnonzero(just);dtree=cKDTree(x);dd,nn=dtree.query(x[ids],k=12,workers=2)
            ee=np.column_stack([np.repeat(ids,11),nn[:,1:].ravel()]);keep=(dd[:,1:].ravel()<.095)&frozen[ee[:,1]]
            ee=np.sort(ee[keep],axis=1);ee=np.unique(ee,axis=0);ll=np.linalg.norm(x[ee[:,0]]-x[ee[:,1]],axis=1);ok=ll>.009
            edges=np.r_[edges,ee[ok]];length=np.r_[length,ll[ok]];alive=np.r_[alive,np.ones(ok.sum(),dtype=bool)]
        support=1-np.clip((t-2.0)/.5,0,1)
        for sub in range(5):
            dt=1/150;before=x.copy();v[frozen,2]-=9.81*(1-support*.92)*dt;v[frozen]*=np.exp(-dt*.7);x[frozen]+=v[frozen]*dt
            for it in range(7):
                e=edges[alive];rest=length[alive]
                if not len(e):break
                a,b=e.T;delta=x[b]-x[a];dd=np.linalg.norm(delta,axis=1);strain=np.abs(dd/rest-1)
                if it==0:
                    broken=strain>({'ice':.22,'glass':.13,'lava':.40}[K]);ai=np.flatnonzero(alive);alive[ai[broken]]=False
                corr=delta*((dd-rest)/np.maximum(dd,1e-6)*.4)[:,None];corr[strain>.6]=0
                accum=np.zeros_like(x);degree=np.zeros(n);np.add.at(accum,a,corr);np.add.at(accum,b,-corr);np.add.at(degree,a,1);np.add.at(degree,b,1);x+=accum/np.maximum(1,degree[:,None])
            v[frozen]=(x[frozen]-before[frozen])/dt
        assert np.isfinite(x).all();assert np.abs(x).max()<100
        # The frozen geometry follows particle states; it is never a swept curve.
        if K=='lava':
            # Keep the trusted carrier surface, with advected heat on vertices.
            _,near=tree.query(mv);vv=mv;ff=mf;heat=enthalpy[near];solid=phase[near]
        else:
            visible=(np.abs(x[:,0])<5.8)&(np.abs(x[:,1])<1.5)&(x[:,2]>-1.2)&(x[:,2]<5.3)
            vv,ff=density_surface(x[visible],spacing=.024,radius=.023,level=.34)
            if len(vv):_,near=cKDTree(x).query(vv);heat=enthalpy[near];solid=phase[near]
            else:heat=np.empty(0);solid=np.empty(0)
        np.savez_compressed(surf/f'{frame:04}.npz',v=vv,f=ff,heat=heat.astype('f4'),phase=solid.astype('f4'))
    else:
        np.savez_compressed(surf/f'{frame:04}.npz',v=np.empty((0,3),'f4'),f=np.empty((0,3),'i4'),heat=np.empty(0),phase=np.empty(0))
    np.savez_compressed(out/f'{frame:04}.npz',p=x.astype('f4'),v=v.astype('f4'),heat=enthalpy.astype('f4'),phase=phase.astype('f4'),born=born.astype('f4'))
    report.append({'frame':frame,'solid':int(frozen.sum()),'bonds':int(alive.sum()),'broken':int((~alive).sum())})
    if frame%15==0:print(K,frame,'solid',int(frozen.sum()),'bonds',int(alive.sum()),round(time.time()-start,1),flush=True)
(out/'report.json').write_text(json.dumps({'solver':'neighbor heat transport and brittle XPBD phase constraints','limits':'Accelerated cooling; one-way cached FLIP carrier coupling; discrete bond fracture','frames':report},indent=2),encoding='utf-8')
