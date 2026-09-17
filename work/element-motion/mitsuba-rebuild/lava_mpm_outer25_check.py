"""Check measured crack preservation during exterior reconstruction."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import json
import numpy as np
from lava_mpm import ROOT
from lava_mpm_material_surface import reconstruct
from lava_mpm_outer_surface import reconstruct_outer
source=ROOT/'rebuild-25/notch-0.0005-r1/state.npz';s=dict(np.load(source));meta=json.loads(source.with_suffix('.json').read_text());sample=np.array(meta['sample_size'])
mesh,original=reconstruct(s,sample);out,report=reconstruct_outer(mesh,s,sample)
crack=mesh['crack_vertices'];assert len(crack)>0
assert np.array_equal(mesh['v'][crack],out['v'][crack]) and np.array_equal(mesh['f'],out['f'])
assert abs(out['cell_volume'].sum()-s['volume'].sum())<s['volume'].sum()*1e-7
assert out['cell_volume'].min()>0
result=dict(status='pass',source=str(source),measuredOpenFacePairs=original['openFacePairs'],crackVerticesPreserved=len(crack),reconstruction=report,limits='A measured fractured laboratory specimen validates the reconstruction constraints; it is not a natural lava appearance test.')
folder=ROOT/'rebuild-25/outer-validation';folder.mkdir(exist_ok=True);(folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
