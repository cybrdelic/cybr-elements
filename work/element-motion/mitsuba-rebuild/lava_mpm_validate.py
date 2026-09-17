"""Independent physical/numerical tests, all CPU. Failing tests block renders."""
from pathlib import Path
import json,time,traceback,argparse
import numpy as np
from scipy.sparse import diags
from scipy.special import erf
from scipy.optimize import brentq
from lava_mpm import Material,MPM,ROOT,basis,p2g,strain_matrix,heat_solve,tensile_damage,block


def transfers():
    rng=np.random.default_rng(20);dx=.01;origin=np.zeros(3);shape=np.array([12]*3)
    x=rng.uniform(.025,.075,(80,3));ids,w,g,dp=basis(x,dx,origin,shape)
    affine=np.array([[.03,-.1,.2],[.1,-.01,.07],[.04,-.05,.02]]);v=x@affine.T+[.1,.2,.3]
    C=np.tile(affine,(len(x),1,1));mass=np.ones(len(x));h=np.ones(len(x))*1e5
    gm,mom,e=p2g(ids,w,dp,mass,v,C,h,int(np.prod(shape)));gv=mom/np.maximum(gm[:,None],1e-30)
    out=np.sum(w[:,:,None]*gv[ids],axis=1);cc=4/dx**2*np.einsum('pk,pki,pkj->pij',w,gv[ids],dp)
    errors=dict(weight=float(abs(w.sum(1)-1).max()),gradient=float(abs(g.sum(1)).max()),affineVelocity=float(abs(out-v).max()),affineGradient=float(abs(cc-C).max()),momentum=float(np.linalg.norm(mom.sum(0)-(mass[:,None]*v).sum(0))))
    assert max(errors.values())<1e-10,errors
    return errors


def enthalpy():
    m=Material();t=np.linspace(250,1700,2001);error=float(abs(m.temperature(m.enthalpy(t))-t).max())
    latent=float(m.enthalpy(m.liquidus)-m.enthalpy(m.solidus)-m.cp*(m.liquidus-m.solidus))
    assert error<1e-10 and abs(latent-m.latent_heat)<1e-8
    return dict(roundtripK=error,latentHeatJPerKg=latent)


