#!/usr/bin/env node
import fs from 'node:fs';
import {FlipSolver,makePreset} from '../src/flip.js';
import {encodeCheckpoint,decodeCheckpoint} from '../src/checkpoint.js';
const [command,input,framesArg,output]=process.argv.slice(2),frames=Number(framesArg);
if(!['simulate','resume'].includes(command)||!input||!output||!Number.isInteger(frames)||frames<0||frames>100000){console.error('Usage: node tools/checkpoint.mjs simulate <scene> <frames> <output.cfc>\n       node tools/checkpoint.mjs resume <input.cfc> <additional-frames> <output.cfc>');process.exit(2);}
try{
 const sim=command==='resume'?decodeCheckpoint(fs.readFileSync(input)):new FlipSolver(makePreset(input,'high'));
 for(let i=0;i<frames;i++){sim.advance(1/48);if(i%24===0)console.log(JSON.stringify({frame:i,time:sim.time,particles:sim.count}));}
 fs.writeFileSync(output,new Uint8Array(encodeCheckpoint(sim)));console.log('Wrote resumable PRIMARY checkpoint:',output);
}catch(error){console.error(error.stack);process.exit(1);}
