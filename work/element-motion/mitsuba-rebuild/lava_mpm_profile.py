"""Bounded CPU profile at the saved strong-softening event."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import cProfile, io, json, pstats, time
import numpy as np
from lava_mpm import MPM, ROOT

def grips(x):
    mask=np.zeros_like(x,dtype=bool); value=np.zeros_like(x)
    mask[:,0]=abs(x[:,0])>=.0035;value[:,0]=np.sign(x[:,0])*.0001
    return mask,value

if __name__=='__main__':
    folder=ROOT/'rebuild-25';folder.mkdir(exist_ok=True)
    s=MPM.load(ROOT/'rebuild-24'/'softening-impulse-5')
    # Compile the basis kernels once outside the measured interval.
    from lava_mpm import basis_rect,p2g
    ids,w,g,dp=basis_rect(s.x,s.cell_size,s.origin,np.array(s.shape))
    p2g(ids,w,dp,s.mass,s.v,s.C,s.h,int(np.prod(s.shape)))
    p=cProfile.Profile();start=time.time();p.enable();row=s.step(2e-6,thermal=False,node_velocity=grips);p.disable()
    p.dump_stats(str(folder/'softening.prof'))
    out=io.StringIO();pstats.Stats(p,stream=out).sort_stats('cumtime').print_stats(32)
    (folder/'softening-profile.txt').write_text(out.getvalue())
    s.save(folder/'profile-step')
    print(json.dumps(dict(wallSeconds=time.time()-start,row=row,profile=str(folder/'softening-profile.txt'))))
