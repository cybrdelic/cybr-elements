"""Same physical solve, alternative sparse permutations; no reduced physics."""
import os,json,time,numpy as np
from lava_mpm import ROOT,MPM
from lava_mpm_continuous import HotBed
from lava_mpm_inlet import emit

def main():
    folder=ROOT/'continuous-21';results=[];states=[]
    for order in ('COLAMD','MMD_AT_PLUS_A','MMD_ATA'):
        os.environ['LAVA_CONTACT_ORDER']=order
        s=MPM.load(folder);setup=json.loads((folder/'inlet.json').read_text())
        if s.time>=setup['nextEmission']-1e-9:emit(s,setup['config'],setup['period'])
        begin=time.time();row=s.step(.004,bed=HotBed(setup['bedTemperatureK']),boundary=setup['config']);elapsed=time.time()-begin
        states.append(s);results.append(dict(order=order,seconds=elapsed,residual=row['mechanicalResidual']))
    base=states[0]
    for s,r in zip(states,results):
        r['velocityErrorMPerS']=float(np.linalg.norm(s.v-base.v,axis=1).max());r['temperatureErrorK']=float(abs(s.material.temperature(s.h)-base.material.temperature(base.h)).max())
        assert r['velocityErrorMPerS']<1e-6 and r['temperatureErrorK']<1e-4,r
    result=dict(status='pass',sourceTime=base.time-.004,results=results,limits='Permutation equivalence for one fully coupled source/contact step. No change to equations or timestep.')
    (ROOT/'validation'/'sparse_permutation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
