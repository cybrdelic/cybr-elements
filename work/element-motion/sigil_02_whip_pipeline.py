"""Isolate the water intro revision while retaining the reviewed optical pipeline."""
from pathlib import Path
R=Path(__file__).resolve().parent
sim=(R/'sigil_02_ground_water.mjs').read_text().replace('sigil-02-bending-ground/','sigil-02-water-whip/')
sim=sim.replace("forces=[0,1,2].map(c=>load(`guide-${c}.f32`))", "forces=[0,1,2].map(c=>{const b=fs.readFileSync(`${cfg.forceRoot}/guide-${c}.f32`);return new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);})")
a=sim.index('function goal(');b=sim.index('class Flow',a)
sim=sim[:a]+'''const track=load('whip.f32'),stride=cfg.guideSamples*9;
const guideNow=new Float32Array(stride),guideNext=new Float32Array(stride);
function sampleTime(t,result){
 const ft=Math.max(0,Math.min(cfg.guideTimes-1.001,t/cfg.guideDt)),frame=Math.floor(ft),blend=ft-frame;
 for(let q=0;q<stride;q++)result[q]=track[frame*stride+q]*(1-blend)+track[(frame+1)*stride+q]*blend;
}
function goal(i,t,table,result){
 const k=i*9,u=source[k+6],cz=source[k+7],cy=source[k+8];
 const fq=u*(cfg.guideSamples-1),q=Math.min(cfg.guideSamples-2,Math.floor(fq)),a=fq-q;
 const arrival=smooth((t-2.7-u*.95)/1.65);
 for(let j=0;j<3;j++){
  const r=q*9+j;
  const center=table[r]*(1-a)+table[r+9]*a;
  const n=table[r+3]*(1-a)+table[r+12]*a;
  const b=table[r+6]*(1-a)+table[r+15]*a;
  const moving=(center+n*cz+b*cy)*cfg.spaceScale+cfg.origin[j];
  result[j]=moving*(1-arrival)+source[k+3+j]*arrival;
 }
}
''' +sim[b:]
sim=sim.replace('if(guide>0)for(let i=0;i<this.count;i++){','if(guide>0){sampleTime(t,guideNow);sampleTime(t+.025,guideNext);}\n   if(guide>0)for(let i=0;i<this.count;i++){')
sim=sim.replace('goal(i,t,this.goal0);goal(i,t+.025,this.goal1);','goal(i,t,guideNow,this.goal0);goal(i,t+.025,guideNext,this.goal1);')
sim=sim.replace('Math.max(-7,Math.min(7,acceleration))','Math.max(-24,Math.min(24,acceleration))')
sim=sim.replace('.length>=80','.length>=12')
sim=sim.replace('All water exists at frame zero in a continuous ribbon on the floor.', 'All water exists at frame zero in a rounded ground crescent. A volume-aware 3D hook and accelerating cast guide its lift.')
(R/'sigil_02_whip_water.mjs').write_text(sim)
mesh=(R/'sigil_02_ground_mesh.py').read_text().replace("'sigil-02-bending-ground'","'sigil-02-water-whip'")
mesh=mesh.replace('list(range(0,390,6))+[389]', 'list(range(0,180,6))')
mesh=mesh.replace('[0,18,42,66,90,114,144,180,234,270,300,354,389]','[0,18,36,54,72,90,114,150,174]')
mesh=mesh.replace('[0,66,114,180,234,270,300,354,389]','[0,36,66,90,120,180,270,389]')
mesh=mesh.replace("if not pilot and not preview and f not in", "if not pilot and f not in")
(R/'sigil_02_whip_mesh.py').write_text(mesh)
render=(R/'sigil_02_ground_water_render.py').read_text().replace("'sigil-02-bending-ground'","'sigil-02-water-whip'")
render=render.replace('list(range(0,390,6))+[389]', 'list(range(0,180,6))')
render=render.replace('[0,18,42,66,90,114,144,180,234,270,300,354,389]','[0,18,36,54,72,90,114,150,174]')
render=render.replace("if '--full' in args:\n  vectors.close()", "if '--full' in args or '--preview' in args:\n  vectors.close()")
(R/'sigil_02_whip_render.py').write_text(render)
print('Isolated native solver, reconstruction and render scripts written.')
