"""Damped power-creep return map against a bracketed scalar root."""
import json,numpy as np
from scipy.optimize import brentq
from lava_mpm import Material,ROOT
m=Material(rheology='basalt_power_creep');rows=[];omega=2/(m.rock_creep_n+1)
for temperature in [1100.,1200.,1250.]:
    for trial in [1e7,1e9,1e10]:
        def target(sigma):return trial*float(m.network(np.array([temperature]),.2,np.array([sigma]))[2][0])
        reference=brentq(lambda q:q-target(q),0,trial,xtol=1e-6)
        guess=0.
        for i in range(200):
            value=np.log1p(target(np.expm1(guess)*1e6)/1e6)
            error=value-guess
            if abs(error)<1e-10:break
            guess+=omega*error
        result=float(np.expm1(guess)*1e6);relative=abs(result-reference)/max(reference,1.)
        assert relative<1e-7 and i<100
        rows.append(dict(temperatureK=temperature,trialStressPa=trial,iterations=i+1,relativeStressError=relative))
report=dict(status='pass',fallbackRelaxation=omega,cases=rows)
(ROOT/'rebuild-38/creep-damping-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
