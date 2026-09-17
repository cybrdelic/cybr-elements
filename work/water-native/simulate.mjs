import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';import crypto from 'node:crypto';
const variant=process.argv[2]||'01',frames=+(process.argv[3]||192),root=new URL('./',import.meta.url),out=new URL(`cache-${variant}/`,root),source=JSON.parse(fs.readFileSync(new URL(`source-${variant}.json`,root)));fs.mkdirSync(out,{recursive:true});
const c=makeProductionPreset('jets');Object.assign(c,{nameKey:'sigil',h:.025,nx:224,ny:140,nz:96,extent:[5.6,3.5,2.4],obstacles:[],maxParticles:100000,seed:8460+(+variant),gravity:[0,-9.81,0]});
const events=source.points.map((p,i)=>({p,birth:.012+.18*(p[0]-.8)/4})).sort((a,b)=>a.birth-b.birth);
class Flow extends FlipSolver{
 emit(dt){
  this.cursor??=0;
  while(this.cursor<events.length&&events[this.cursor].birth<=this.time+dt){
   const {p,birth}=events[this.cursor++],tau=.37-birth;
   const vx=.28*Math.sin(p[1]*7)+.10*(this.random()-.5),vy=.32*Math.sin(p[0]*5)+.08*(this.random()-.5),vz=.32*Math.sin(p[0]*5+p[1]*7)+.10*(this.random()-.5);
   // Ballistic source placement and newborn velocity. No correction after birth.
   const x=p[0]-vx*tau,y=p[1]-4.905*tau*tau-vy*tau,z=p[2]-vz*tau;
   if(this.add(x,y,z,vx,9.81*tau+vy,vz))this.spawned++;
  }
 }
}
const sim=new Flow(c),m={config:c,frameDt:1/120,playbackFps:24,frames:[],variant,source:'Full approved v6 silhouette; one-time ballistic source; no forces or position corrections after birth beyond original solver physics',timeMap:'Smooth slow motion around ballistic formation; one new physical state per output frame'},start=performance.now();
for(let f=0;f<frames;f++){
 const dt=.0028+.0095*(1-Math.exp(-Math.pow((f-66)/39,4)));
 const info=sim.advance(dt),n=sim.count;if(!info.finite||!info.pressure.converged||info.capacityRejected)throw Error(JSON.stringify(info));
 const raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:1}));
 m.frames.push({frame:f,dt,...info,primarySha256:crypto.createHash('sha256').update(raw).digest('hex')});fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(m));if(f%8===0)console.log(JSON.stringify({frame:f,n,t:sim.time,seconds:(performance.now()-start)/1000}));
}m.complete=true;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(m));console.log('COMPLETE');
