"""Matched-frame evidence for the emitter sampling correction; no rendering."""
from pathlib import Path
import json,numpy as np
from scipy.ndimage import gaussian_filter
R=Path(__file__).resolve().parent/'lava-focus/renders'
result={}
for label,stem in [('before','no-lines'),('after','clean-light')]:
 a=np.load(R/f'{stem}-detail-0029-640-16spp-raw-aov.npz')
 patch=a['color'][220:330,380:550];luma=patch@np.array([.2126,.7152,.0722]);residual=luma-gaussian_filter(luma,3)
 result[label]={'meanLuminance':float(luma.mean()),'highFrequencyResidualRMS':float(np.sqrt(np.mean(residual**2))),'samplesPerPixel':16}
result['residualReduction']=1-result['after']['highFrequencyResidualRMS']/result['before']['highFrequencyResidualRMS']
result['scope']='One fixed cold-surface patch, same mesh, camera, illumination, and sample count. This measures noise reduction, not material realism.'
(R/'sampling-review.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
