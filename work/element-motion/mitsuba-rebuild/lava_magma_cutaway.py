"""Expose the hot interior by removing the near-side crust, on CPU."""
from pathlib import Path
import os,json
os.environ.update(CUDA_VISIBLE_DEVICES='-1',OPENBLAS_NUM_THREADS='1')
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from lava_stages_build import compact,save,R,O
from lava_breakout_cpu import noise,smooth
a=dict(np.load(R/'crust-volume/blocks-01.npz'));v=a['v'];f=a['f'];e=np.r_[f[:,[0,1]],f[:,[1,2]],f[:,[2,0]]]
adj=coo_matrix((np.ones(len(e),'u1'),(e[:,0],e[:,1])),shape=(len(v),len(v))).tocsr();_,labels=connected_components(adj,directed=False)
keep=a['component']==0
for label in np.unique(labels[~keep]):
 mask=labels==label;p=v[mask].mean(0)
 if p[1]>.0 or p[0]<-.64:keep[mask]=True
b=compact(a,f[keep[f].all(1)]);core=b['component']==0
# Broad exposed thermal boundary, with a hotter interior toward the rear.
b['temperature'][core]=1370+95*smooth(b['v'][core,1]*3+.65)+12*noise(b['rest'][core],7,495)
save('magma',b)
(O/'magma-cutaway.json').write_text(json.dumps({'view':'Illustrative cutaway: near-side crust omitted to expose the hot interior','not':'A photograph of underground magma or an eruption/cavity mechanics simulation'},indent=2))
print(json.dumps({'vertices':len(b['v']),'triangles':len(b['f']),'path':str(O/'magma.npz')}))
