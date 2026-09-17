/** Bake a typed graph into actual solver states; no execution of graph strings. */
import fs from 'node:fs';import path from 'node:path';import crypto from 'node:crypto';
import {SceneGraph} from '../src/production/scene-graph.js';import {FlipSolver} from '../src/flip.js';import {encodeCheckpoint} from '../src/checkpoint.js';
const [file,out='cache/graph_experiment']=process.argv.slice(2);if(!file)throw Error('Usage: node tools/run_graph.mjs graph.json [output-directory]');
const graph=new SceneGraph(JSON.parse(fs.readFileSync(file,'utf8'))),compiled=graph.compile(),sim=new FlipSolver(compiled.config),manifest={schema:'cybr-flip-cache/3',name:compiled.config.nameKey,config:compiled.config,frameDt:compiled.frameDt,frames:[],graph:graph.toJSON(),cacheKeys:compiled.cacheKeys,canonicalInputs:compiled.canonicalInputs,simulationBackend:'CPU quadratic APIC / MG-PCG'};
fs.mkdirSync(out,{recursive:true});const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
for(let i=0;i<compiled.frames;i++){const info=sim.advance(compiled.frameDt);if(!info.finite||info.solidViolations)throw Error('Simulation validation failed.');const prefix=path.join(out,String(i).padStart(4,'0'));
 const particle=Buffer.concat([Buffer.from(sim.p.buffer,0,sim.count*12),Buffer.from(sim.v.buffer,0,sim.count*12)]),shape=Buffer.from(sim.shape.buffer,0,sim.count*24);fs.writeFileSync(prefix+'.particles',particle);fs.writeFileSync(prefix+'.shape',shape);manifest.frames.push({frame:i,...info,primarySha256:hash(particle),shapeSha256:hash(shape)});
 if(i===0||i===compiled.frames-1)fs.writeFileSync(prefix+'.checkpoint',Buffer.from(encodeCheckpoint(sim)));if(i%12===0)console.log('FRAME',i,info.time,info.particles);
}
manifest.simulationComplete=true;fs.writeFileSync(path.join(out,'manifest.json'),JSON.stringify(manifest,null,2));console.log('BAKED',path.resolve(out));
