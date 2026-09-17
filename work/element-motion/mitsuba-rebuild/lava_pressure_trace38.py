"""Bounded pressure diagnostics from a stored system; no simulation render."""
import os
os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import json,sys,time,argparse
from pathlib import Path
import numpy as np
from scipy.sparse import load_npz
from lava_mpm import ROOT
from lava_mpm_sparse_pressure import contact

p=argparse.ArgumentParser();p.add_argument('--mode',default='primal');a=p.parse_args();os.environ['LAVA_MPM_PRESSURE_NEWTON']=a.mode
folder=ROOT/'rebuild-38/pressure-system';v=dict(np.load(folder/'vectors.npz'));rows=[];start=time.monotonic()
def trace(frame,event,arg):
    if event=='line' and frame.f_code.co_name=='contact' and 'residual' in frame.f_locals:
        loc=frame.f_locals;i=loc.get('iteration',-1)
        if len(rows)<=i:
            rows.append(dict(iteration=i,residual=float(loc['residual']),energy=float(loc['energy']),gradient=float(np.linalg.norm(loc['g'])),active=int(np.sum(loc['value']>0)),step=loc.get('step'),wallSeconds=time.monotonic()-start))
    return trace
sys.settrace(trace);error=None
try:
    r=contact(load_npz(folder/'A.npz'),v['rhs'],load_npz(folder/'S.npz'),load_npz(folder/'C.npz'),v['compliance'],v['offset'],deadline=time.monotonic()+45)
except Exception as exc:error=repr(exc)
finally:sys.settrace(None)
report=dict(mode=a.mode,lineSearch=os.environ.get('LAVA_MPM_PRESSURE_LINESEARCH','armijo'),error=error,iterations=rows,wallSeconds=time.monotonic()-start,finalResidual=None if error else r[1])
(folder/(a.mode+'-'+report['lineSearch']+'-trace.json')).write_text(json.dumps(report,indent=2));print(json.dumps(dict(error=error,iterations=len(rows),finalResidual=report['finalResidual'],last=rows[-2:])))
