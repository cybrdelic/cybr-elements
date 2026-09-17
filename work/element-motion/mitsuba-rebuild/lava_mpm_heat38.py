"""EXPERIMENTAL: TR-BDF2 passes the ODE test but fails the coupled scene.

Do not select this for production. The current main driver uses bounded
backward Euler with step-doubling acceptance instead.

The implicit stages use the existing nonlinear material law. Boundary heat
is integrated with the method's weights, preserving the enthalpy ledger.
An overshooting stage rejects the step; no temperature clipping is applied.
"""
import numpy as np


def heat_solve_trbdf2(m,h0,mass,K,area,gas_temperature,dt,bed_area=None,bed_conductance=0.,bed_temperature=293.15,conduit_conductance=0.,conduit_temperature=293.15):
    from lava_mpm import heat_solve
    gamma=2-np.sqrt(2.);alpha=1/(gamma*(2-gamma));beta=(1-gamma)/(2-gamma)
    t0=m.temperature(h0);ba=np.zeros_like(area) if bed_area is None else bed_area
    flux=dict(radiation=m.emissivity*5.670374419e-8*area*(t0**4-m.ambient**4),
              convection=m.convection*area*(t0-gas_temperature),
              bed=bed_conductance*ba*(t0-bed_temperature),
              conduit=conduit_conductance*(t0-conduit_temperature))
    initial_flux=K@t0+sum(flux.values());tau=gamma*dt/2
    rhs=h0-tau*initial_flux/mass
    args=(K,area,gas_temperature)
    kwargs=dict(bed_area=bed_area,bed_conductance=bed_conductance,bed_temperature=bed_temperature,
                conduit_conductance=conduit_conductance,conduit_temperature=conduit_temperature)
    mid,r1=heat_solve(m,rhs,mass,*args,tau,initial_temperature=t0,**kwargs)
    end,r2=heat_solve(m,alpha*mid-(alpha-1)*h0,mass,*args,beta*dt,initial_temperature=m.temperature(mid),**kwargs)
    bounds=np.r_[t0.ravel(),np.ravel(gas_temperature),np.ravel(bed_temperature),np.ravel(conduit_temperature),m.ambient]
    temperatures=np.r_[m.temperature(mid),m.temperature(end)]
    if temperatures.min()<bounds.min()-1e-6 or temperatures.max()>bounds.max()+1e-6:
        raise RuntimeError('TR-BDF2 heat step overshot boundary temperatures; reduce dt')
    report={key:alpha*(tau*flux[key]+r1[key])+r2[key] for key in flux}
    report.update(balance=float(mass@(end-h0)+sum(np.sum(q) for q in report.values())),iterations=r1['iterations']+r2['iterations'],scheme='TR-BDF2')
    return end,report
