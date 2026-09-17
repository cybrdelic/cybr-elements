"""Pressure line-search minima versus independent scalar optimization."""
import json
import numpy as np
from scipy.optimize import minimize_scalar
from lava_mpm_sparse_pressure import exact_step
from lava_mpm import ROOT
rng=np.random.default_rng(81);errors=[]
for _ in range(20):
    value=rng.normal(size=15);direction=rng.normal(size=15);comp=rng.uniform(.1,2,size=15)
    slope=-rng.uniform(.1,3);curvature=rng.uniform(.1,2)
    linear=slope-float(np.sum(direction*np.maximum(value,0)/comp))
    def energy(t):return linear*t+curvature*t*t/2+float(np.sum(np.maximum(value+t*direction,0)**2/(2*comp)))
    answer=exact_step(value,direction,comp,slope,curvature)
    reference=minimize_scalar(energy,bounds=(0,64),method='bounded',options={'xatol':1e-12})
    errors.append(abs(answer-reference.x));assert errors[-1]<1e-6
assert abs(exact_step(np.array([-1.]),np.array([1.]),np.array([1e-8]),-1.,1.)-1)<1e-12
report=dict(status='pass',cases=len(errors),maximumStepError=max(errors),kinkMinimumCorrect=True)
(ROOT/'rebuild-38/linesearch-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
