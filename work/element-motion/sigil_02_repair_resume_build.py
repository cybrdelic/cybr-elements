"""Resume without rerendering completed frames or resetting spray history."""
from pathlib import Path
R=Path(__file__).resolve().parent
p=R/'sigil_02_repair_water_mesh.py';s=p.read_text()
s=s.replace('from bending_surface import DetailReconstruction,encode','from bending_surface import DetailReconstruction,encode\nfrom mesh_cache import deposit,sample')
needle=" if n:\n  # CPU depth/speed preview"
replay=''' if (B/'water-frames'/f'{f:04}.jpg').exists():
  # Rebuild only classifier/spray state during deterministic simulation replay.
  # The expensive surface and GPU image are retained exactly as rendered.
  if n>2048:
   lower=np.maximum(0,np.floor((p.min(0)-5*h)/h)*h);upper=np.minimum(extent,np.ceil((p.max(0)+5*h)/h)*h);spacing=h*.43
   gridShape=tuple(np.ceil((upper-lower)/spacing).astype(int)+1)
   rho,vx,vy,vz=deposit(p-lower,v,gridShape,spacing,h*.98);density=sample(rho,p-lower,spacing);del rho,vx,vy,vz
   if len(isolated)<n:isolated=np.pad(isolated,(0,n-len(isolated)))
   before=isolated.copy();isolated=np.zeros(n,bool);boundary=np.flatnonzero(density<3.55)
   if len(boundary):
    tree=cKDTree(p);dist,ids=tree.query(p[boundary],k=min(32,n),workers=1);counts=(dist<h).sum(1);isolated[boundary]=np.where(before[boundary],(density[boundary]<1.40)&(counts<7),(density[boundary]<1.16)&(counts<5));del tree,dist,ids
   if spray is None:spray=Spray(h)
   cluster=object.__new__(DetailReconstruction);cluster.h=h
   spray.step(p,v,isolated,m['frameDt'],cluster.droplet_clusters)
   old=out/f'{f:04}.json'
   if old.exists():previous_iso=json.loads(old.read_text()).get('isovalue',previous_iso)
  (source/f'{f:04}.gz').unlink()
  if f%15==0:print('REPLAY state',f,'seconds',round(time.time()-started,1),flush=True)
  continue
 if n:
  # CPU depth/speed preview'''
assert needle in s;s=s.replace(needle,replay)
old=" if f>135 and n>4:\n  visible=p[:,1]>.48;p=p[visible];v=v[visible];n=len(p);isolated=np.empty(0,bool)"
new=""" allp,allv=p,v;visibleIds=np.arange(n)
 if len(isolated)<n:isolated=np.pad(isolated,(0,n-len(isolated)))
 if f>135 and n>4:
  visibleIds=np.flatnonzero(p[:,1]>.48);p=p[visibleIds];v=v[visibleIds];n=len(p);isolated=isolated[visibleIds]
"""
assert old in s;s=s.replace(old,new)
s=s.replace('isolated=rec.isolated.copy();previous_iso=iso','localIsolated=rec.isolated.copy();isolated=np.zeros(len(allp),bool);isolated[visibleIds]=localIsolated;previous_iso=iso')
s=s.replace('spray.step(p,v,isolated,m[\'frameDt\'],rec.droplet_clusters)','spray.step(allp,allv,isolated,m[\'frameDt\'],rec.droplet_clusters)')
(R/'sigil_02_repair_water_mesh_resume.py').write_text(s)
s=(R/'sigil_02_repair_full.py').read_text()
s=s.replace("start('lightning-full',[PY,str(R/'sigil_02_repair_lightning_branched.py'),'--full'])",'# Lightning waits until the memory-heavy water pipeline has exited.')
s=s.replace("str(R/'sigil_02_repair_water_mesh.py')","str(R/'sigil_02_repair_water_mesh_resume.py')")
s=s.replace(" e=start('earth-full'", " start('lightning-full',[PY,str(R/'sigil_02_repair_lightning_branched.py'),'--full'])\n e=start('earth-full'")
s=s.replace("p=R/'sigil_02_repair_water_mesh.py';s=p.read_text()","p=R/'sigil_02_repair_water_mesh_resume.py';s=p.read_text()")
# The graphics caches are bounded; serialize the large working sets instead of
# reducing output quality. Retain the safety threshold.
(R/'sigil_02_repair_resume.py').write_text(s)
print('Prepared deterministic state replay, stable tail particle IDs, and serialized heavy jobs.')
