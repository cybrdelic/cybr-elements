"""Small numeric snapshot of a saved CPU state; no images or large payloads."""
import argparse,json,numpy as np
from lava_mpm import MPM,ROOT
p=argparse.ArgumentParser();p.add_argument('--name',required=True);args=p.parse_args();s=MPM.load(ROOT/args.name)
T=s.material.temperature(s.h);c=np.linalg.norm(s.C,axis=(1,2));i=c.argmax();speed=np.linalg.norm(s.v,axis=1)
top=s.rest[:,2]>np.quantile(s.rest[:,2],.8);bottom=s.rest[:,2]<np.quantile(s.rest[:,2],.2)
out=dict(time=s.time,particles=len(s.x),maximumSpeed=float(speed.max()),Cpercentile=np.quantile(c,[.5,.9,.99,1]).tolist(),outlier=dict(index=int(i),position=s.x[i].tolist(),velocity=s.v[i].tolist(),temperature=float(T[i]),solid=float(s.material.solid(T[i])),damage=float(s.damage[i]),C=s.C[i].tolist()),topRangeK=[float(T[top].min()),float(T[top].max())],bottomRangeK=[float(T[bottom].min()),float(T[bottom].max())])
(ROOT/args.name/'state-audit.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
