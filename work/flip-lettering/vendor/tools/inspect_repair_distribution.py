"""Measure marker spacing on matched-resolution solver comparisons.

Nearest-neighbour spacing is a discretization diagnostic, not physical density
or a proof of local mass conservation. No threshold is tuned to favor a solver.
"""
from pathlib import Path
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json,numpy as np
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[1]
rows=[]
for scene in ['impact_reference_ii','impact_legacy','impact']:
 folder=ROOT/'cache'/scene;m=json.loads((folder/'manifest.json').read_text());h=m['config']['h']
 for frame in [0,24,40,48]:
  info=m['frames'][frame];n=info['particles'];a=np.fromfile(folder/f'{frame:04d}.particles',dtype='<f4')
  p=a[:n*3].reshape(n,3);distance=cKDTree(p).query(p,k=2,workers=1)[0][:,1]/h
  row={'scene':scene,'frame':frame,'physicalTime':info['time'],'particles':n,'h':h,'flipFraction':m['config']['flip'],
    'separation':m['config'].get('separation',True),'nearestNeighbourDistanceInGridSpacings':{'minimum':float(distance.min()),'q01':float(np.quantile(distance,.01)),
    'q05':float(np.quantile(distance,.05)),'median':float(np.median(distance)),'q95':float(np.quantile(distance,.95)),
    'fractionBelowQuarterCell':float(np.mean(distance<.25)),'fractionBelowTenthCell':float(np.mean(distance<.1))},
    'kineticEnergy':info['kineticEnergy'],'primarySha256':info['primarySha256']}
  rows.append(row);print(scene,frame,round(100*row['nearestNeighbourDistanceInGridSpacings']['fractionBelowQuarterCell'],2),'percent below .25h',flush=True)
result={'rows':rows,'sameGridSpacing':len(set(x['h'] for x in rows))==1,'qualification':'These are geometric marker-spacing diagnostics on three distinct trajectories with matching initial resolution and seed. They do not establish local mass conservation, physical density error, or visual superiority. Both FLIP fraction and separation change between legacy III and the repair.'}
(ROOT/'tests/repair/particle-distribution.json').write_text(json.dumps(result,indent=2))