def insulated_heat():
    m=Material(emissivity=0,convection=0);dx=.002;n=24
    t=np.r_[np.full(n//2,1050.),np.full(n-n//2,1500.)];mass=np.ones(n)*m.density*dx
    edge=np.ones(n-1)*m.conductivity/dx
    K=diags([np.r_[edge,0]+np.r_[0,edge],-edge,-edge],[0,-1,1],format='csr')
    h=m.enthalpy(t);initial=mass@h;max_error=0
    for _ in range(20):
        h,r=heat_solve(m,h,mass,K,np.zeros(n),np.full(n,293.15),.5)
        max_error=max(max_error,abs(float(mass@h-initial))/abs(initial))
    assert max_error<1e-9 and m.temperature(h).min()>=1050 and m.temperature(h).max()<=1500
    return dict(relativeEnergyError=max_error,rangeK=[float(m.temperature(h).min()),float(m.temperature(h).max())])


def stefan():
    # One-phase Stefan problem: initially at liquidus, cold Dirichlet face.
    # Narrow mushy interval approaches the known similarity front position.
    m=Material(solidus=1200.,liquidus=1200.05,emissivity=0,convection=0)
    cold=900.;seconds=12.;alpha=m.conductivity/(m.density*m.cp);Ste=m.cp*(m.solidus-cold)/m.latent_heat
    lam=brentq(lambda z:np.sqrt(np.pi)*z*np.exp(z*z)*erf(z)-Ste,1e-6,3)
    exact=2*lam*np.sqrt(alpha*seconds);results=[]
    for dx in (.00025,.000125):
        n=int(.014/dx);edge=np.ones(n-1)*m.conductivity/dx
        K=diags([np.r_[edge,0]+np.r_[0,edge],-edge,-edge],[0,-1,1],format='csr')
        mass=np.full(n,m.density*dx);h=m.enthalpy(np.full(n,m.liquidus));bed=np.zeros(n);bed[0]=1
        dt=.05
        for _ in range(round(seconds/dt)):
            h,_=heat_solve(m,h,mass,K,np.zeros(n),np.full(n,293.15),dt,bed,2*m.conductivity/dx,cold)
        # Integral liquid depletion is less sensitive than one cell threshold.
        front=float(np.sum(m.solid(m.temperature(h)))*dx);results.append(dict(dx=dx,front=front,relativeError=abs(front-exact)/exact))
    assert results[-1]['relativeError']<.09,results
    assert results[-1]['relativeError']<=results[0]['relativeError']+.015,results
    return dict(analyticFrontM=exact,grids=results)


def fracture():
    m=Material();rows=[]
    for dx in (.004,.008,.016):
        e0=m.tensile_strength/m.young;ef=m.fracture_energy/(m.tensile_strength*dx)-e0/2
        e=np.linspace(0,e0+18*ef,100000);history,damage=tensile_damage(np.zeros_like(e),np.zeros_like(e),e*m.young,m.young,m.tensile_strength,m.fracture_energy,dx)
        stress=(1-damage)*m.young*e
        # Includes elastic loading before initiation, not just the tail.
        energy=float(np.trapezoid(stress,e)*dx)
        rows.append(dict(dx=dx,softeningEnergyJPerM2=energy,relativeError=abs(energy-m.fracture_energy)/m.fracture_energy))
    assert max(r['relativeError'] for r in rows)<1e-6
    # At unchanged load history, damage must not increase each timestep.
    h,d=tensile_damage(np.array([e0*2]),np.array([.2]),np.array([0.]),m.young,m.tensile_strength,m.fracture_energy,.01)
    h2,d2=tensile_damage(h,d,np.array([0.]),m.young,m.tensile_strength,m.fracture_energy,.01)
    assert np.allclose(d,d2)
    return dict(lengthTests=rows,noDamageAtUnloadedRepeat=bool(np.allclose(d,d2)))


def gravity():
    x=block([.01,.01,.04],[.04,.04,.07],.01);dt=.003
    s=MPM(x,.01,.02,temperature=1500,origin=[-.04]*3,shape=[9]*3,ground=False)
    r=s.step(dt,thermal=False)
    expected=np.array([0.,0.,-9.81*dt]);error=float(np.max(np.linalg.norm(s.v-expected,axis=1)))
    assert error<2e-7,(error,r)
    return dict(velocityErrorMPerS=error,mechanicalResidual=r['mechanicalResidual'],massErrorKg=float(s.mass.sum()-s.initial_mass))


def shear_decay():
    # Actual 3D MPM strain operator, with an independent analytic shear mode.
    from scipy.sparse.linalg import factorized
    from scipy.sparse import coo_matrix
    L=.08;rho=2700.;eta=150.;dt=.0001;duration=.012;results=[]
    exact=float(np.exp(-eta/rho*np.pi**2*duration/L**2))
    for dx in (.01,.005,.0025):
        spacing=dx/2
        x=block([0,0,0],[L,4*dx,4*dx],spacing);origin=np.full(3,-2*dx);shape=np.array([round(L/dx)+5,9,9])
        ids,w,g,dp=basis(x,dx,origin,shape);nodes=int(np.prod(shape));mass=np.full(len(x),rho*spacing**3)
        gm,_,_=p2g(ids,w,dp,mass,np.zeros_like(x),np.zeros((len(x),3,3)),np.zeros(len(x)),nodes)
        ai=np.flatnonzero(gm>1e-15);ix=np.full(nodes,-1,dtype=int);ix[ai]=np.arange(len(ai));local=ix[ids]
        assert local.min()>=0
        _,Bdev,_=strain_matrix(local,g,len(ai));xyz=origin+np.array(np.unravel_index(ai,shape)).T*dx
        M=diags(np.repeat(gm[ai],3));A=M+Bdev.T@diags(np.full(len(x)*6,2*dt*eta*spacing**3))@Bdev
        free=np.zeros(len(ai)*3,dtype=bool);free[1::3]=(xyz[:,0]>1e-8)&(xyz[:,0]<L-1e-8)
        # Quadratic B-splines need odd ghost extension. Zeroing only nodal
        # values allows nonzero interpolated wall velocity (a slip error).
        fi=np.flatnonzero(free);unknown={int(j):i for i,j in enumerate(fi)}
        lookup={tuple(np.round(q/dx).astype(int)):i for i,q in enumerate(xyz)}
        rr=list(fi);cc=list(range(len(fi)));dd=[1.]*len(fi)
        for i,q in enumerate(xyz):
            if q[0]<-1e-8 or q[0]>L+1e-8:
                mirror=q.copy();mirror[0]=-q[0] if q[0]<0 else 2*L-q[0]
                j=lookup[tuple(np.round(mirror/dx).astype(int))]*3+1
                rr.append(i*3+1);cc.append(unknown[j]);dd.append(-1.)
        S=coo_matrix((dd,(rr,cc)),shape=(len(ai)*3,len(fi))).tocsr()
        reducedM=S.T@M@S;solve=factorized((S.T@A@S).tocsc())
        z=np.sin(np.pi*xyz[fi//3,0]/L);u=S@z;initial=u.copy()
        for _ in range(round(duration/dt)):z=solve(reducedM@z)
        u=S@z
        ratio=float(np.sum(gm[ai]*u[1::3]*initial[1::3])/np.sum(gm[ai]*initial[1::3]**2))
        results.append(dict(dx=dx,measuredAmplitude=ratio,relativeError=abs(ratio-exact)/exact))
    assert results[-1]['relativeError']<.04,results
    assert results[2]['relativeError']<results[1]['relativeError']<results[0]['relativeError'],results
    return dict(analyticAmplitude=exact,grids=results)


def coupled_cooling():
    x=block([.01,.01,.01],[.04,.04,.04],.01)
    s=MPM(x,.01,.02,temperature=1424,origin=[-.04]*3,shape=[9]*3,gravity=(0,0,0),ground=False)
    rows=[]
    for _ in range(4):rows.append(s.step(.2))
    assert rows[-1]['meanSolidFraction']>0
    assert rows[-1]['thermalBalanceRelative']<1e-8
    return dict(final=rows[-1],ledger=s.ledger)


def liquid_memory():
    x=block([.01,.01,.03],[.05,.05,.07],.01)
    s=MPM(x,.01,.02,temperature=1500,origin=[-.04]*3,shape=[10]*3,gravity=(0,0,0),ground=False)
    s.v[:,1]=.05*np.sin((x[:,0]-.01)/.04*np.pi)
    initial=float(np.sum(s.mass*np.sum(s.v*s.v,axis=1))*.5);rows=[]
    for _ in range(12):
        s.step(.002,thermal=False)
        rows.append(float(np.sum(s.mass*np.sum(s.v*s.v,axis=1))*.5))
    assert np.max(abs(s.deviator))==0,'A completely liquid particle retained elastic stress'
    assert max(rows)<=initial*(1+1e-6) and rows[-1]<=rows[0],rows
    return dict(initialKineticJ=initial,finalKineticJ=rows[-1],storedElasticStressPa=float(abs(s.deviator).max()))


def contact():
    x=block([.01,.01,.0025],[.04,.04,.0225],.005)
    s=MPM(x,.005,.01,temperature=1500,origin=[-.04]*3,shape=[14]*3,ground=True)
    s.v[:,2]=-.08
    for _ in range(30):s.step(.004,thermal=False)
    penetration=float(max(0,-s.x[:,2].min()))
    energy=float(np.sum(s.mass*(.5*np.sum(s.v*s.v,axis=1)+9.81*s.x[:,2])))
    initial=float(np.sum(s.mass*(.5*.08**2+9.81*x[:,2])))
    assert penetration<1e-10 and energy<initial*1.02,(penetration,energy,initial)
    return dict(penetrationM=penetration,initialMechanicalJ=initial,finalMechanicalJ=energy,groundImpulseNs=s.ledger['ground_impulse'])


def fragment_contact():
    from lava_mpm_fracture import mechanical_fields,contact_fields
    x=np.r_[block([-.02,-.01,.03],[0,.01,.05],.005),block([0,-.01,.03],[.02,.01,.05],.005)]
    labels=np.repeat([0,1],len(x)//2);dx=.01
    ids,w,g,dp=basis(x,dx,np.array([-.05,-.04,0]),np.array([12]*3))
    grid,fields,local=mechanical_fields(ids,labels);mass=np.full(len(x),2700*.005**3)
    v=np.zeros_like(x);v[:,0]=np.where(labels==0,.1,-.1)
    gm,mom,_=p2g(local,w,dp,mass,v,np.zeros((len(x),3,3)),np.zeros(len(x)),len(grid));u=mom/np.maximum(gm[:,None],1e-30)
    count,energy,error,heat=contact_fields(grid,fields,local,w,g,mass,u,gm,dx,2700.)
    assert count>0 and error<1e-12 and energy>0
    assert abs(energy-heat.sum())<1e-12
    # Separating surfaces must not be pulled back together by the contact.
    v[:,0]*=-1;gm,mom,_=p2g(local,w,dp,mass,v,np.zeros((len(x),3,3)),np.zeros(len(x)),len(grid));u=mom/np.maximum(gm[:,None],1e-30)
    count2,_,error2,_=contact_fields(grid,fields,local,w,g,mass,u,gm,dx,2700.)
    assert count2==0,(count2,error2)
    return dict(approachingImpulses=count,separatingImpulses=count2,momentumError=error,dissipatedEnergyJ=energy)


def melting_reset():
    x=block([.01,.01,.03],[.04,.04,.06],.01)
    s=MPM(x,.01,.02,temperature=1500,origin=[-.04]*3,shape=[10]*3,gravity=(0,0,0),ground=False)
    s.deviator[:,0]=1e4;s.deviator[:,1]=-1e4
    s.step(.001,thermal=False)
    assert abs(s.deviator).max()==0
    return dict(remainingSolidStressPa=float(abs(s.deviator).max()))


def fracture_topology():
    from lava_mpm_fracture import Connectivity
    x=block([-.02,-.01,.03],[.02,.01,.05],.005);n=len(x);network=Connectivity(n)
    solid=np.ones(n);damage=np.zeros(n);direction=np.tile([1.,0.,0.],(n,1))
    before=network.update(x,solid,damage,direction,.005).copy()
    assert len(np.unique(before))==1
    damage[abs(x[:,0])<.003]=1
    after=network.update(x,solid,damage,direction,.005).copy()
    assert len(np.unique(after))==2,len(np.unique(after))
    assert len(np.unique(after[x[:,0]<0]))==1 and len(np.unique(after[x[:,0]>0]))==1
    # Complete remelting and re-solidification forms new connectivity.
    network.update(x,np.zeros(n),np.zeros(n),direction,.005)
    refrozen=network.update(x,solid,np.zeros(n),direction,.005)
    assert len(np.unique(refrozen))==1
    return dict(intactFields=1,fracturedFields=2,refrozenFields=1)


def implicit_fragment_contact():
    from lava_mpm_fracture import implicit_contact
    from scipy.sparse import csr_matrix
    A=diags([1.,1.,1.,2.,2.,2.]);rhs=np.array([.1,0,0,-.2,0,0]);S=diags(np.ones(6));C=csr_matrix([[1.,0,0,-1.,0,0]])
    v,res,multipliers,loss,it=implicit_contact(A,rhs,S,C,1e-12)
    exact=-.1/3
    assert abs(v[0]-exact)<1e-10 and abs(v[3]-exact)<1e-10 and multipliers[0]>0
    assert abs(v[0]+2*v[3]+.1)<1e-12
    # High stiffness must not change the validity of the constraint solve.
    v2,res2,_,_,_=implicit_contact(A*1e10,rhs,S,C,1e-16)
    assert res2<1e-8 and np.isfinite(v2).all()
    return dict(velocity=v[[0,3]].tolist(),expectedVelocity=exact,residual=res,stiffResidual=res2,objectiveLossJ=loss)


def solid_collision_scene():
    from scipy.spatial import cKDTree
    left=block([-.02,-.01,.03],[0,.01,.05],.005);right=block([0,-.01,.03],[.02,.01,.05],.005);x=np.r_[left,right]
    s=MPM(x,.005,.01,temperature=1000,origin=[-.05,-.04,0],shape=[12]*3,gravity=(0,0,0),ground=False)
    group=np.repeat([0,1],len(x)//2);pairs=cKDTree(x).query_pairs(.005*1.82,output_type='ndarray');pairs=pairs[group[pairs[:,0]]==group[pairs[:,1]]]
    s.connectivity.edges=pairs;s.connectivity.broken=np.zeros(len(pairs),dtype=bool);s.connectivity.frozen[:]=True
    s.v[:,0]=np.where(group==0,.01,-.01)
    initial=float(np.sum(s.mass*np.sum(s.v*s.v,axis=1))*.5);maximum=0;contacts=0
    for _ in range(12):
        row=s.step(.002,thermal=False);contacts+=row['contactImpulses'];maximum=max(maximum,row['maximumSpeed'])
    kinetic=float(np.sum(s.mass*np.sum(s.v*s.v,axis=1))*.5)
    assert contacts>0 and maximum<.025 and kinetic<=initial*1.01,(contacts,maximum,kinetic,initial)
    return dict(initialKineticJ=initial,finalKineticJ=kinetic,maximumSpeed=maximum,contactConstraints=contacts,maximumMomentumError=max(r['contactMomentumError'] for r in s.rows))


def bed_exchange():
    from lava_mpm_bed import Bed
    bed=Bed(origin=(-.04,-.04,-.03),shape=(8,8,3),dx=.01)
    x=block([-.015,-.015,.0025],[.015,.015,.0225],.005)
    s=MPM(x,.005,.01,temperature=1450,origin=[-.04,-.04,-.03],shape=[10,10,12],gravity=(0,0,0),ground=True)
    for _ in range(5):s.step(.05,bed=bed);row=bed.advance(.05)
    mismatch=abs(s.ledger['bed']-bed.received)
    assert mismatch<1e-8 and bed.temperature.max()>293.15
    return dict(exchangeMismatchJ=mismatch,bed=row)


TESTS=dict(transfers=transfers,enthalpy=enthalpy,insulated_heat=insulated_heat,stefan=stefan,fracture=fracture,gravity=gravity,shear_decay=shear_decay,coupled_cooling=coupled_cooling,liquid_memory=liquid_memory,contact=contact,fragment_contact=fragment_contact,melting_reset=melting_reset,fracture_topology=fracture_topology,implicit_fragment_contact=implicit_fragment_contact,solid_collision_scene=solid_collision_scene,bed_exchange=bed_exchange)
def main(names):
    out=ROOT/'validation';out.mkdir(parents=True,exist_ok=True);allrows={};failed=False
    for name in names:
        t=time.time()
        try:row=dict(status='pass',evidence=TESTS[name]())
        except Exception as e:row=dict(status='fail',error=str(e),traceback=traceback.format_exc());failed=True
        row['seconds']=time.time()-t;allrows[name]=row;(out/f'{name}.json').write_text(json.dumps(row,indent=2));print(name,row['status'],round(row['seconds'],3),str(row.get('error',''))[:500],flush=True)
    if failed:raise SystemExit(1)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tests',nargs='*',default=list(TESTS));a=p.parse_args();main(a.tests)
