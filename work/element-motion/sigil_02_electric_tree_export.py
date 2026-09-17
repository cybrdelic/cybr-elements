"""Export cached 3D Laplacian-growth trees with correct branch-current hierarchy."""
from pathlib import Path
import numpy as np,json
R=Path(__file__).resolve().parent;O=R/'sigil-02-active-elements/lightning';families=[]
for family in range(5):
 segments=[]
 for event in range(30):
  net=np.load(R/'sigil-02-repair'/f'discharge-train-{family}-{event:02}.npz');p=net['points'];parent=net['parent'];strength=net['strength'];children=[[] for _ in p]
  for j in range(1,len(p)):
   if strength[j]>.012:children[parent[j]].append(j)
  roots=[j for j in range(len(p)) if children[j] and (j==0 or len(children[parent[j]])!=1 or strength[j]<=.012)]
  for root in roots:
   for child in children[root]:
    ids=[root,child];k=child
    while len(children[k])==1:k=children[k][0];ids.append(k)
    # The shared trunk attachment does not carry trunk current into a fork.
    amp=float(max(strength[ids[1:]]));segments.append(dict(points=p[ids].tolist(),radius=.0035*max(.15,amp**.55),power=amp,group=int(np.clip((p[ids,0].mean()+4.1)/8.2*6,0,5))))
 families.append(segments)
(O/'channels.json').write_text(json.dumps(dict(families=families,source='Cached 3D Laplacian-growth trees in the approved 02 control volume; branch power excludes shared trunk root',segments=[len(s) for s in families])))
print('Exported branch current hierarchy:',[sum(s['power']>.5 for s in paths) for paths in families],'main channels')
