"""One bounded CPU regression run; receipts identify the tested source."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2',NUMBA_NUM_THREADS='2')
import hashlib,json,time,traceback
from pathlib import Path
from lava_mpm import ROOT,SOURCE_HASHES
import lava_mpm_rebuild_check as revised
import lava_mpm_validate as baseline


def main():
    tests={name:getattr(revised,name) for name in ('creep','phase','friction','pressure','transfers','coupled','collision','surface')}
    tests.update({'baseline_'+name:baseline.TESTS[name] for name in ('transfers','enthalpy','insulated_heat','stefan','fracture','gravity','shear_decay','coupled_cooling','liquid_memory','melting_reset','bed_exchange')})
    reports={};start=time.time()
    for name,fn in tests.items():
        before=time.time()
        try:r=dict(status='pass',details=fn())
        except Exception as exc:r=dict(status='fail',error=str(exc),traceback=traceback.format_exc(limit=5))
        r['wallSeconds']=time.time()-before;reports[name]=r;print(name,r['status'],round(r['wallSeconds'],2),flush=True)
    status='pass' if all(r['status']=='pass' for r in reports.values()) else 'fail'
    report=dict(status=status,tests=reports,sourceHashes=SOURCE_HASHES,wallSeconds=time.time()-start,device='CPU',gpuUsed=False)
    path=ROOT/'rebuild-24/component-validation.json';path.write_text(json.dumps(report,indent=2));print(str(path))
    raise SystemExit(status!='pass')


if __name__=='__main__':main()
