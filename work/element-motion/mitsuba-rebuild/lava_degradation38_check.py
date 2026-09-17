"""A saturated damage trial must not manufacture stress or heat."""
import copy,json
from unittest.mock import patch
import numpy as np
from lava_mpm import MPM,Material,block,ROOT

m=Material(rheology='basalt_power_creep')
base=MPM(block([0,0,0],[.006,.006,.006],.002),.002,.004,
         material=m,temperature=1100.,gravity=(0,0,0),ground=False,
         origin=[-.008,-.008,-.008],shape=[7,7,7])
base._accepted_damage=np.zeros(len(base.x))
base.deviator[:,0]=.5
base.deviator[:,1]=-.5
base._creep_stress_guess=np.full(len(base.x),50e6)
def target(*args,**kwargs):
    return np.full(len(base.x),.99),{}
states=[]
for d in [1.,.99999]:
    s=copy.deepcopy(base);s.damage[:]=d
    with patch('lava_mpm_phase_field.update_damage',target):
        row=s._step(.001,thermal=False)
    states.append(s)
    assert np.isfinite(s.h).all() and row['viscousHeatJ']<1e-3,row
    assert np.max(abs(s.deviator))<1e5
np.testing.assert_allclose(states[0].deviator,states[1].deviator,rtol=1e-10,atol=1e-8)
np.testing.assert_allclose(states[0].h,states[1].h,rtol=1e-12,atol=1e-8)
report=dict(status='pass',saturatedTrialsHaveIdenticalPhysicalResponse=True,
            viscousHeatJ=states[0].rows[-1]['viscousHeatJ'],
            maximumStressPa=float(abs(states[0].deviator).max()))
(ROOT/'rebuild-38/degradation-check.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
