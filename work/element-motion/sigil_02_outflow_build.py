"""Correct the hidden basin at release; preserve all reviewed formation images."""
from pathlib import Path
import shutil
R=Path(__file__).resolve().parent;O=R/'sigil-02-repair'
(O/'water-outflow-frames').mkdir(exist_ok=True)
for f in range(136):
 shutil.copy2(O/f'water-frames/{f:04}.jpg',O/f'water-outflow-frames/{f:04}.jpg')
shutil.copy2(O/'water-particles/manifest.json',O/'water-basin-manifest.json')
s=(R/'sigil_02_repair_water.mjs').read_text()
s=s.replace("out=new URL('water-particles/',root)","out=new URL('water-outflow-particles/',root)")
s=s.replace("class Flow extends FlipSolver{", """class Flow extends FlipSolver{
 constructor(config){super(config);this.ids=new Uint32Array(this.maxParticles);}
 step(dt){
  const result=super.step(dt);
  if(this.time/timeScale>=136/30){
   let kept=0;
   for(let i=0;i<this.count;i++){
    if(this.p[i*3+1]<=.12){this.deleted++;continue;}
    if(kept!==i){
     for(const [a,stride] of [[this.p,3],[this.v,3],[this.affine,9],[this.shape,6],[this.previousPosition,3]])a.copyWithin(kept*stride,i*stride,(i+1)*stride);
     this.ids[kept]=this.ids[i];
    }
    kept++;
   }
   this.count=kept;this.shapeInitialized=kept;
  }
  return result;
 }
""")
s=s.replace('if(this.add(...source.subarray(k+1,k+7)))this.spawned++;','if(this.add(...source.subarray(k+1,k+7))){this.ids[this.count-1]=k/7;this.spawned++;}')
s=s.replace('total=192','total=216')
s=s.replace("if(f>=24&&n<1000)","if(f>=24&&f<136&&n<1000)")
s=s.replace("Buffer.from(sim.v.buffer,0,n*12)]", "Buffer.from(sim.v.buffer,0,n*12),Buffer.from(sim.ids.buffer,0,n*4)]")
(R/'sigil_02_water_outflow.mjs').write_text(s)

s=(R/'sigil_02_repair_water_mesh_resume.py').read_text()
s=s.replace("source=B/'water-particles';out=B/'water-mesh'", "source=B/'water-outflow-particles';out=B/'water-outflow-mesh'")
s=s.replace('frames=range(192)','frames=range(216)')
s=s.replace('spray=None','spray=None;previous_ids=np.empty(0,np.uint32);orphan_p=np.empty((0,3),np.float32);orphan_v=orphan_p.copy();orphan_r=np.empty(0,np.float32)',1)
s=s.replace("p=raw[:n*3].reshape(-1,3);v=raw[n*3:].reshape(-1,3);", "p=raw[:n*3].reshape(-1,3);v=raw[n*3:n*6].reshape(-1,3);particle_ids=raw[n*6:].view('<u4');")
s=s.replace("if (B/'water-frames'/f'{f:04}.jpg').exists():", """if f>=136 and spray is not None:
  # Stable source ids keep existing fragments attached to the same parcels.
  where=np.searchsorted(previous_ids,particle_ids)
  assert np.all(previous_ids[where]==particle_ids)
  retired=np.ones(len(previous_ids),bool);retired[where]=False
  gone=np.flatnonzero(retired & spray.active[:len(previous_ids)])
  if len(gone):
   rad=spray.r[gone].reshape(-1);keep=rad>0
   orphan_p=np.concatenate([orphan_p,spray.p[gone].reshape(-1,3)[keep]])
   orphan_v=np.concatenate([orphan_v,spray.v[gone].reshape(-1,3)[keep]])
   orphan_r=np.concatenate([orphan_r,rad[keep]])
  for array in [spray.active,spray.p,spray.v,spray.r,spray.previousNeighbours]:
   moved=array[where].copy();array[:]=0;array[:n]=moved
  isolated=isolated[where]
 previous_ids=particle_ids.copy()
 if len(orphan_r):
  for _ in range(3):
   dt=m['frameDt']/3;orphan_v[:,1]-=9.81*dt
   relative=orphan_v-np.array([.035,0,.020]);speed=np.linalg.norm(relative,axis=1)
   drag=3*1.225*.47/(8*1000*np.maximum(orphan_r,.00002))*speed
   orphan_v-=relative*(1-np.exp(-drag*dt))[:,None];orphan_p+=orphan_v*dt
  keep=orphan_p[:,1]>.12;orphan_p=orphan_p[keep];orphan_v=orphan_v[keep];orphan_r=orphan_r[keep]
 if (B/'water-outflow-frames'/f'{f:04}.jpg').exists():""")
s=s.replace("if f>135 and n>4:","if False and n>4:")
s=s.replace("np.savez_compressed(out/f'{f:04}.velocity.npz'", """if len(orphan_r):
  drops=np.concatenate([drops,orphan_p]);radii=np.concatenate([radii,orphan_r]);dv=np.concatenate([dv,orphan_v])
  measure['retiredParentFragmentsStillInView']=len(orphan_r)
 np.savez_compressed(out/f'{f:04}.velocity.npz'""")
s=s.replace("p[::max(1,n//10000)]","p[::max(1,n//10000)]")
(R/'sigil_02_water_outflow_mesh.py').write_text(s)
s=(R/'sigil_02_repair_water_render.py').read_text().replace('water-mesh','water-outflow-mesh').replace('water-frames','water-outflow-frames').replace('range(192)','range(216)')
(R/'sigil_02_water_outflow_render.py').write_text(s)
print('Outflow scripts built; 136 reviewed frames retained. Removed mass is accounted and detached spray continues until it leaves view.')
