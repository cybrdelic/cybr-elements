"""Independent acceptance cases for sparse pressure and transaction costs."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import json,time,traceback
import numpy as np
from scipy.sparse import diags,eye,csr_matrix
from lava_mpm import ROOT,Material,MPM,block,SOURCE_HASHES

def pressure():
    from lava_mpm_sparse_pressure import contact
    from lava_mpm_fracture import implicit_contact
    rng=np.random.default_rng(25);Q=rng.normal(size=(36,36));A=csr_matrix(Q.T@Q+np.eye(36))
    C=csr_matrix(rng.normal(size=(52,36)));b=rng.normal(size=36);offset=rng.normal(size=52)*.05
    compliance=np.exp(rng.uniform(-4,1,52));S=eye(36,format='csr')
    small=contact(A,b,S,C,compliance,offset);reference=implicit_contact(A,b,S,C,compliance,offset)
    error=float(np.max(abs(small[0]-reference[0])));assert error<1e-7,error
    # 2,048 independent compressible pistons; exact BE solution, no dense
    # reference assembly (which would require quadratic storage).
    n=2048;mass=np.linspace(1,2,n);K=np.linspace(50,250,n);dt=.1
    strain=np.linspace(-.02,.01,n);start=time.time()
    z=contact(diags(mass),np.zeros(n),eye(n,format='csr'),diags(np.full(n,-dt)),1/K,-strain)
    exact=np.maximum(-dt*K*strain/(mass+dt*dt*K),0.)
    err=float(np.max(abs(z[0]-exact)));assert err<1e-10 and z[1]<1e-8
    return dict(coupledDenseDifference=error,pistons=n,analyticError=err,wallSeconds=time.time()-start,iterations=z[-1])

def transaction():
    from lava_mpm_coupled import snapshot,restore
    s=MPM(block([0,0,.001],[.002,.002,.003],.001),.001,.002,ground=False)
    s.rows=[dict(time=i,phaseField={'fractureEnergyJ':float(i)}) for i in range(12000)]
    before=snapshot(s,{});old=s.x.copy();s.x+=1;s.rows.append({'rejected':True});s.ledger['fracture']=9.
    restore(s,{},before)
    assert len(s.rows)==12000 and np.array_equal(s.x,old) and s.ledger['fracture']==0
    assert s.rows is not before[0]['rows'] and s.rows[0] is before[0]['rows'][0]
    start=time.time()
    for _ in range(20):q=snapshot(s,{});restore(s,{},q)
    elapsed=time.time()-start
    return dict(acceptedRows=12000,rollback=True,twentyRoundTripsSeconds=elapsed)

def material():
    m=Material(melt_viscosity_law='farrell_180719')
    t=1195+273.15;logeta=float(np.log10(m.viscosity(t)))
    assert abs(logeta-2.3)<.2
    # Equation 3 independent scalar evaluation at the paper's core temperature.
    assert abs(logeta-(-4.55+5978.4/(t-595.3)))<1e-12
    # Actual MPM manufactured affine shear verifies heat rate eta*gamma^2 V.
    x=block([-.002,-.002,.002],[.002,.002,.006],.001)
    s=MPM(x,.001,.002,temperature=t,material=m,ground=False,gravity=(0,0,0),origin=[-.006,-.006,-.002],shape=[8,8,8])
    gamma=.3;s.v[:,0]=gamma*s.x[:,2];s.C[:,0,2]=gamma;dt=.002
    def shear(xyz):
        value=np.zeros_like(xyz);value[:,0]=gamma*xyz[:,2]
        return np.ones_like(xyz,dtype=bool),value
    s.step(dt,thermal=False,node_velocity=shear)
    expected=float(m.viscosity(t)*gamma**2*s.mass.sum()/m.density*dt)
    error=abs(s.ledger['viscous_heat']-expected)/expected;assert error<1e-8
    return dict(coreTemperatureK=t,log10ViscosityPaS=logeta,reportedLog10Range=[2.1,2.5],shearHeatingRelativeError=error,
        source='https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2019JB018815',
        scope='Published dry melt VFT relation, flow 180719. Not a calibration of crystal kinetics, basalt fracture or rock creep.')

def crack_bridge():
    from lava_mpm_fracture import Connectivity
    h=.001;x=block([-.004,0,0],[.004,.003,.002],h)
    # Analytic diffuse band: peak at one layer, healthy neighbours. This is
    # a topology test of a supplied field, not a simulated fracture claim.
    d=np.exp(-abs(x[:,0]-.0005)/.002);direction=np.tile([1.,0.,0.],(len(x),1))
    c=Connectivity(len(x));c.update(x,np.ones(len(x)),d,direction,h,.65)
    left=np.unique(c.labels[x[:,0]<-.0005]);right=np.unique(c.labels[x[:,0]>.0015])
    assert not np.intersect1d(left,right).size
    a,b=c.edges.T;normal=abs(x[b,0]-x[a,0])>h*.1
    assert not c.broken[~normal].any()
    return dict(components=len(np.unique(c.labels)),brokenEdges=int(c.broken.sum()),oppositeSidesDisconnected=True,tangentialBondsPreserved=True)

def acceleration():
    from lava_mpm_coupled import advance
    x=block([-.004,-.001,.001],[.004,.001,.003],[.001,.0005,.0005]);states=[];counts=[]
    def grips(xyz):
        mask=np.zeros_like(xyz,dtype=bool);v=np.zeros_like(xyz);mask[:,0]=abs(xyz[:,0])>=.0035;v[:,0]=np.sign(xyz[:,0])*.0001
        return mask,v
    for mode in ('relaxed','anderson'):
        s=MPM(x,.001,.002,temperature=850.,ground=False,gravity=(0,0,0),cell_size=[.002,.001,.001],sample_size=[.001,.0005,.0005],origin=[-.01,-.004,-.002],shape=[11,9,10])
        s.damage_acceleration=mode
        for _ in range(10):s.step(.002,thermal=False,node_velocity=grips)
        states.append(s);counts.append(sum(q['damageCouplingIterations'] for q in s.rows))
    delta=float(np.max(abs(states[0].damage-states[1].damage)))
    work=abs(states[0].ledger['prescribed_boundary_work']-states[1].ledger['prescribed_boundary_work'])/abs(states[0].ledger['prescribed_boundary_work'])
    assert delta<5e-5 and work<1e-4 and counts[1]<counts[0],(delta,work,counts)
    # A timeout of the second half-step restores the entire outer trial.
    s=MPM(x,.001,.002,temperature=1450.,ground=False);initial=s.x.copy();calls=[0];actual=s.step
    def timeout_step(dt,**kwargs):
        calls[0]+=1
        if calls[0]==3:raise TimeoutError('Deliberate second-half deadline')
        return actual(dt,**kwargs)
    s.step=timeout_step
    try:advance(s,.001,max_dt=.001,thermal=False)
    except TimeoutError:pass
    else:raise AssertionError('Missing deadline exception')
    assert s.time==0 and len(s.rows)==0 and np.array_equal(s.x,initial)
    return dict(damageDifference=delta,workRelativeDifference=work,couplingIterations=dict(zip(('relaxed','anderson'),counts)),timeoutRollsBackWholeTrial=True)

def rock_creep():
    from scipy.optimize import brentq
    m=Material(rheology='basalt_power_creep',fracture_energy=1e24)
    t=1173.15;sigma=100e6;dt=10.;mu=m.young/(2*(1+m.poisson))
    independent=lambda stress:6.1e8*(stress/1e6)**3.6*np.exp(-456000/(8.314462618*t))
    f=m.network(np.array([t]),dt,np.array([sigma]))[1][0]
    assert abs(f*sigma/3-independent(sigma))/independent(sigma)<1e-12
    exact=brentq(lambda q:q+3*mu*dt*independent(q)-sigma,0.,sigma)
    x=block([0,0,.001],[.002,.002,.003],.001)
    s=MPM(x,.001,.002,temperature=t,material=m,ground=False,gravity=(0,0,0),origin=[-.004,-.004,-.002],shape=[8,8,8])
    s.deviator[:,:3]=np.array([2.,-1.,-1.])*sigma/3
    fixed=lambda xyz:(np.ones_like(xyz,dtype=bool),np.zeros_like(xyz))
    row=s.step(dt,thermal=False,node_velocity=fixed)
    measured=np.sqrt(1.5*np.sum(s.deviator**2,axis=1))
    error=float(np.max(abs(measured-exact))/exact);assert error<2e-6
    assert np.max(abs(s.dilation))<1e-10 and s.ledger['viscous_heat']>0
    # The same creep mechanism cannot relax hydrostatic strain.
    h=MPM(x,.001,.002,temperature=t,material=m,ground=False,gravity=(0,0,0),origin=[-.004,-.004,-.002],shape=[8,8,8]);h.dilation[:]=.001
    h.step(dt,thermal=False,node_velocity=fixed)
    assert np.max(abs(h.dilation-.001))<1e-10 and h.ledger['viscous_heat']<1e-20
    return dict(temperatureK=t,initialEquivalentStressPa=sigma,strainRatePerS=independent(sigma),backwardEulerStressPa=exact,stressRelativeError=error,
        couplingIterations=row['damageCouplingIterations'],hydrostaticCreep=False,
        source='https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2011JB008884',
        scope='GFB power law reported for 850–950 C and 300 MPa confinement. Surface lava use is an extrapolation; crystal fractions and fracture constants remain nominal.')

def mixed_contact():
    from lava_mpm_friction import contact,mixed_contact
    from scipy.sparse import vstack
    rng=np.random.default_rng(311);Q=rng.normal(size=(6,6));A=csr_matrix(Q.T@Q+np.eye(6)*3)
    C0=csr_matrix([[1,0,0,-1,0,0]]);Cp=csr_matrix(rng.normal(size=(40,6))*.1);C=vstack([C0,Cp],format='csr')
    rhs=np.array([2.,4.,0.,-2.,0.,0.]);comp=np.r_[1e-8,np.full(40,.05)];offset=np.r_[0.,rng.normal(size=40)*.01];mu=np.r_[.6,np.zeros(40)];to=np.zeros(82);S=eye(6,format='csr')
    dense=contact(A,rhs,S,C,comp,offset,mu,to)
    mixed=mixed_contact(A,rhs,S,C,comp,offset,mu,to,1)
    error=float(np.max(abs(dense[0]-mixed[0])));assert error<1e-7,error
    assert mixed[-1]['naturalResidual']<2e-8 and mixed[-1]['stationarity']<1e-5
    unloaded_offset=offset.copy();unloaded_offset[0]=-100
    unloaded=mixed_contact(A,rhs,S,C,comp,unloaded_offset,mu,to,1)
    reference=contact(A,rhs,S,C,comp,unloaded_offset,mu,to)
    unloaded_error=float(np.max(abs(unloaded[0]-reference[0])))
    assert unloaded[-1].get('unloadedFrictionFastPath') and unloaded_error<1e-7
    return dict(denseVelocityDifference=error,unloadedVelocityDifference=unloaded_error,pressureRows=40,frictionRows=1,pressureActiveIterations=mixed[-1]['pressureActiveIterations'],stationarity=mixed[-1]['stationarity'])

def heat_bounds():
    from lava_mpm import bounded_heat_transfer
    old=np.array([0.,100.]);mass=np.array([1.,1.]);local=np.array([[0],[0]]);w=np.ones((2,1))
    h,r=bounded_heat_transfer(old,np.array([50.]),np.array([60.]),local,w,mass)
    assert np.max(h)<=100 and np.min(h)>=0 and abs(mass@h-120)<1e-12
    assert r['unlimitedMaximumOvershootJPerKg']==10 and r['flipFraction']<1
    identity,_=bounded_heat_transfer(old,np.array([50.]),np.array([50.]),local,w,mass)
    assert np.array_equal(identity,old)
    from lava_mpm_continuous import HotBed
    x=block([-.002,-.002,0],[.002,.002,.002],.0005);t=np.where(x[:,2]<.0005,1450.,1200.)
    s=MPM(x,.0005,.001,temperature=t,origin=[-.005,-.005,-.002],shape=[11,11,9],gravity=(0,0,0))
    for _ in range(5):s.step(.1,mechanics=False,bed=HotBed(1450.))
    maximum=float(s.material.temperature(s.h).max());assert maximum<=1450+1e-7
    assert s.rows[-1]['thermalBalanceRelative']<1e-9
    return dict(twoParticleResult=h.tolist(),energyErrorJ=r['transferEnergyErrorJ'],zeroTimeIdentity=True,mpmMaximumTemperatureK=maximum,maximumAllowedTemperatureK=1450.,thermalBalanceRelative=s.rows[-1]['thermalBalanceRelative'])

if __name__=='__main__':
    results={}
    for name in ('pressure','transaction','material','crack_bridge','acceleration','rock_creep','mixed_contact','heat_bounds'):
        try:results[name]=dict(status='pass',details=globals()[name]())
        except Exception as exc:results[name]=dict(status='fail',error=str(exc),traceback=traceback.format_exc(limit=5))
        print(json.dumps(dict(test=name,**results[name])),flush=True)
    folder=ROOT/'rebuild-25';folder.mkdir(exist_ok=True)
    result=dict(status='pass' if all(q['status']=='pass' for q in results.values()) else 'fail',tests=results,sourceHashes=SOURCE_HASHES)
    (folder/'component-validation.json').write_text(json.dumps(result,indent=2))
    raise SystemExit(result['status']!='pass')
