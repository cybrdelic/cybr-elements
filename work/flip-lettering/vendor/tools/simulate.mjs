import { FlipSolver,makePreset } from '../src/flip.js';
import fs from 'node:fs';import path from 'node:path';import {performance} from 'node:perf_hooks';
const [name='breach',framesArg='120',quality='high']=process.argv.slice(2);
const frames=Number(framesArg),config=makePreset(name,quality),solver=new FlipSolver(config);
const out=new URL(`../cache/${name}/`,import.meta.url);fs.mkdirSync(out,{recursive:true});
const manifest={name,config,frameDt:1/48,frames:[],format:'float32-le: positions xyz then velocities xyz, particle count in manifest',solver:'src/flip.js'};
const start=performance.now();
for(let f=0;f<frames;f++){
 const m=solver.advance(1/48),p=solver.p.subarray(0,solver.count*3),v=solver.v.subarray(0,solver.count*3);
 const a=Buffer.concat([Buffer.from(p.buffer,p.byteOffset,p.byteLength),Buffer.from(v.buffer,v.byteOffset,v.byteLength)]);
 fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.particles`,out),a);
 manifest.frames.push({frame:f,...m});
 if(!m.finite||m.solidViolations||m.capacityRejected)throw new Error(`Validation failure: ${JSON.stringify(m)}`);
 if(f%12===0)console.log(JSON.stringify({scene:name,frame:f,particles:solver.count,time:m.time,divBefore:m.divergenceBefore,divAfter:m.divergenceAfter,maxSpeed:m.maxSpeed,wall:(performance.now()-start)/1000}));
 fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest,null,2));
}
manifest.wallSeconds=(performance.now()-start)/1000;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest,null,2));
console.log('COMPLETE',name,manifest.wallSeconds);
