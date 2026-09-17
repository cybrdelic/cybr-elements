"""Analytic measured-gap width/volume and closed-crack reconstruction checks."""
import os
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='2')
import json
import numpy as np
import manifold3d as mf
from lava_mpm import ROOT
from lava_mpm_gap_surface import subtract_gaps
cube=mf.Manifold.cube([.004,.004,.004],True).to_mesh64();v=np.array(cube.vert_properties)[:,:3];f=np.array(cube.tri_verts,dtype=int)
width=.00012
a=np.array([[-width/2,-.001,-.003],[-width/2,.001,-.003],[-width/2,.001,.003],[-width/2,-.001,.003]])
b=a+[width,0,0]
vv,ff,crack,report=subtract_gaps(v,f,np.array([[a,b]]))
expected=width*.002*.004;error=abs(report['removedVolumeM3']-expected)
assert error<1e-16 and crack.any()
cut=vv[ff[crack]].reshape(-1,3)
# Gap end walls may include both x positions; none may widen the void.
width_error=max(abs(cut[:,0].min()+width/2),abs(cut[:,0].max()-width/2));assert width_error<1e-12
for other in [a,a-[width,0,0]]:
    _,_,closed,r=subtract_gaps(v,f,np.array([[a,other]]));assert not closed.any() and r['removedVolumeM3']==0
result=dict(status='pass',analyticVoidVolumeM3=expected,volumeErrorM3=error,maximumGapWidthErrorM=width_error,closedAndCompressedFacesDoNotCut=True,artificialGapWideningM=0.,limits='Geometric reconstruction of declared face gaps; not a fracture constitutive calibration.')
folder=ROOT/'rebuild-25/gap-validation';folder.mkdir(exist_ok=True);(folder/'proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
