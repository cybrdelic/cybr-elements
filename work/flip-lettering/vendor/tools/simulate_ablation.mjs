/** Deterministic visual-regression cache generator. Old caches are never re-labelled. */
import {FlipSolver,makePreset} from '../src/flip.js';
import {FlipSolver as Reference,makePreset as makeReference} from '../src/flip-reference.js';
import {encodeCheckpoint} from '../src/checkpoint.js';
import fs from 'node:fs';import crypto from 'node:crypto';
const [name='impact',framesText='120',quality='ultra',variant='repair',outputName=name]=process.argv.slice(2),frames=Number(framesText);
if(!Number.isInteger(frames)||frames<1||frames>10000)throw Error('Invalid frame count');
if(!/^[a-z0-9_-]+$/.test(outputName))throw Error('Invalid output name');
const config=variant==='ii'?makeReference(name,quality):makePreset(name,quality);
if(['repair','hybrid'].includes(variant)){config.flip=.93;config.separation=true;}
if(variant==='hybrid')config.transfer='apic-flip';
config.ablationOnly=true;config.variant=variant;
const Solver=variant==='ii'?Reference:FlipSolver,solver=new Solver(config),out=new URL(`../cache/${outputName}/`,import.meta.url);
fs.mkdirSync(out,{recursive:true});
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const sourceFiles=['src/flip.js','src/flip-reference.js','src/flip-base.js','src/numerics/multigrid.js','src/numerics/stress.js','tools/simulate_ablation.mjs'];
const sourceHashes=Object.fromEntries(sourceFiles.map(p=>[p,sha(fs.readFileSync(new URL('../'+p,import.meta.url)))]));
const manifest={schema:'cybr-flip-cache/3',name:outputName,preset:name,config,frameDt:1/48,frames:[],sourceHashes,solver:variant==='ii'?'src/flip-reference.js':'src/flip.js',
 rawFormat:'little-endian float32: positions xyz then velocities xyz; .shape is per-particle xx yy zz xy xz yz',
 simulationBackend:variant==='ii'?'CPU II affine FLIP reference':'CPU III numerical reference; controlled ablation only',createdAt:new Date().toISOString()};
const start=performance.now();
const save=()=>{fs.writeFileSync(new URL('manifest.tmp',out),JSON.stringify(manifest,null,2));fs.renameSync(new URL('manifest.tmp',out),new URL('manifest.json',out));};
for(let frame=0;frame<frames;frame++) {
 const info=solver.advance(1/48),n=solver.count,p=solver.p.subarray(0,n*3),v=solver.v.subarray(0,n*3);
 if(!info.finite||info.solidViolations||info.capacityRejected||!info.pressure.converged)throw Error('Invalid high-resolution state '+JSON.stringify(info));
 const raw=Buffer.concat([Buffer.from(p.buffer,p.byteOffset,p.byteLength),Buffer.from(v.buffer,v.byteOffset,v.byteLength)]);
 const prefix=String(frame).padStart(4,'0');fs.writeFileSync(new URL(prefix+'.particles',out),raw);
 let history;
 if(solver.shape){const shape=solver.shape.subarray(0,n*6);history=Buffer.from(shape.buffer,shape.byteOffset,shape.byteLength);}else {const shape=new Float32Array(n*6);for(let i=0;i<n;i++)shape[i*6]=shape[i*6+1]=shape[i*6+2]=1;history=Buffer.from(shape.buffer);}
 fs.writeFileSync(new URL(prefix+'.shape',out),history);
 manifest.frames.push({frame,...info,primarySha256:sha(raw),shapeSha256:sha(history)});
 if(solver.shape&&(frame===0||frame===frames-1))fs.writeFileSync(new URL(prefix+'.checkpoint',out),Buffer.from(encodeCheckpoint(solver)));
 save();
 if(frame%8===0)console.log(JSON.stringify({scene:outputName,variant,frame,particles:n,time:info.time,relativeResidual:info.pressure.relativeResidual,energy:info.kineticEnergy,seconds:(performance.now()-start)/1000}));
}
manifest.wallSeconds=(performance.now()-start)/1000;manifest.simulationComplete=true;save();console.log('COMPLETE',outputName,manifest.wallSeconds);
