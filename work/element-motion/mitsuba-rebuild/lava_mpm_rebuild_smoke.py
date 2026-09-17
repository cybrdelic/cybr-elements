"""Final boundary, compatibility and production-gate checks. CPU only."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import json,traceback,time
from pathlib import Path
from lava_mpm import ROOT,SOURCE_HASHES


def main():
    import lava_mpm_admm_check,lava_mpm_local_check,lava_mpm_transition_check
    from lava_mpm_validate import contact
    from lava_mpm_surface import extract
    from lava_mpm_render_gate import inspect_surface
    functions={'sparse_contact':lava_mpm_admm_check.main,'partial_crack_transfer':lava_mpm_local_check.main,'phase_transition':lava_mpm_transition_check.main,'liquid_ground':contact}
    results={}
    for name,fn in functions.items():
        t=time.time()
        try:fn();result=dict(status='pass')
        except Exception as exc:result=dict(status='fail',error=str(exc),traceback=traceback.format_exc(limit=4))
        result['wallSeconds']=time.time()-t;results[name]=result;print(name,result['status'],flush=True)
    try:
        surface=extract(ROOT/'rebuild-24/tension-850-0.001/state.npz',method='material');gate=inspect_surface(surface)
        assert gate['status']=='blocked' and not gate['checks']['productionScene'] and not gate['checks']['validatedConfiguration']
        results['production_gate']=dict(status='pass',gate=gate)
    except Exception as exc:results['production_gate']=dict(status='fail',error=str(exc),traceback=traceback.format_exc(limit=4))
    result=dict(status='pass' if all(q['status']=='pass' for q in results.values()) else 'fail',tests=results,sourceHashes=SOURCE_HASHES)
    path=ROOT/'rebuild-24/integration-validation.json';path.write_text(json.dumps(result,indent=2));print(json.dumps(dict(status=result['status'],path=str(path))))
    raise SystemExit(result['status']!='pass')


if __name__=='__main__':main()
