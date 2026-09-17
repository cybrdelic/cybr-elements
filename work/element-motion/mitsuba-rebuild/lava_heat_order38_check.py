"""Heat integration accuracy against an independent high-accuracy ODE."""
import json
import numpy as np
from scipy.integrate import solve_ivp
from scipy.sparse import csr_matrix
from lava_mpm import Material,ROOT,heat_solve
from lava_mpm_heat38 import heat_solve_trbdf2

m=Material();mass=np.array([.001]);area=np.array([.001]);K=csr_matrix((1,1));h0=np.array([m.enthalpy(1500.)])
def rate(t,h):
    temperature=m.temperature(h)
    return -(m.emissivity*5.670374419e-8*area*(temperature**4-m.ambient**4)+m.convection*area*(temperature-m.ambient))/mass
ref=solve_ivp(rate,(0,3),h0,rtol=1e-11,atol=1e-7,method='DOP853').y[:,-1]
rows=[]
for method in [heat_solve,heat_solve_trbdf2]:
    errors=[]
    for n in [30,60,120]:
        h=h0.copy();ledger=0.;max_balance=0.
        for _ in range(n):
            h,r=method(m,h,mass,K,area,m.ambient,3/n)
            ledger+=float(np.sum(r['radiation']+r['convection']));max_balance=max(max_balance,abs(r['balance']))
        err=float(abs(m.temperature(h)-m.temperature(ref))[0]);errors.append(err)
        assert abs(float(mass@(h-h0))+ledger)<1e-6 and max_balance<1e-7
    rows.append(dict(method=method.__name__,temperatureErrorsK=errors))
assert rows[1]['temperatureErrorsK'][-1]<rows[0]['temperatureErrorsK'][-1]/10
assert rows[1]['temperatureErrorsK'][-1]<.01
report=dict(status='pass',referenceTemperatureK=float(m.temperature(ref)[0]),cases=rows,enthalpyLedgerConserved=True)
(ROOT/'rebuild-38/heat-order-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
