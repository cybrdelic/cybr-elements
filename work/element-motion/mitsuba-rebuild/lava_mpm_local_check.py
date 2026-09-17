"""Partial crack tip must open locally without globally detaching a block."""
import json
import numpy as np
from lava_mpm import MPM,ROOT,block,basis,p2g
from lava_mpm_fracture import local_fracture_labels,mechanical_fields


def main():
    spacing=.0025;dx=.005
    x=block([-.015,-.02,.02],[.015,.02,.03],spacing)
    s=MPM(x,spacing,dx,temperature=1000,gravity=(0,0,0),ground=False,origin=[-.04,-.04,0],shape=[18,18,14])
    cold=np.ones(len(x));directions=np.tile([1.,0,0],(len(x),1))
    s.connectivity.update(x,cold,np.zeros(len(x)),directions,spacing)
    a,b=s.connectivity.edges.T
    # A precracked mechanical coupon is an explicit validation boundary
    # condition, never an authored fracture input to the lava simulation.
    cut=(x[a,0]*x[b,0]<0)&(np.maximum(x[a,1],x[b,1])<.008)
    s.connectivity.broken=cut
    labels=s.connectivity.update(x,cold,np.zeros(len(x)),directions,spacing)
    assert len(np.unique(labels))==1,'The coupon should remain connected around its crack tip'
    ids,w,g,dp=basis(x,dx,s.origin,np.array(s.shape));tags=local_fracture_labels(ids,s.connectivity,s.shape,s.origin,dx,False)
    shifted=local_fracture_labels(ids,s.connectivity,s.shape,s.origin-np.array([0,0,.1]),dx,False)
    assert np.array_equal(tags,shifted),'Free bodies must not acquire a ghost boundary at z=0'
    grid,field,local=mechanical_fields(ids,tags);unique,counts=np.unique(grid,return_counts=True)
    xyz=s.origin+np.array(np.unravel_index(unique,s.shape)).T*dx
    split=(counts>1)&(abs(xyz[:,0])<.001)&(xyz[:,1]<-.005)
    assert split.any(),'Partial crack was welded despite crossing local supports'
    v=np.tile([.04,-.02,.01],(len(x),1));mass,momentum,_=p2g(local,w,dp,s.mass,v,np.zeros_like(s.C),s.h,len(grid))
    assert abs(mass.sum()-s.mass.sum())<1e-12
    assert np.linalg.norm(momentum.sum(0)-(s.mass[:,None]*v).sum(0))<1e-12
    u=momentum/np.maximum(mass[:,None],1e-30);out=np.sum(w[:,:,None]*u[local],axis=1)
    error=float(np.max(abs(out-v)));assert error<1e-12
    row=s.step(.001,thermal=False)
    assert row['maximumSpeed']<1e-5 and row['mechanicalResidual']<1e-6
    result=dict(status='pass',globalSolidComponents=1,locallySplitNodes=int(split.sum()),uniformTranslationError=error,zeroLoadMaximumSpeed=row['maximumSpeed'],solver=row)
    out=ROOT/'validation'/'local_fracture.json';out.write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(status='pass',globalSolidComponents=1,locallySplitNodes=int(split.sum()),uniformTranslationError=error,output=str(out))))

if __name__=='__main__':main()
