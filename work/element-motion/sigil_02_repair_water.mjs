import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';
const root=new URL('sigil-02-repair/',import.meta.url),out=new URL('water-particles/',root);fs.mkdirSync(out,{recursive:true});
const buf=fs.readFileSync(new URL('water-source.f32',root));const source=new Float32Array(buf.buffer,buf.byteOffset,buf.byteLength/4),count=source.length/7;
const timeScale=.4,spaceScale=.35,origin=[2.1,.98,.756],c=makeProductionPreset('jets');
Object.assign(c,{nameKey:'02-moving-water-fronts',h:.018,nx:234,ny:174,nz:84,extent:[4.212,3.132,1.512],obstacles:[],maxParticles:count+100,seed:91351,gravity:[0,-.42,0],flip:.88,separation:true,surfaceTension:.072});
class Flow extends FlipSolver{
 emit(dt){this.sourceCursor??=0;const t=(this.time+dt)/timeScale;while(this.sourceCursor<count&&source[this.sourceCursor*7]<=t){const k=this.sourceCursor++*7;if(this.add(...source.subarray(k+1,k+7)))this.spawned++;}}
 applyForces(dt){const t=this.time/timeScale,u=Math.max(0,Math.min(1,(t-3.5)/.65));this.gravity[1]=-.42-9.39*u*u*(3-2*u);super.applyForces(dt);}
}
const sim=new Flow(c);const manifest={config:c,frameDt:timeScale/30,playbackFps:30,timeScale,spaceScale,origin,frames:[],source:'Full02 moving source fronts; FLIP/APIC, pressure and capillarity. Authored reduced gravity during bending. Free momentum, no glyph targets.'};
const started=performance.now(),total=192;
for(let f=0;f<total;f++){
 while(fs.readdirSync(out).filter(x=>x.endsWith('.gz')).length>=8)await new Promise(r=>setTimeout(r,300));
 const info=sim.advance(manifest.frameDt);if(!info.finite||!info.pressure.converged||info.capacityRejected||Math.abs(info.sourceVolumeBalance)>1e-8)throw Error(JSON.stringify(info));
 const n=sim.count;if(f>=24&&n<1000)throw Error('Source validation: expected emitted water');const raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);
 fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:1}));manifest.frames.push({frame:f,...info});
 const tmp=new URL('manifest.tmp',out);fs.writeFileSync(tmp,JSON.stringify(manifest));fs.renameSync(tmp,new URL('manifest.json',out));
 if(f%15===0)console.log(JSON.stringify({frame:f,particles:n,seconds:Math.round((performance.now()-started)/1000),pressure:info.pressure.relativeResidual}));
 if(f===89&&!process.argv.includes('--ungated')){console.log('PILOT GATE at frame89');while(!fs.existsSync(new URL('water-continue',root)))await new Promise(r=>setTimeout(r,500));}
}
manifest.complete=true;manifest.elapsedSeconds=(performance.now()-started)/1000;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));console.log('SIM COMPLETE');
