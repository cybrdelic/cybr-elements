"""Regression checks for phase coherence and changing contact activity."""
import json,numpy as np
from scipy.sparse import csr_matrix,eye
from lava_mpm import MPM,Material,ROOT,block
from lava_mpm_fracture import implicit_contact

def main():
    s=MPM(block([0,0,.02],[.02,.02,.04],.005),.005,.01,temperature=1248.15,material=Material(fracture_length=.02),ground=False,gravity=(0,0,0))
    solid=s.material.solid(s.material.temperature(s.h))
    labels=s.connectivity.update(s.x,solid,s.damage,s.principal_direction,s.sample_size,s.coherent_fraction)
    _,fluidity,_,_=s.material.network(s.material.temperature(s.h),.01)
    assert np.all(s.connectivity.frozen) and np.all(fluidity>0),'Coherence must retain finite hot-crust creep'
    assert np.all(solid>s.failure_fraction) and s.coherent_fraction==s.failure_fraction
    row=s.step(.01,thermal=False)
    assert row['maximumSpeed']<1e-8 and np.max(s.damage)==0
    # Contact 1 separates in the unconstrained solution. Constraining contact
    # 0 makes it approach, so the working set must add and solve contact 1.
    A=csr_matrix([[1.,.8],[.8,1.]]);free=np.array([1.,-.1]);rhs=A@free
    v,res,lam,loss,iterations=implicit_contact(A,rhs,eye(2,format='csr'),eye(2,format='csr'),1e-10)
    assert iterations>=2 and np.all(lam>0) and np.max(abs(v))<1e-8 and res<1e-8
    # Previously fractured material that melts must have the same liquid
    # viscosity as fresh melt. This compares actual MPM momentum/heat solves.
    material=Material()
    answers=[];heats=[]
    x=block([-.01,-.01,.02],[.01,.01,.04],.005)
    for damage in (0.,1.):
        q=MPM(x.copy(),.005,.01,temperature=1500.,material=material,ground=False,gravity=(0,0,0))
        q.damage[:]=damage;q.v[:,1]=.01*np.sin(x[:,0]/.02*np.pi)
        r=q.step(.01,thermal=False);answers.append(q.v.copy());heats.append(r['viscousHeatJ'])
    viscosity_error=float(np.linalg.norm(answers[0]-answers[1])/max(np.linalg.norm(answers[0]),1e-30))
    assert viscosity_error<1e-6 and min(heats)>0,(viscosity_error,heats)
    result=dict(status='pass',coherentFraction=s.coherent_fraction,failureFraction=s.failure_fraction,zeroLoadSpeed=row['maximumSpeed'],coupledContactExpansions=iterations,coupledContactVelocityError=float(abs(v).max()),mechanicalResidual=res,damagedMeltVelocityRelativeError=viscosity_error,damagedMeltHeatJ=heats)
    (ROOT/'validation'/'phase_contact_transition.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
