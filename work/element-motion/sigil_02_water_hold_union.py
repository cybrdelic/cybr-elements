"""One fluid parcel per lattice cell in the union of all rounded source tubes."""
from pathlib import Path
import json,shutil,numpy as np
from scipy.spatial import cKDTree
R=Path(__file__).resolve().parent;O=R/'sigil-02-water-hold';cfg=json.loads((O/'config.json').read_text());h=cfg['h'];spacing=h*.5
old=np.fromfile(O/'source.f32','<f4').reshape(-1,7);g=np.load(O/'guides.npz');centers=g['points'];radii=g['radii'];tree=cKDTree(centers);oldtree=cKDTree(old[:,1:4]);rng=np.random.default_rng(64211)
lo=np.floor((centers.min(0)-radii.max()-spacing)/spacing)*spacing;hi=np.ceil((centers.max(0)+radii.max()+spacing)/spacing)*spacing
rows=[]
for x in np.arange(lo[0],hi[0],spacing):
 yy,zz=np.meshgrid(np.arange(lo[1],hi[1],spacing),np.arange(lo[2],hi[2],spacing),indexing='ij');p=np.column_stack((np.full(yy.size,x),yy.ravel(),zz.ravel()));p+=rng.uniform(-spacing*.12,spacing*.12,p.shape)
 d,ids=tree.query(p,k=12,workers=2);ratio=d/radii[ids];valid=(ratio.min(1)<1);p=p[valid]
 if not len(p):continue
 _,nearest=oldtree.query(p,workers=2);birth=old[nearest,0];velocity=old[nearest,4:];rows.append(np.column_stack((birth,p,velocity)))
a=np.concatenate(rows).astype('<f4');a=a[np.argsort(a[:,0])]
assert len(np.unique(np.floor((a[:,1:4]-lo)/spacing+.5).astype(int),axis=0))==len(a)
for name in ['particles','mesh','pilot']:
 src=(O/name).resolve();dst=(O/f'{name}-v1').resolve();assert src.parent==O.resolve() and dst.parent==O.resolve() and not dst.exists();src.rename(dst)
for file in (O/'particles-v1').glob('*.gz'):
 if file.stem not in ['0045','0075','0120','0165']:
  assert file.resolve().parent==(O/'particles-v1').resolve();file.unlink()
shutil.copy2(O/'source.f32',O/'source-v1.f32');a.tofile(O/'source.f32');shutil.copy2(O/'source-report.json',O/'source-report-v1.json')
report=dict(particles=len(a),previousParticles=len(old),unionSampling=True,spacing=spacing,noDuplicateLatticeCells=True,medianSpeed=float(np.median(np.linalg.norm(a[:,4:],axis=1))),writeEnds=float(a[:,0].max()),holdUntil=5.8,releaseEnds=6.65)
(O/'source-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
