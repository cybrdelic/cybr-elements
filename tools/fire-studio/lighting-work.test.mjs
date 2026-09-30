// Recording fixtures check the shipped pool/dispatch contract. Actual WGSL
// compaction, illumination and pixel equality are separate native GPU gates.
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {
  LIGHTING_WORK, LIGHTING_WORK_BUFFER_BYTES, createLightingWork,
  recordLightingWork, lightingWorkShaders, lightWorkEntryWGSL,
  LIGHTING_RECEIVER_BUFFER_BYTES,createLightingReceivers,lightReceiverEntryWGSL,
}=await import(pathToFileURL(path.join(root,'pyro-gpu/lighting-work.js')).href);
const {rendererShaders,dilateWGSL,dilateReceiversWGSL}=await import(pathToFileURL(path.join(root,'pyro-gpu/renderer.js')).href);

globalThis.GPUBufferUsage={STORAGE:128,INDIRECT:256};
const allocated=[],destroyed=[];
const pool=createLightingWork({createBuffer(spec){allocated.push(spec);return {...spec,destroy(){destroyed.push(spec.label);}};}});
assert.deepEqual(allocated.map(x=>[x.label,x.size,x.usage]),[
  ['incident-light-counts',2048,128],['incident-light-offsets',2048,128],
  ['incident-light-indices',131072,128],['incident-light-dispatch',16,384],
]);
assert.equal(Object.values(LIGHTING_WORK_BUFFER_BYTES).reduce((a,b)=>a+b),135184);
const originalBuffers=Object.keys(LIGHTING_WORK_BUFFER_BYTES).map(key=>pool[key]);
const events=[],pipelines={},groups={};
for(const name of ['build','prefix','scatter']){pipelines[name]={name};groups[name]={name};}
const encoder={beginComputePass({label}){events.push(['begin',label]);return {
  setPipeline(p){events.push(['pipeline',p.name]);},
  setBindGroup(index,g){events.push(['group',index,g.name]);},
  dispatchWorkgroups(...dims){events.push(['dispatch',...dims]);},
  end(){events.push(['end']);},
};}};
for(let i=0;i<3;i++)recordLightingWork(encoder,pipelines,groups);
assert.deepEqual(events.filter(x=>x[0]==='dispatch').map(x=>x.slice(1)),[[512],[1],[512],[512],[1],[512],[512],[1],[512]]);
assert.equal(events.filter(x=>x[0]==='end').length,9);
assert.deepEqual(Object.keys(LIGHTING_WORK_BUFFER_BYTES).map(key=>pool[key]),originalBuffers,'refresh never reallocates resources');
pool.destroy();assert.deepEqual(destroyed,allocated.map(x=>x.label));
let receiverAllocation;
const receiver=createLightingReceivers({createBuffer(spec){receiverAllocation=spec;return {spec};}});
assert.equal(LIGHTING_RECEIVER_BUFFER_BYTES,131072);
assert.deepEqual(receiverAllocation,{label:'incident-light-receivers',size:131072,usage:128});
assert.equal(receiver.spec,receiverAllocation);

// The production receiver test must remain camera demand (&1), while every
// shadow ray still checks positive-soot support (&2). No density cutoff is
// introduced in compaction, and the dense comparison shader remains present.
assert.equal(LIGHTING_WORK.brickCount,32768);assert.equal(LIGHTING_WORK.incidentBit,1);
for(const name of ['build','scatter'])assert.ok(lightingWorkShaders[name].includes('(source[id.x]&INCIDENT_BIT)!=0u'));
assert.ok(lightingWorkShaders.scatter.includes('textureStore(lightOut,vec3i(at),vec4f(0,0,0,1))'));
assert.ok(lightingWorkShaders.prefix.includes('dispatch.count=total'));
assert.ok(lightWorkEntryWGSL.includes('if(index>=lightDispatch.count){return;}'));
for(const tree of [false,true])for(const sparse of [false,true]){
  const shaders=rendererShaders(tree,sparse);
  assert.ok(shaders.light.includes('let b=id/2u;let litRegion='),'dense baseline retained');
  assert.ok(shaders.lightWork.endsWith(lightWorkEntryWGSL));
  assert.ok(shaders.lightWork.includes('(occupied[brick.x+32u*(brick.y+32u*brick.z)]&2u)!=0u'));
  assert.ok(shaders.lightWork.includes('let step=(end-start)/12.'));
  assert.ok(shaders.lightWork.includes('@binding(26)'));assert.ok(shaders.lightWork.includes('@binding(27)'));
  assert.ok(shaders.lightReceivers.endsWith(lightReceiverEntryWGSL));
  assert.ok(shaders.lightReceivers.includes('@binding(30)'));
  assert.ok(!shaders.lightReceivers.includes('@binding(26)'),'default receiver path has no queue resource');
}
assert.ok(dilateReceiversWGSL.includes('@binding(2) var<storage,read_write> receiverFlags'));
assert.ok(dilateReceiversWGSL.includes('destination[index]=alive'));
assert.ok(dilateReceiversWGSL.includes('receiverFlags[index]=select(0u,receivers,(alive&1u)!=0u)'));
assert.ok(dilateWGSL.includes('alive|=source['),'original halo remains available for QA');
// Continuous interpolation proof is separable. Check every source texel and
// every light texel along one axis, including the clamped domain boundaries.
for(let i=0;i<256;i++)for(let j=0;j<64;j++){
  if(Math.max(0,(i-.5)/4,j-.5)<Math.min(64,(i+1.5)/4,j+1.5)){
    const brick=Math.floor(i/8);assert.ok(j>=2*brick-1&&j<=2*brick+2);
  }
}
for(let z=-1;z<=1;z++)for(let y=-1;y<=1;y++)for(let x=-1;x<=1;x++)for(let c=0;c<8;c++){
  const bits=[85,255,170][x+1]&[51,255,204][y+1]&[15,255,240][z+1];
  const parity=[c&1,(c>>1)&1,c>>2];
  assert.equal(Boolean(bits&(1<<c)),[x,y,z].every((v,k)=>v===0||v===(parity[k]===0?-1:1)));
}
console.log('PASS: lifetime receiver buffer, continuous interpolation footprint, complete inactive-clear contract, independent soot support, optional queue ordering and dense/sparse/tree shader families. Native pixels/timings remain separate evidence.');
