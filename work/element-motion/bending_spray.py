"""Resolution-dependent secondary spray parcels, with explicit mass accounting.

Isolated primary markers represent fluid parcels, not necessarily single drops.
Connected clusters remain large drops; detached single markers become a bounded
lognormal fragment population. Fragment sizes are an authored subgrid closure,
not a claim that the primary FLIP grid resolves these drops. Volume is conserved
within every parcel; persistent fragments inherit velocity and integrate gravity
and radius-dependent aerodynamic drag. Rejoining markers return to the bulk.
"""
import numpy as np
from scipy.spatial import cKDTree

class Spray:
    def __init__(self,h,capacity=220000,fragments=24):
        self.h=h;self.fragments=fragments;self.volume=(h*.5)**3
        self.active=np.zeros(capacity,bool)
        self.p=np.zeros((capacity,fragments,3),np.float32)
        self.v=np.zeros_like(self.p);self.r=np.zeros((capacity,fragments),np.float32)
        self.births=0;self.rejoins=0
    def step(self,p,v,isolated,dt,cluster):
        ids=np.flatnonzero(isolated);dense=np.zeros(len(ids),bool)
        if len(ids):
            tree=cKDTree(p[ids]);dense=tree.query_ball_point(p[ids],self.h*.62,return_length=True,workers=2)>=3
        heavy=ids[dense];singles=ids[~dense]
        mask=np.zeros_like(self.active);mask[singles]=True
        self.rejoins+=int(np.count_nonzero(self.active&~mask));new=singles[~self.active[singles]];old=singles[self.active[singles]]
        if len(new):
            k=np.arange(self.fragments)[None,:];q=new[:,None]
            def uniform(s):return np.mod(np.sin(q*12.9898+k*78.233+s*37.719)*43758.5453,1).clip(.00001,.99999)
            normal=np.sqrt(-2*np.log(uniform(1)))*np.cos(2*np.pi*uniform(2))
            radii=np.exp(normal*.65);radii*=np.cbrt(self.volume*3/(4*np.pi)/np.sum(radii**3,axis=1))[:,None]
            weights=radii**3/np.sum(radii**3,axis=1)[:,None]
            offsets=np.stack([uniform(s)-.5 for s in [3,4,5]],axis=2)*self.h*.8
            offsets-=np.sum(offsets*weights[:,:,None],axis=1)[:,None]
            capillarySpeed=np.minimum(.18,.35*np.sqrt(.072/(1000*np.maximum(radii,.00005))))
            direction=offsets/np.maximum(np.linalg.norm(offsets,axis=2)[:,:,None],1e-8)
            kick=direction*capillarySpeed[:,:,None]
            kick-=np.sum(kick*weights[:,:,None],axis=1)[:,None]
            self.p[new]=p[new,None]+offsets;self.v[new]=v[new,None]+kick;self.r[new]=radii
            self.births+=len(new)*self.fragments
        if len(old):
            pos=self.p[old].copy();velocity=self.v[old].copy();radius=self.r[old]
            for _ in range(3):
                step=dt/3;velocity[:,:,1]-=9.81*step
                relative=velocity-np.array([.035,0,.020],np.float32)
                speed=np.linalg.norm(relative,axis=2)
                # Quadratic sphere drag; the smaller fragments slow sooner.
                drag=3*1.225*.47/(8*1000*np.maximum(radius,.00002))*speed
                velocity-=relative*(1-np.exp(-drag*step))[:,:,None]
                pos+=velocity*step
            self.p[old]=pos;self.v[old]=velocity
        self.active=mask
        hp,hr,hv,counts=cluster(p[heavy],v[heavy])
        fp=self.p[singles].reshape(-1,3);fr=self.r[singles].reshape(-1);fv=self.v[singles].reshape(-1,3)
        outputP=np.concatenate([hp,fp]);outputR=np.concatenate([hr,fr]);outputV=np.concatenate([hv,fv])
        represented=float(np.sum(outputR.astype(float)**3)*4*np.pi/3);target=len(ids)*self.volume
        assert abs(represented-target)<max(1e-10,target*1e-5)
        return outputP,outputR,outputV,{'sprayFragments':len(fp),'coherentDrops':len(hp),'sprayParentMarkers':len(singles),'sprayVolume':represented,'sprayTargetVolume':target,'sprayVolumeRelativeError':(represented-target)/max(target,1e-12),'secondaryBirths':self.births,'secondaryRejoins':self.rejoins,'subgridClosure':'24 volume-normalized lognormal fragments per detached single parcel; coherent clusters stay intact; quadratic air drag'}
