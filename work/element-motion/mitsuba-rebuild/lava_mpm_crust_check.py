"""Independent stress-relaxation and phase-limit checks for the lava crust."""
import json
import numpy as np
from lava_mpm import Material,ROOT


def main():
    m=Material(); rows=[]
    for t in (1450.,1370.,1300.,1200.,1050.):
        dt=.01; mu,fluidity,relax,coefficient=m.network(np.array([t]),dt)
        initial=1.e5 if mu[0]>0 else 0.; stress=initial
        for _ in range(100):stress*=float(relax[0])
        exact=initial*np.exp(-float(mu[0]*fluidity[0]))
        if float(m.solid(t))>=m.crystal_lock_fraction:
            assert stress==initial and fluidity[0]==0
        if t>=m.liquidus:assert mu[0]==0 and coefficient[0]==0
        rows.append(dict(temperatureK=t,solidFraction=float(m.solid(t)),initialShearPa=initial,afterOneSecondPa=stress,analyticAfterOneSecondPa=exact,networkFluidity=float(fluidity[0])))
    # A finite-viscosity Maxwell material at a less stiff material scale:
    # backward Euler must converge to its independently known exponential.
    q=Material(young=1.e5); t=np.array([1350.]); mu,b,_,_=q.network(t,.01); exact=float(np.exp(-mu[0]*b[0])); errors=[]
    for dt in (.02,.01,.005):
        _,_,relax,_=q.network(t,dt); measured=float(relax[0]**round(1/dt));errors.append(abs(measured-exact))
    assert errors[2]<errors[1]<errors[0]
    old_eta=float(m.viscosity(1200));old_mu=float(m.young/(2*(1+m.poisson))*m.solid(1200)**3)
    from lava_mpm_fracture import viscous_interfaces
    from scipy.sparse import diags
    from scipy.sparse.linalg import spsolve
    masses=np.array([2.,3.]);dt=.1;dx=.01;rho=2700.;eta=np.array([5.,50.])
    A,pairs,coef=viscous_interfaces(np.array([0,0]),masses,np.array([True,False]),eta,dx,rho,dt)
    initial_v=np.array([.4,0,0,-.2,0,0]);M=diags(np.repeat(masses,3));v=spsolve(M+A,M@initial_v)
    relative_exact=(initial_v[0]-initial_v[3])/(1+coef[0]*(1/masses[0]+1/masses[1]))
    assert abs((v[0]-v[3])-relative_exact)<1e-12
    momentum_before=(initial_v.reshape(2,3)*masses[:,None]).sum(0);momentum_after=(v.reshape(2,3)*masses[:,None]).sum(0)
    assert np.linalg.norm(momentum_before-momentum_after)<1e-12
    work=float(v@(A@v));kinetic_loss=float(.5*(initial_v@(M@initial_v)-v@(M@v)))
    assert work>0 and kinetic_loss>=work
    drag=dict(relativeVelocityError=abs(v[0]-v[3]-relative_exact),momentumError=float(np.linalg.norm(momentum_before-momentum_after)),heatJ=work,kineticLossJ=kinetic_loss)
    out=ROOT/'validation'/'crystal_network.json';out.write_text(json.dumps(dict(status='pass',old1200KRelaxationSeconds=old_eta/old_mu,new1200KRelaxation='elastic below failure',rows=rows,maxwellTimestepErrors=errors,interfaceDrag=drag,limits='Nominal crystal-packing and one-cell viscous interface closures; not composition-calibrated basalt rheology'),indent=2))
    print(json.dumps(dict(status='pass',old1200KRelaxationSeconds=old_eta/old_mu,crustStressRetention=rows[-2]['afterOneSecondPa']/rows[-2]['initialShearPa'],output=str(out))))

if __name__=='__main__':main()
