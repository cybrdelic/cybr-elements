"""Closed hot nozzle must retain equilibrium and account for reservoir heat."""
import json
import numpy as np
from scipy.sparse import csr_matrix
from lava_mpm import Material,heat_solve,ROOT
from lava_mpm_inlet import thermal_boundary

m=Material();xyz=np.array([[-.02,0,0],[-.006,0,0],[.01,0,0]])
area=np.array([.0002,.0003,.0004]);air,wall=thermal_boundary(xyz,area,np.full(3,.003),dict(pipe_end=-.006))
np.testing.assert_allclose(air+wall,area,atol=1e-15)
assert air[0]==0 and wall[2]==0
mass=np.array([.001]);K=csr_matrix((1,1));temp=1450.
h,report=heat_solve(m,np.array([m.enthalpy(temp)]),mass,K,air[:1],293.15,1.,conduit_conductance=wall[:1]*1000,conduit_temperature=temp)
np.testing.assert_allclose(m.temperature(h),temp,atol=1e-10)
assert report['radiation'][0]==0 and report['convection'][0]==0
cold=np.array([m.enthalpy(1200.)]);h,report=heat_solve(m,cold,mass,K,air[:1],293.15,.5,conduit_conductance=wall[:1]*1000,conduit_temperature=temp)
assert report['conduit'][0]<0 and 1200<float(m.temperature(h)[0])<temp
error=float(abs(mass@(h-cold)+report['conduit'].sum()))
assert error<1e-7
report=dict(status='pass',partitionConservesArea=True,enclosedNozzleRetainsEquilibrium=True,reservoirEnergyErrorJ=error)
(ROOT/'rebuild-38/pipe-heat-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
