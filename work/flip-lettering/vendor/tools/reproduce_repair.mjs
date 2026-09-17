/** Regenerate 15 early high-resolution states with the delivered source. */
import fs from 'node:fs';import crypto from 'node:crypto';import {FlipSolver} from '../src/flip.js';import {makeProductionPreset} from '../src/quality-profile.js';
const names=['impact','breach','jets','slosh','hero'],records=[],sha=b=>crypto.createHash('sha256').update(b).digest('hex');
for(const name of names){
 const m=JSON.parse(fs.readFileSync(`cache/${name}/manifest.json`,'utf8')),s=new FlipSolver(makeProductionPreset(name));
 for(let f=0;f<3;f++){
  s.advance(m.frameDt);
  const raw=Buffer.concat([Buffer.from(s.p.buffer,0,s.count*12),Buffer.from(s.v.buffer,0,s.count*12)]),shape=Buffer.from(s.shape.buffer,0,s.count*24);
  if(sha(raw)!==m.frames[f].primarySha256||sha(shape)!==m.frames[f].shapeSha256)throw Error(`${name} ${f}: reproduction mismatch`);
  records.push({scene:name,frame:f,particles:s.count,primaryAndShapeByteIdentical:true});
 }console.log('REPRODUCED',name);
}
fs.writeFileSync('tests/repair/reproduction.json',JSON.stringify({passed:true,independentlyRegeneratedStates:records.length,publicProductionProfileUsed:true,sameRuntimeNotCrossDeviceGuarantee:true,records},null,2));
