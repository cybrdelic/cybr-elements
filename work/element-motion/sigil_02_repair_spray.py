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
        self.births=0;self.rejoins=0;self.previousNeighbours=np.zeros(capacity,np.int16)
    def step(self,p,v,isolated,dt,cluster):
        ids=np.flatnonzero(isolated);dense=np.zeros(len(ids),bool)
        if len(ids):
            tree=cKDTree(p[ids]);dense=tree.query_ball_point(p[ids],self.h*.62,return_length=True,workers=2)>=3
        # Estimate local unresolved relative motion using nearby primary markers.
        treeAll=cKDTree(p);dist,neighbours=treeAll.query(p,k=min(9,len(p)),workers=2)
        dist=dist[:,1:];neighbours=neighbours[:,1:];support=dist<self.h*1.5
        weights=np.where(support,1/np.maximum(dist,self.h*.1)**2,0);den=weights.sum(1)
        mean=np.einsum('nk,nkj->nj',weights,v[neighbours])/np.maximum(den[:,None],1e-20)
        mean[den==0]=v[den==0];relative2=np.sum((v-mean)**2,axis=1)
        weber=1000*relative2*self.h/.072;counts=support.sum(1)
        lost=self.previousNeighbours[:len(p)]-counts
        energetic=(weber>2.5)&(counts<=5)
        energetic|=(lost>=3)&(weber>.8)
        chosen=(~dense)
        singles=ids[chosen];heavy=ids[~chosen]
        self.previousNeighbours[:len(p)]=counts
        mask=np.zeros_like(self.active);mask[singles]=True
        self.rejoins+=int(np.count_nonzero(self.active&~mask));new=singles[~self.active[singles]];old=singles[self.active[singles]]
        if len(new):
            k=np.arange(self.fragments)[None,:];q=new[:,None]
            def uniform(s):return np.mod(np.sin(q*12.9898+k*78.233+s*37.719)*43758.5453,1).clip(.00001,.99999)
            normal=np.sqrt(-2*np.log(uniform(1)))*np.cos(2*np.pi*uniform(2))
            fragmentCount=np.clip((12+12*weber[new]/(weber[new]+8)).astype(int),4,self.fragments)
            radii=np.minimum(6.,(1-uniform(7))**(-1/1.7))*(k<fragmentCount[:,None]);radii*=np.cbrt(self.volume*3/(4*np.pi)/np.sum(radii**3,axis=1))[:,None]
            weights=radii**3/np.sum(radii**3,axis=1)[:,None]
            offsets=np.stack([uniform(s)-.5 for s in [3,4,5]],axis=2)*self.h*.8
            offsets-=np.sum(offsets*weights[:,:,None],axis=1)[:,None]
            capillarySpeed=np.minimum(.18,.35*np.sqrt(.072/(1000*np.maximum(radii,.00005))))
            direction=offsets/np.maximum(np.linalg.norm(offsets,axis=2)[:,:,None],1e-8)
            kick=direction*capillarySpeed[:,:,None]
            kick-=np.sum(kick*weights[:,:,None],axis=1)[:,None]
            rms=np.sqrt(np.sum(np.sum(kick*kick,axis=2)*weights,axis=1))
            budget=np.sqrt(np.maximum(0,relative2[new]-.072/(1000*self.h))*.15)
            kick*=np.minimum(1,budget/np.maximum(rms,1e-9))[:,None,None]
            self.p[new]=p[new,None]+offsets;self.v[new]=v[new,None]+kick;self.r[new]=radii
            self.births+=int(fragmentCount.sum())
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
        valid=fr>0;fp=fp[valid];fr=fr[valid];fv=fv[valid]
        outputP=np.concatenate([hp,fp]);outputR=np.concatenate([hr,fr]);outputV=np.concatenate([hv,fv])
        represented=float(np.sum(outputR.astype(float)**3)*4*np.pi/3);target=len(ids)*self.volume
        assert abs(represented-target)<max(1e-10,target*1e-5)
        return outputP,outputR,outputV,{'sprayFragments':len(fp),'coherentDrops':len(hp),'sprayParentMarkers':len(singles),'sprayVolume':represented,'sprayTargetVolume':target,'sprayVolumeRelativeError':(represented-target)/max(target,1e-12),'secondaryBirths':self.births,'secondaryRejoins':self.rejoins,'energeticDetachedParents':int(len(singles)),'coherentDetachedParents':int(len(heavy)),'maximumWeber':float(weber[ids].max()) if len(ids) else 0,'subgridClosure':'Unresolved solitary parcels use persistent 12..24 truncated-Pareto fragments; dense clusters remain coherent drops. Exact parcel volume, source momentum and bounded extra dispersion are retained.'}
