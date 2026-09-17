"""Failure-path checks for pressure deadlines and checkpoint integrity."""
import tempfile,json,time
from pathlib import Path
from unittest.mock import patch
import numpy as np
from scipy.sparse import eye
from lava_mpm import MPM,block,ROOT
from lava_mpm_sparse_pressure import contact

try:
    contact(eye(3),np.ones(3),eye(3),eye(3),1.,deadline=time.monotonic()-1)
    raise AssertionError('An expired pressure solve proceeded')
except TimeoutError:pass

if True:
    # tempfile's restrictive Windows ACL cannot be used by this workspace
    # runner. Keep the tiny failure fixture in the normal writable tree.
    p=ROOT/'rebuild-38/process-io-check';p.mkdir(parents=True,exist_ok=True)
    s=MPM(block([0,0,0],[.002,.002,.002],.001),.001,.002,ground=False)
    s.save(p);old_data=(p/'state.npz').read_bytes();old_meta=(p/'state.json').read_bytes()
    s.time=1.;s.x+=.001
    original=Path.write_text
    def fail_metadata(path,*args,**kwargs):
        if path.name=='state.partial.json':raise OSError('Injected disk-full failure')
        return original(path,*args,**kwargs)
    with patch.object(Path,'write_text',fail_metadata):
        try:s.save(p);raise AssertionError('Expected write failure')
        except OSError:pass
    assert (p/'state.npz').read_bytes()==old_data and (p/'state.json').read_bytes()==old_meta
    assert MPM.load(p).time==0.
    meta=json.loads(old_meta);meta['time']=99;(p/'state.json').write_text(json.dumps(meta))
    try:MPM.load(p);raise AssertionError('Mixed checkpoint accepted')
    except ValueError:pass
report=dict(status='pass',expiredPressureSolveRejected=True,failedWritePreservesAcceptedCheckpoint=True,mixedCheckpointRejected=True)
(ROOT/'rebuild-38/process-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
