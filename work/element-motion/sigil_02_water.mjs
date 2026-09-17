import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';
import zlib from 'node:zlib';
const root=new URL('sigil-02-elements/',import.meta.url),out=new URL('water-particles/',root);
fs.mkdirSync(out,{recursive:true});
const buf=fs.readFileSync(new URL('water-source.f32',root));
const sources=new Float32Array(buf.buffer,buf.byteOffset,buf.byteLength/4),sourceCount=sources.length/7;
const timeScale=.32,spaceScale=.35,origin=[2.1,.98,.63];
const c=makeProductionPreset('jets');
Object.assign(c,{nameKey:'sigil-02-full-source',h:.018,nx:234,ny:174,nz:70,extent:[4.212,3.132,1.26],obstacles:[],maxParticles:Math.max(220000,sourceCount+10),seed:93157,gravity:[0,-.018,0],flip:.88,separation:true,surfaceTension:.072});
class SourceFlow extends FlipSolver {
 emit(dt){
  this.nextSource??=0;
  const t=(this.time+dt)/timeScale;
  while(this.nextSource<sourceCount&&sources[this.nextSource*7]<=t){
   const k=this.nextSource++*7;
   if(this.add(...sources.subarray(k+1,k+7)))this.spawned++;
  }
 }
 applyForces(dt){
  const t=this.time/timeScale,u=Math.max(0,Math.min(1,(t-6.8)/.45));
  // Authored suspension during bending, then full physical gravity. No
  // position correction, letter-shaped collision walls or post-mesh fitting.
  this.gravity[1]=-.018-9.792*u*u*(3-2*u);super.applyForces(dt);
 }
}
const sim=new SourceFlow(c),manifest={config:c,frameDt:timeScale/30,playbackFps:30,timeScale,spaceScale,origin,frames:[],source:'Complete rounded 3D 02 source volume, native APIC/FLIP pressure and capillarity; supplied momentum and authored suspension; no glyph walls or fitted surface'};
const started=performance.now();
for(let f=0;f<294;f++){
 // Bound disk usage while reconstruction/rendering consume the stream.
 while(fs.readdirSync(out).filter(x=>x.endsWith('.gz')).length>=8)await new Promise(r=>setTimeout(r,500));
 const info=sim.advance(manifest.frameDt);
 if(!info.finite||!info.pressure.converged||info.capacityRejected||Math.abs(info.sourceVolumeBalance)>1e-8)throw Error(JSON.stringify(info));
 const n=sim.count,raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);
 fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:2}));
 manifest.frames.push({frame:f,...info});
 const temp=new URL('manifest.tmp',out);fs.writeFileSync(temp,JSON.stringify(manifest));fs.renameSync(temp,new URL('manifest.json',out));
 if(f%15===0)console.log(JSON.stringify({frame:f,n,seconds:Math.round((performance.now()-started)/1000),pressure:info.pressure.relativeResidual}));
}
manifest.complete=true;manifest.elapsedSeconds=(performance.now()-started)/1000;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));console.log('WATER COMPLETE');
