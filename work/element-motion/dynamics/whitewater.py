"""Secondary liquid simulation sourced by acceleration and surface exposure.
Persistent particles transition between submerged bubbles, surface foam and
ballistic spray. Film loss follows drainage and local exposure.
"""
from pathlib import Path
import sys,json,time
import numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R));from cache_io import fluid_particles,fluid_mesh
rng=np.random.default_rng(853);out=R/'cache/foam';out.mkdir(parents=True,exist_ok=True)
p=np.empty((0,3));v=p.copy();r=np.empty(0);life=np.empty(0);film=np.empty(0);pid=np.empty(0,dtype=int);source=np.empty(0,dtype=int);attached=np.empty(0,dtype=bool);prev=np.empty((0,3));prevp=np.empty((0,3));lastid=0;report=[];start=time.time()
for frame in range(120):
    q,qv=fluid_particles(frame);verts,faces,_,_=fluid_mesh(frame)
    if len(q)>20 and len(verts)>20:
        tree=cKDTree(q);dist,neigh=tree.query(q,k=12,workers=2)
        stree=cKDTree(verts);surface_distance,_=stree.query(q);exposed=surface_distance<.045
        acc=np.zeros(len(q));old=min(len(q),len(prev));acc[:old]=np.linalg.norm(qv[:old]-prev[:old],axis=1)*30
        shear=np.linalg.norm(qv-qv[neigh[:,1:]].mean(1),axis=1)
        emission=np.clip((acc-9)/30,0,1)*np.clip(shear/.35,0,1)*exposed
        candidates=np.flatnonzero(rng.random(len(q))<emission*.35)
        if len(candidates)>300:candidates=rng.choice(candidates,300,replace=False)
        candidates=np.repeat(candidates,8)
        # Place secondary seeds at actual surface vertices, not in an emitter halo.
        dd,vi=stree.query(q[candidates]);candidates=candidates[dd<.14];vi=vi[dd<.14]
        count=len(candidates);np0=verts[vi]+rng.normal(0,.009,(count,3))
        if len(p) and len(prevp):
            ok=attached&(source<len(prevp));p[ok]+=q[source[ok]]-prevp[source[ok]]
        p=np.concatenate([p,np0]);v=np.concatenate([v,qv[candidates]*.94]);r=np.r_[r,np.minimum(.011,.0042/np.maximum(rng.random(count),.02)**.30)]
        film=np.r_[film,rng.uniform(.8,1.2,count)];life=np.r_[life,np.zeros(count)];pid=np.r_[pid,np.arange(lastid,lastid+count)];lastid+=count
        source=np.r_[source,candidates];attached=np.r_[attached,rng.random(count)<.86]
        # Interpolate the carrier velocity and surface normal at each substep.
        for sub in range(4):
            dt=1/120
            ds,ii=stree.query(p);dp,ni=tree.query(p,k=4,workers=2);ww=1/np.maximum(dp,.006)**2;ww/=ww.sum(1)[:,None];flow=np.sum(qv[ni]*ww[:,:,None],axis=1)
            surface=verts[ii];delta=p-surface;normal=delta/np.maximum(ds[:,None],.001)
            # A local occupancy estimate distinguishes submerged and exposed cells.
            occupied=dp[:,0]<.046;foam=(ds<.026)|attached;spray=(~occupied)&(~foam);bubble=occupied&(~foam)
            v[foam]+=(flow[foam]-v[foam])*(1-np.exp(-dt*28));v[foam]-=delta[foam]*dt*180
            v[bubble]+=(flow[bubble]-v[bubble])*(1-np.exp(-dt*9));v[bubble,2]+=dt*2.8
            v[spray,2]-=9.81*dt;v[spray]*=np.exp(-dt*.65)
            p[~attached]+=v[~attached]*dt
            # Surface-attached gas follows the moving FLIP material identity;
            # only its drift relative to the carrier is integrated here.
            p[attached]+=(v[attached]-flow[attached])*dt
            p[attached]+=(surface[attached]-p[attached])*(1-np.exp(-dt*35))
            life+=dt
            # Foam drains faster where it is isolated; bubbles preserve gas mass.
            film-=dt*(.13+spray*.6+np.clip(ds/.1,0,1)*.16)
        alive=(film>0)&(life<3.5)&(p[:,2]>-2)&(np.abs(p[:,0])<7)&(np.abs(p[:,1])<3)
        p,v,r,life,film,pid,source,attached=[a[alive] for a in [p,v,r,life,film,pid,source,attached]]
        assert np.isfinite(p).all() and np.isfinite(v).all()
    prev=qv.copy();prevp=q.copy();np.savez_compressed(out/f'{frame:04}.npz',p=p.astype('f4'),v=v.astype('f4'),r=r.astype('f4'),film=film.astype('f4'),id=pid)
    report.append({'frame':frame,'particles':len(p)})
    if frame%20==0:print('whitewater',frame,len(p),round(time.time()-start,1),flush=True)
(out/'report.json').write_text(json.dumps({'solver':'persistent POP secondary advection, buoyancy, ballistic spray and film drainage','carrier':'accepted FLIP cache','limits':'Approximate occupancy classification; no fully resolved wet-foam cell pressure solve','frames':report},indent=2),encoding='utf-8')
