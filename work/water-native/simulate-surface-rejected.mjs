import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';
const variant=process.argv[2]||'01',frames=+(process.argv[3]||144),root=new URL('./',import.meta.url),out=new URL(`cache-${variant}/`,root),source=JSON.parse(fs.readFileSync(new URL(`source-${variant}.json`,root)));fs.mkdirSync(out,{recursive:true});
const c=makeProductionPreset('jets');Object.assign(c,{nameKey:'sigil',h:.035,nx:160,ny:20,nz:86,extent:[5.6,.7,3.01],obstacles:[],maxParticles:250000,seed:8460+(+variant),gravity:[0,-9.81,0]});
const points=source.points.map(p=>[p[0],.112+p[2]-.86,source.bounds[3]-p[1]+.65]);
class Flow extends FlipSolver{
 emit(dt){
  if(this.time>.24)return;
  const counts=new Map(),h=this.h,key=(x,y,z)=>Math.floor(x/h)+160*(Math.floor(y/h)+20*Math.floor(z/h));
  for(let i=0;i<this.count;i++){const q=i*3;const k=key(...this.p.subarray(q,q+3));counts.set(k,(counts.get(k)||0)+1);}
  const front=.8+4*Math.min(1,(this.time+dt)/.14),fade=Math.max(0,Math.min(1,(.24-this.time)/.06));
  for(const p of points){if(p[0]>front||this.random()>fade)continue;const k=key(...p);if((counts.get(k)||0)>=7)continue;
   const jitter=this.h*.10,x=p[0]+(this.random()-.5)*jitter,y=p[1]+(this.random()-.5)*jitter,z=p[2]+(this.random()-.5)*jitter;
   // Only newborn particles receive source momentum. Existing water is free.
   const vx=.20*Math.sin(z*8),vy=-.5,vz=.14*Math.sin(x*7+z*8);
   if(this.add(x,y,z,vx,vy,vz)){counts.set(k,(counts.get(k)||0)+1);this.spawned++;}
  }
 }
}
const sim=new Flow(c),m={config:c,frameDt:1/96,playbackFps:24,frames:[],variant,source:'Full approved v6 silhouette; swept replenishing source; free gravity after birth; no home/tangent guide'},start=performance.now();
for(let f=0;f<frames;f++){
 const info=sim.advance(m.frameDt),n=sim.count;if(!info.finite||!info.pressure.converged||info.capacityRejected)throw Error(JSON.stringify(info));
 const raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:1}));
 m.frames.push({frame:f,...info});fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(m));if(f%8===0)console.log(JSON.stringify({frame:f,n,seconds:(performance.now()-start)/1000}));
}m.complete=true;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(m));console.log('COMPLETE');
