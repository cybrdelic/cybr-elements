"""Implicit secant iteration for irreversible damage and MPM momentum.

Each trial starts from the same physical state/time. Trial damage is a
nonlinear unknown, not an initial crack prescription. Momentum is re-solved
with its surviving stiffness and released connectivity before committing.
External reservoirs, histories, and ledgers advance exactly once.
"""
from copy import deepcopy
import time
import numpy as np


def tensile_dissipation(history,material,length):
    """Analytic dissipated work of the declared uniaxial softening law."""
    e0=material.tensile_strength/material.young
    ef=material.fracture_energy/(material.tensile_strength*length)-e0/2
    if np.any(ef<=0):raise ValueError('Unresolved fracture process-zone energy')
    e=np.maximum(history,e0);tail=np.exp(-(e-e0)/ef)
    work=.5*material.young*e0**2+material.tensile_strength*ef*(1-tail)
    stored=.5*material.tensile_strength*tail*e
    return np.where(history>e0,np.maximum(work-stored,0),0.)


def step(s,dt,*,bed=None,gas=None,tolerance=1e-5,max_iterations=18,**kwargs):
    begin=time.time();base=deepcopy(s);damage=base.damage.copy();direction=base.principal_direction.copy()
    calls=0
    for iteration in range(max_iterations):
        candidate=deepcopy(base);trial_bed=deepcopy(bed);trial_gas=deepcopy(gas)
        # The nonlinear stiffness iterate is separate from committed damage
        # and history. Iteration is allowed to retract a trial prediction;
        # physical irreversibility is enforced against the start-of-step
        # state, not against earlier nonlinear solver guesses.
        candidate.principal_direction=direction.copy()
        row=candidate.step(dt,bed=trial_bed,gas=trial_gas,damage_iterate=damage,**kwargs);calls+=1
        error=float(np.max(abs(candidate.damage-damage)))
        if error<=tolerance:break
        damage=candidate.damage.copy()
        direction=candidate.principal_direction.copy()
    else:
        raise RuntimeError(('Implicit damage/momentum iteration did not converge',dict(dt=dt,iterations=calls,residual=error)))
    # The trial ledger only saw its last damage increment. Replace it with
    # the integrated irreversible work over this entire physical step.
    length=1/np.sqrt(np.sum((candidate.principal_direction/s.cell_size)**2,axis=1))
    old=tensile_dissipation(base.history,s.material,length)
    new=tensile_dissipation(candidate.history,s.material,length)
    dissipated=float(np.sum(base.volume*np.maximum(new-old,0)))
    candidate.ledger['fracture']=base.ledger['fracture']+dissipated
    t=candidate.material.temperature(candidate.h)
    candidate.connectivity.update(candidate.x,candidate.material.solid(t),candidate.damage,candidate.principal_direction,candidate.sample_size,candidate.coherent_fraction)
    row['fractureEnergyJ']=dissipated;row['damageCorrectorIterations']=calls;row['damageCorrectorResidual']=error;row['seconds']=time.time()-begin
    row['brokenConnectivityEdges']=int(candidate.connectivity.broken.sum())
    s.__dict__.clear();s.__dict__.update(candidate.__dict__)
    for actual,trial in ((bed,trial_bed),(gas,trial_gas)):
        if actual is not None:
            actual.__dict__.clear();actual.__dict__.update(trial.__dict__)
    return row
