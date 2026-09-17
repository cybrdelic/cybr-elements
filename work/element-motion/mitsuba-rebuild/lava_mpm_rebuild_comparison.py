"""Matched three-level short load comparison; full breakup is a separate gate."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import json,time
import numpy as np
from lava_mpm import ROOT,SOURCE_HASHES
from lava_mpm_rebuild_timestep import run


def main():
    states=[];runs=[]
    for dt in (.002,.001,.0005):
        s,r=run(850.,dt,.02,False);states.append(s);runs.append(r)
    comparisons=[]
    for a,b in zip(states[:-1],states[1:]):
        mass=b.mass;velocity=float(np.sqrt(np.sum(mass[:,None]*(a.v-b.v)**2)/max(np.sum(mass[:,None]*b.v**2),1e-30)))
        wa=a.ledger['prescribed_boundary_work'];wb=b.ledger['prescribed_boundary_work']
        comparisons.append(dict(velocityRelative=velocity,positionM=float(np.linalg.norm(a.x-b.x,axis=1).max()),damageAbsolute=float(abs(a.damage-b.damage).max()),workRelative=abs(wa-wb)/abs(wb)))
    gates=dict(completed=all(r['complete'] for r in runs),work=all(q['workRelative']<.05 for q in comparisons),velocity=all(q['velocityRelative']<.05 for q in comparisons),position=all(q['positionM']<5e-6 for q in comparisons),damage=all(q['damageAbsolute']<.005 for q in comparisons),decreasingWorkError=comparisons[1]['workRelative']<comparisons[0]['workRelative'])
    out=dict(status='pass' if all(gates.values()) else 'fail',gates=gates,runs=runs,comparisons=comparisons,sourceHashes=SOURCE_HASHES,
        scope='Tensile loading through approximately 25% continuum damage. Not full crack separation, natural lava breakup or a rerun of structure-23.',
        fullFractureValidated=False)
    (ROOT/'rebuild-24/short-temporal-validation.json').write_text(json.dumps(out,indent=2));print(json.dumps(dict(status=out['status'],comparisons=comparisons)))


if __name__=='__main__':main()
