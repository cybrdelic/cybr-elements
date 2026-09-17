import {FlipSolver,makePreset} from '../src/flip.js';
import {encodeCheckpoint} from '../src/checkpoint.js';
import fs from 'node:fs';import crypto from 'node:crypto';
const [name='impact',framesText='96',quality='high']=process.argv.slice(2),frames=Number(framesText);
if(!Number.isInteger(frames)||frames<1||frames>10000)throw Error('Invalid frame count.');
const config=makePreset(name,quality),solver=new FlipSolver(config),out=new URL(`../cache/${name}/`,import.meta.url);
fs.mkdirSync(out,{recursive:true});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const sourceFiles=['src/flip.js','src/flip-reference.js','src/flip-base.js','src/numerics/multigrid.js','src/numerics/stress.js'];
const sourceHashes=Object.fromEntries(sourceFiles.map(p=>[p,sha(fs.readFileSync(new URL('../'+p,import.meta.url)))]));
const manifest={schema:'cybr-flip-cache/3',name,config,frameDt:1/48,frames:[],sourceHashes,solver:'src/flip.js',
 rawFormat:'little-endian float32: positions xyz then velocities xyz; .shape is per-particle xx yy zz xy xz yz',
 simulationBackend:'JavaScript CPU quadratic APIC/FLIP',createdAt:new Date().toISOString()};
const start=performance.now();
const save=()=>{fs.writeFileSync(new URL('manifest.tmp',out),JSON.stringify(manifest,null,2));fs.renameSync(new URL('manifest.tmp',out),new URL('manifest.json',out));};
for(let frame=0;frame<frames;frame++) {
 const info=solver.advance(1/48),n=solver.count,p=solver.p.subarray(0,n*3),v=solver.v.subarray(0,n*3),shape=solver.shape.subarray(0,n*6);
 if(!info.finite||info.solidViolations||info.capacityRejected||!info.pressure.converged)throw Error('Invalid high-resolution state '+JSON.stringify(info));
 const raw=Buffer.concat([Buffer.from(p.buffer,p.byteOffset,p.byteLength),Buffer.from(v.buffer,v.byteOffset,v.byteLength)]),history=Buffer.from(shape.buffer,shape.byteOffset,shape.byteLength);
 const prefix=String(frame).padStart(4,'0');fs.writeFileSync(new URL(prefix+'.particles',out),raw);fs.writeFileSync(new URL(prefix+'.shape',out),history);
 manifest.frames.push({frame,...info,primarySha256:sha(raw),shapeSha256:sha(history)});
 if(frame===0||frame===frames-1)fs.writeFileSync(new URL(prefix+'.checkpoint',out),Buffer.from(encodeCheckpoint(solver)));
 if(frame%12===0){console.log(JSON.stringify({scene:name,frame,particles:n,time:info.time,relativeResidual:info.pressure.relativeResidual,levels:info.pressure.levels,seconds:(performance.now()-start)/1000}));save();}
}
manifest.wallSeconds=(performance.now()-start)/1000;manifest.simulationComplete=true;save();console.log('COMPLETE',name,manifest.wallSeconds);
