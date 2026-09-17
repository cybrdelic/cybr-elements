"""Isolated, unselected return-map experiment against independent roots.

The coupled experiment did not sufficiently reduce the global iterations;
it was reverted. This script preserves the scalar derivation for the record.
https://mooseframework.inl.gov/source/materials/PowerLawCreepStressUpdate.html
"""
import json,numpy as np
from scipy.optimize import brentq
from lava_mpm import Material,ROOT
m=Material(rheology='basalt_power_creep');rows=[]
def return_stress(t,dt,trial_stress):
    trial=np.maximum(np.asarray(trial_stress),0.)/1e6
    mu,f0,_,_=m.network(t,dt,np.zeros_like(t));a=1+dt*mu*f0
    b=dt*mu*3*m.rock_creep_a/1e6*np.exp(-m.rock_creep_q/(8.314462618*t))
    lo=np.zeros_like(trial);hi=trial/a
    for _ in range(52):
        mid=(lo+hi)*.5;below=a*mid+b*mid**m.rock_creep_n<trial
        lo=np.where(below,mid,lo);hi=np.where(below,hi,mid)
    return (lo+hi)*.5*1e6
for t in [800.,1100.,1250.,1400.,1450.]:
    for dt in [.0001,.02,.2,1.]:
        for trial in [0.,1e3,1e7,1e9,1e10]:
            target=lambda sigma:trial*float(m.network(np.array([t]),dt,np.array([sigma]))[2][0])
            expected=brentq(lambda sigma:sigma-target(sigma),0,trial,xtol=1e-8) if trial else 0.
            actual=float(return_stress(np.array([t]),dt,np.array([trial]))[0])
            relative=abs(actual-expected)/max(expected,1.)
            assert relative<1e-9 and 0<=actual<=trial
            rows.append(dict(temperatureK=t,dt=dt,trialPa=trial,relativeError=relative))
report=dict(status='pass',selectedForMainRun=False,cases=len(rows),maximumRelativeError=max(r['relativeError'] for r in rows),source='Implicit local return mapping; independent brentq roots of the original network law')
(ROOT/'rebuild-38/return-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
