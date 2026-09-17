"""Transfer preserved basalt detail to the cached cohesive simulation."""
from pathlib import Path
import os,json,time
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
import numpy as np
from lava_cohesive_cpu import foundation,shell_mesh,O

def main():
    start=time.time();a=np.load(O/'shell-03-mechanics.npz')
    h,mask,edge,lo,s,bv,bf,bn,bt=foundation()
    sv,sf,sn,st,sr=shell_mesh(a['x'],a['f'],a['welds'],a['active'],a['rest'],detail=(h,lo,s))
    data=dict(v=np.concatenate([bv,sv]).astype('f4'),f=np.concatenate([bf,sf+len(bv)]).astype('i4'),normal=np.concatenate([bn,sn]).astype('f4'),temperature=np.r_[bt,st].astype('f4'),rest=np.concatenate([bv,sr]).astype('f4'),component=np.r_[np.zeros(len(bv)),np.ones(len(sv))].astype('u1'))
    path=O/'shell-detailed.npz';np.savez_compressed(path,**data)
    report={'sourceMechanics':'shell-03-mechanics.npz','preservedDetailSource':'../refined-lobed-02.npz','device':'CPU','seconds':round(time.time()-start,2),'vertices':len(data['v']),'triangles':len(data['f']),'method':'Cohesive crust displacement plus preserved basalt microrelief and explicit through-holes','limits':['Large tears follow the cohesive solver','Fine cooling vents remain authored from the preferred baseline','One-way foundation coupling']}
    path.with_suffix('.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))

if __name__=='__main__':main()
