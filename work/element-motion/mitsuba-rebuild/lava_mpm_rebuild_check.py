"""Small, independent CPU acceptance tests for the revised model."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import argparse,hashlib,json,time,traceback
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix,diags,eye
from lava_mpm import Material,MPM,ROOT,block
from lava_mpm_phase_field import update_damage,gradient_operator
from lava_mpm_friction import contact


def creep():
    m=Material();temperatures=np.array([850.,933.15,1050.,1164.,1260.]);mu,f,_,_=m.network(temperatures,.001)
    tau=np.divide(1.,mu*f,out=np.full_like(mu,np.inf),where=mu*f>0)
    assert np.isfinite(tau).all() and np.all(np.diff(tau)<0)
    crossing=m.liquidus-m.crystal_lock_fraction*(m.liquidus-m.solidus)
    t=np.array([crossing-1e-4,crossing+1e-4]);mu,f,_,_=m.network(t,.01)
    continuity=float(abs(np.diff(f)[0])/np.mean(f));assert continuity<1e-4
    # Independent analytic Maxwell relaxation under fixed strain.
    t=1050.;mu,f,_,_=m.network(np.array([t]),.01);tau0=float(1/(mu*f)[0]);errors=[]
    for n in (20,40,80):
        dt=tau0/n;_,_,r,_=m.network(np.array([t]),dt)
        measured=float(r[0]**n);errors.append(abs(measured-np.exp(-1)))
    assert errors[2]<errors[1]<errors[0] and errors[2]<.003
    return dict(temperaturesK=temperatures.tolist(),relaxationSeconds=tau.tolist(),packingContinuity=continuity,analyticRelaxationErrors=errors,calibration='Nominal, not composition-fitted')


def phase():
    gc=100.;ell=.002;h=.0005;x=block([0,0,0],[.008,.002,.002],h);v=np.full(len(x),h**3);eligible=np.ones(len(x),bool)
    H=np.full(len(x),2e5);d,r=update_damage(x,v,[h]*3,np.zeros(len(x)),H,eligible,gc,ell)
    exact=2*H[0]/(gc/ell+2*H[0]);error=float(np.max(abs(d-exact)));assert error<1e-10
    unloaded,_=update_damage(x,v,[h]*3,d,np.zeros(len(x)),eligible,gc,ell)
    assert np.max(abs(unloaded-d))<1e-10
    compression,_=update_damage(x,v,[h]*3,np.zeros(len(x)),np.zeros(len(x)),eligible,gc,ell)
    assert np.max(compression)==0
    melted,_=update_damage(x,v,[h]*3,d,H,np.zeros(len(x),bool),gc,ell);assert np.max(melted)==0
    # Analytic stationary crack profile exp(-|x|/ell), two surfaces combined
    # have fracture energy Gc per unit area. Refine physical ell unchanged.
    energies=[]
    for h in (ell/2,ell/4,ell/8):
        xx=np.arange(-12*ell,12*ell+h*.1,h)
        rest=np.c_[xx,np.zeros(len(xx)),np.zeros(len(xx))];volume=np.full(len(xx),h**3)
        L=gradient_operator(rest,volume,[h]*3,np.ones(len(xx),bool));profile=np.exp(-abs(xx)/ell)
        energy=float((gc/(2*ell)*np.dot(volume,profile**2)+gc*ell/2*profile@(L@profile))/h**2)
        energies.append(energy)
    err=abs(np.array(energies)-gc)/gc;assert err[2]<err[1]<err[0] and err[2]<.004
    return dict(homogeneousAnalyticError=error,kktResidual=r['kktResidual'],crackEnergyJPerM2=energies,exactCrackEnergyJPerM2=gc,irreversible=True,compressionDoesNotFracture=True,meltResets=True)


def friction():
    results=[]
    rng=np.random.default_rng(23)
    for rotation in (np.eye(3),np.linalg.qr(rng.normal(size=(3,3)))[0]):
        for tangential in (.05,.8):
            mass=np.array([1.,2.]);A=diags(np.repeat(mass,3));S=eye(6,format='csr')
            va=np.array([.2,tangential,0.]);vb=np.array([-.1,0.,0.]);initial=np.r_[va@rotation.T,vb@rotation.T]
            n=rotation[:,0];C=csr_matrix(np.r_[n,-n][None,:]);rhs=A@initial
            u,res,jn,loss,it,T,jt,report=contact(A,rhs,S,C,1e-12,friction=.6)
            inverse=1/mass[0]+1/mass[1];normal=.3/inverse;tangent=min(.6*normal,tangential/inverse)
            expected=initial.copy();impulse=rotation@np.array([normal,tangent,0.]);expected[:3]-=impulse/mass[0];expected[3:]+=impulse/mass[1]
            error=float(np.max(abs(u-expected)));assert error<1e-8,(error,report)
            momentum=float(np.linalg.norm((u.reshape(2,3)*mass[:,None]).sum(0)-(initial.reshape(2,3)*mass[:,None]).sum(0)))
            assert momentum<1e-10 and report['maximumConeViolation']<1e-10
            assert .5*u@(A@u)<=.5*initial@(A@initial)+1e-10
            results.append(dict(tangentialSpeed=tangential,error=error,momentumError=momentum,**report))
            # Separating bodies retain tangential motion and receive no impulse.
            separate=initial.copy();separate[:3]-=.4*n
            ans=contact(A,A@separate,S,C,1e-12,friction=.6)
            assert np.max(abs(ans[0]-separate))<1e-10 and np.max(abs(ans[2]))==0
    # An anisotropic coupled quadratic checks global equilibrium.
    K=rng.normal(size=(6,6));A=csr_matrix(K.T@K+np.eye(6));C=csr_matrix([[1,0,0,-1,0,0]])
    ans=contact(A,np.array([1.,2.,.3,-1.,0.,0.]),eye(6,format='csr'),C,1e-12,friction=.5)
    assert ans[-1]['stationarity']<1e-8 and ans[-1]['naturalResidual']<2e-8
    return dict(analyticCases=results,coupled=ans[-1])


def coupled():
    from lava_mpm_coupled import advance,snapshot
    x=block([-.001,-.001,.001],[.001,.001,.003],.0005)
    s=MPM(x,.0005,.001,temperature=1100.,origin=[-.004,-.004,-.002],shape=[9,9,10],ground=False,gravity=(0,0,-9.81))
    report=advance(s,.002,max_dt=.002,thermal=False)
    expected=-9.81*.002;error=float(np.max(abs(s.v[:,2]-expected)))
    assert error<2e-6 and s.damage.max()<1e-6
    # Force a failure after thermal mutation. All state must be rolled back.
    before=snapshot(s,{})
    def invalid(xyz):raise ValueError('Deliberate test failure after heat solve')
    try:s.step(.01,node_velocity=invalid)
    except ValueError:pass
    else:raise AssertionError('Failure was swallowed')
    assert s.time==before[0]['time'] and np.array_equal(s.h,before[0]['h']) and s.ledger==before[0]['ledger']
    return dict(gravityVelocityError=error,adaptive=report,rollback=True,damage=float(s.damage.max()))


def surface():
    from lava_mpm_material_surface import reconstruct
    from lava_mpm_hybrid_surface import fair_liquid
    from lava_mpm_surface_check import state,picture
    from PIL import Image,ImageDraw
    h=.001;x=block([-.006,-.006,.001],[.006,.006,.005],h)
    s=MPM(x,h,2*h,temperature=1450.,ground=False)
    # Explicit mesh test fixture: a partly opened cold lid over molten cells.
    # No mechanical evolution is claimed for this geometric test.
    s.h[s.x[:,2]>.003]=s.material.enthalpy(850.)
    t=s.material.temperature(s.h);solid=s.material.solid(t)
    s.connectivity.update(x,solid,s.damage,s.principal_direction,h,.65)
    a,b=s.connectivity.edges.T;s.connectivity.broken=(x[a,0]*x[b,0]<0)
    s.x[:,0]+=.0003*np.sign(x[:,0])*np.clip((x[:,2]-.002)/.001,0,1)
    raw,r=reconstruct(state(s),[h]*3);smooth,q=fair_liquid(raw,s.connectivity.frozen,[h]*3)
    assert q['mobileVertices']>0 and q['maximumDisplacementM']>0 and q['relativeVolumeError']<1e-8
    assert q['crustUnchanged'] and q['topologyUnchanged']
    assert np.array_equal(raw['v'][raw['f'][raw['crack_face']]],smooth['v'][smooth['f'][smooth['crack_face']]])
    # Rigid translation must give the same surface displacement.
    moved={k:v.copy() if isinstance(v,np.ndarray) else v for k,v in raw.items()};offset=np.array([.013,-.021,.004]);moved['v']+=offset
    translated,_=fair_liquid(moved,s.connectivity.frozen,[h]*3)
    error=float(np.max(abs(translated['v']-offset-smooth['v'])));assert error<1e-10
    image=Image.new('RGB',(960,430));image.paste(picture(raw,'Material boundary'),(0,0));image.paste(picture(smooth,'Liquid fairing / fixed crust'),(480,0))
    ImageDraw.Draw(image).text((16,403),'CPU geometric fixture, not simulated lava. Crack walls and crust vertices remain identical.',fill='#aaa')
    path=ROOT/'rebuild-24'/'surface.png';image.save(path)
    return dict(**q,translationEquivarianceErrorM=error,diagnostic=str(path))


def collision():
    from scipy.spatial import cKDTree
    h=.001;x=block([-.002,-.002,.003],[.002,.002,.005],h);group=x[:,0]>=0
    s=MPM(x,h,2*h,temperature=850.,origin=[-.008,-.008,-.002],shape=[9,9,10],ground=False,gravity=(0,0,0))
    pairs=cKDTree(x).query_pairs(h*1.82,output_type='ndarray');pairs=pairs[group[pairs[:,0]]==group[pairs[:,1]]]
    s.connectivity.edges=pairs;s.connectivity.broken=np.zeros(len(pairs),bool);s.connectivity.frozen[:]=True
    s.v[:,0]=np.where(group,-.02,.02);s.v[:,1]=np.where(group,-.04,.04)
    initial=float(.5*np.sum(s.mass[:,None]*s.v**2));momentum0=np.sum(s.mass[:,None]*s.v,axis=0)
    for _ in range(3):s.step(.00005,thermal=False)
    error=float(np.linalg.norm(np.sum(s.mass[:,None]*s.v,axis=0)-momentum0))
    kinetic=float(.5*np.sum(s.mass[:,None]*s.v**2))
    assert error<1e-10 and kinetic<=initial*1.01
    assert s.ledger.get('friction_heat',0)>0 and any(q['contactImpulses']>0 for q in s.rows)
    return dict(particles=len(x),momentumError=error,initialKineticJ=initial,finalKineticJ=kinetic,frictionHeatJ=s.ledger['friction_heat'],maximumSpeed=float(np.linalg.norm(s.v,axis=1).max()),contact=s.rows[-1].get('frictionContact'))


def pressure():
    from lava_mpm_fracture import implicit_contact
    # Two independent unit-area pistons with different compressibilities.
    # m v = dt p, p = -K (e_old + dt v); exact BE compression response.
    mass=np.array([1.,2.]);bulk=np.array([100.,250.]);dt=.1;strain=np.array([-.01,-.02])
    A=diags(mass);C=diags(np.full(2,-dt));compliance=1/bulk
    u,res,lam,_,_=implicit_contact(A,np.zeros(2),eye(2,format='csr'),C,compliance,-strain)
    exact=-dt*bulk*strain/(mass+dt*dt*bulk)
    assert np.max(abs(u-exact))<1e-12 and res<1e-10
    separation=implicit_contact(A,np.zeros(2),eye(2,format='csr'),C,compliance,strain)
    assert np.max(abs(separation[0]))==0 and np.max(abs(separation[2]))==0
    return dict(velocity=u.tolist(),analyticVelocity=exact.tolist(),maximumError=float(np.max(abs(u-exact))),tensileLiquidPressure=0.)


def transfers():
    from lava_mpm import basis_rect,p2g
    from lava_mpm_transfer import transfer
    rng=np.random.default_rng(327);x=block([.003,.003,.003],[.009,.009,.009],.001);cell=np.array([.002]*3)
    ids,w,g,dp=basis_rect(x,cell,np.zeros(3),np.array([8]*3));mass=np.ones(len(x));v=rng.normal(size=x.shape)*.1;C=rng.normal(size=(len(x),3,3))*2
    def project(v,C):
        gm,mom,_=p2g(ids,w,dp,mass,v,C,np.zeros(len(x)),8**3)
        return mom/np.maximum(gm[:,None],1e-30)
    before=project(v,C);vv,CC=transfer(v,C,before,before,ids,w,dp,cell,0.)
    assert np.array_equal(v,vv) and np.array_equal(C,CC)
    after=before+rng.normal(size=before.shape)*.01;vv,CC=transfer(v,C,before,after,ids,w,dp,cell,.0001)
    gm,_,_=p2g(ids,w,dp,mass,v,C,np.zeros(len(x)),8**3)
    grid_delta=(gm[:,None]*(after-before)).sum(0)
    error=float(np.linalg.norm(np.sum(mass[:,None]*(vv-v),axis=0)-grid_delta));assert error<1e-10
    kinetic=lambda v,C:float(.5*np.sum(mass*(np.sum(v*v,axis=1)+np.sum(C*C*cell[None,None,:]**2/4,axis=(1,2)))))
    energies=[]
    for n in (10,20,40):
        vv=v.copy();CC=C.copy()
        for _ in range(n):
            u=project(vv,CC);vv,CC=transfer(vv,CC,u,u,ids,w,dp,cell,.001/n)
        energies.append(kinetic(vv,CC))
    assert max(energies)<kinetic(v,C) and abs(energies[2]-energies[1])<abs(energies[1]-energies[0])
    return dict(zeroTimeIdentity=True,momentumError=error,initialAffineKineticJ=kinetic(v,C),filteredKineticJ=energies,experimental=True)


def main(names):
    folder=ROOT/'rebuild-24';folder.mkdir(exist_ok=True);reports={};start=time.time()
    for name in names:
        t=time.time()
        try:result=dict(status='pass',details=globals()[name]())
        except Exception as exc:result=dict(status='fail',error=str(exc),traceback=traceback.format_exc(limit=5))
        result['wallSeconds']=time.time()-t;reports[name]=result
        print(json.dumps(dict(test=name,**result)),flush=True)
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('lava_mpm*.py')}
    out=dict(status='pass' if all(q['status']=='pass' for q in reports.values()) else 'fail',tests=reports,sourceHashes=sources,wallSeconds=time.time()-start)
    path=folder/('checks-'+('-'.join(names))+'.json');path.write_text(json.dumps(out,indent=2));print(str(path))
    if out['status']!='pass':raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('names',nargs='*',default=['creep','phase','friction','coupled','surface']);main(p.parse_args().names)
