"""Use native point-charge growth, with variable-width 02 stroke regions as guidance."""
from pathlib import Path
import numpy as np,json
from scipy.ndimage import map_coordinates,label
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from skimage.morphology import medial_axis
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair';src=np.load(R/'sigil-02-v2/source.npz');lo=src['lo'];ext=src['extent'];shape=src['sdf'].shape
sk=medial_axis(src['sdf']>0,rng=2002);pts=np.argwhere(sk);lookup={tuple(p):i for i,p in enumerate(pts)};rr=[];cc=[];ww=[]
for i,(y,x) in enumerate(pts):
 for dy,dx in [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]:
  j=lookup.get((y+dy,x+dx))
  if j is not None:rr.append(i);cc.append(j);ww.append(np.hypot(dy,dx))
g=coo_matrix((ww,(rr,cc)),shape=(len(pts),len(pts))).tocsr();components,ncomp=label(sk,np.ones((3,3)));degree=np.diff(g.indptr);guides=[];spacing=ext[0]/(shape[1]-1)
for comp in range(1,ncomp+1):
 ids=np.flatnonzero(components[tuple(pts.T)]==comp)
 if len(ids)<8:continue
 ends=ids[degree[ids]<=2]
 if not len(ends):continue
 root=ids[np.argmin(pts[ids,1])];dist,pred=dijkstra(g,indices=root,return_predecessors=True)
 used=set()
 for end in ends[np.argsort(dist[ends])[::-1]]:
  path=[int(end)];node=int(end)
  while node!=root and pred[node]>=0:node=int(pred[node]);path.append(node)
  path=path[::-1]
  unseen=[j for j,k in enumerate(path) if k not in used]
  if len(unseen)*spacing<.28:continue
  # Reuse a short part of the established leader before a new branch diverges.
  first=max(0,min(unseen)-8);path=path[first:];used.update(path)
  a=pts[path];x=lo[0]+a[:,1]/(shape[1]-1)*ext[0];z=lo[2]+a[:,0]/(shape[0]-1)*ext[2]
  p=np.column_stack((x,.20*np.sin(x*1.35)+.08*np.cos(z*3),z))
  length=np.r_[0,np.cumsum(np.linalg.norm(np.diff(p,axis=0),axis=1))]
  if length[-1]<.28:continue
  samples=np.linspace(0,length[-1],max(10,round(length[-1]/.035)));p=np.column_stack([np.interp(samples,length,p[:,k]) for k in range(3)])
  widths=np.interp(samples,length,src['sdf'][tuple(a.T)])
  arrival=float(np.min(src['arrival'][tuple(a.T)]));guides.append(dict(points=p.tolist(),widths=widths.tolist(),length=float(length[-1]),birth=.25+(arrival-.3)/3.6*1.50))
guides.sort(key=lambda q:q['birth']);(O/'lightning-guides.json').write_text(json.dumps(guides));print('Guided discharge branches',len(guides))
s=(R/'bending-lightning-v5.py').read_text()
s=s.replace("B=R/'bending-rebuild-v5';OUT=B/'lightning-frames'","B=R/'sigil-02-repair';OUT=B/'lightning-frames'")
s=s.replace('EVENTS=np.array([.16,.327,.506,.744,.913,1.087,1.306,1.494,1.674,1.84])',"GUIDES=json.loads((B/'lightning-guides.json').read_text());EVENTS=np.array([g['birth'] for g in GUIDES])")
s=s.replace('CAM=np.array([1.1,-13.,2.8]);TARGET=np.array([0.,0.,1.903125])','CAM=np.array([.65,-13.,3.05]);TARGET=np.array([0.,0.,1.8])')
s=s.replace("dest=B/f'laplacian-forked-3d-{event:02}.npz'","dest=B/f'discharge-{event:02}.npz'")
start=s.index('    rng=np.random.default_rng(18301+event*379);');end=s.index('    candidates=np.zeros',start)
s=s[:start]+'''    rng=np.random.default_rng(18301+event*379)
    guide=np.asarray(GUIDES[event]['points']);widths=np.asarray(GUIDES[event]['widths']);gtree=cKDTree(guide)
    lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(guide,axis=0),axis=1))]
    stopd=np.linspace(0,lengths[-1],max(2,int(np.ceil(lengths[-1]/.28))+1))
    stops=np.column_stack([np.interp(stopd,lengths,guide[:,k]) for k in range(3)])
    h=.038;radius=h*.5;cap=110000
'''+s[end:]
s=s.replace('distance=gtree.query(positions)[0]','distance,nearest=gtree.query(positions)')
s=s.replace('corridor[new]=.07+.93*np.exp(-(distance/.62)**2)','corridor[new]=.008+.992*np.exp(-(distance/(.065+widths[nearest]*.75))**2)')
s=s.replace('range(4400)','range(6500)').replace('+.70/np.maximum(ds,.10)','+.12/np.maximum(ds,.10)').replace('corridor[ids]**.55','corridor[ids]**1.8')
s=s.replace("p+=rng.uniform(-.22,.22,p.shape)*h","p+=rng.uniform(-.30,.30,p.shape)*h")
start=s.index('def exposure(');end=s.index('\ndef channel(',start)
s=s[:start]+'''def exposure(f,event):
    # Short leader/return-stroke trains. No standing current between events.
    t=f/FPS;end=t+1/FPS;main=fork=0.
    birth=EVENTS[event]
    trains=[(birth,1.)]+[(at+.008*(event%5),power) for at,power in [(2.03,1.5),(2.77,.70),(3.36,1.2),(4.12,1.0)] if at>birth+.15]
    for at,gain in trains:
        for offset,power,duration in [(0,1.,.006),(.047+(event%3)*.007,.56,.0038),(.14+(event%2)*.02,.20,.0028)]:
            e=max(0,min(end,at+offset+duration)-max(t,at+offset))*FPS
            main+=e*power*gain;fork+=e*power*gain*(1 if offset==0 else .035)
        leader=max(0,min(end,at)-max(t,at-.038))*FPS*.008
        main+=leader;fork+=leader
    return main,fork

'''+s[end:]
# Advance leaders only on first formation; subsequent strokes re-use channels.
s=s.replace('on=pose(f/30)[2];center=curve(f/30);delta=self.world-center[:,None,None,None]\n        nozzle=np.exp(-np.sum(delta*delta,axis=0)/.13**2)*self.noise',"on=1.;nozzle=np.zeros(self.shape,np.float32)")
s=s.replace("d=distance_transform_edt(mask,sampling=self.spacing);light+=energy*np.exp(-d/.6)/(.009+d*d)","d=distance_transform_edt(mask,sampling=self.spacing);light+=energy*np.exp(-d/.28)/(.012+d*d);nozzle+=energy*np.exp(-(d/.09)**2)*self.noise*.22")
s=s.replace("np.array([.26,.31,.43],np.float32)","np.array([.075,.085,.13],np.float32)")
s=s.replace("frames=[9,15,22,32,44,50]","frames=[12,30,49,61,83,102]").replace("B/'lightning-pilot.jpg'","B/'lightning-pilot.jpg'")
s=s.replace("range(120)","range(168)").replace("B/'lightning-v5.mp4'","B/'lightning-candidate.mp4'").replace("frames=120","frames=168").replace("[9,15,22,32,39,44,50,55,60,80,110]","[12,30,49,61,62,83,84,101,102,124,125,145,167]")
(R/'sigil_02_repair_lightning.py').write_text(s)
