"""Bounded CPU regressions for topology, source identity and boundary loading."""
import importlib,json,numpy as np
from scipy.sparse import eye,csr_matrix
from lava_mpm import ROOT
from lava_mpm_loading import prescribe
from lava_mpm_fracture import Connectivity


def main():
    names=['lava_mpm_inlet_check','lava_mpm_floor_check','lava_mpm_rect_check',
        'lava_mpm_bond_check','lava_mpm_crust_check','lava_mpm_local_check',
        'lava_mpm_boundary_check','lava_mpm_transition_check','lava_mpm_surface_check']
    for name in names:
        importlib.import_module(name).main()
    # Exact independent composition of a prescribed velocity with a
    # reflected boundary. Compatible duplicate constraints must agree.
    S=csr_matrix([[1.,0],[-1.,0],[0,1.]]);lift=np.array([0.,0.,.2])
    Q,b=prescribe(S,lift,np.array([1,1,0],bool),np.array([.3,-.3,0.]))
    assert np.allclose(Q@np.array([.4])+b,[.3,-.3,.6])
    try:prescribe(S,lift,np.array([1,1,0],bool),np.array([.3,.3,0.]))
    except ValueError:pass
    else:raise AssertionError('Conflicting boundary accepted')
    c=Connectivity(2);labels=c.update(np.array([[0.,0,0],[1.,0,0]]),np.array([1.,0.]),np.zeros(2),np.tile([1.,0,0],(2,1)),.01,.65)
    assert c.frozen.tolist()==[True,False] and labels[0]!=labels[1]
    result=dict(status='pass',reflectedGripComposition=True,conflictingGripsRejected=True,isolatedSolidSeparatedFromMelt=True)
    (ROOT/'validation/material_boundary_topology.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))


if __name__=='__main__':main()
