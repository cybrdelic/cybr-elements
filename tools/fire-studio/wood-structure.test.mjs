import test from 'node:test';import assert from 'node:assert/strict';
import {resolve} from 'node:path';import{fileURLToPath,pathToFileURL}from'node:url';
import{readFileSync}from'node:fs';
import{createHash}from'node:crypto';
const root=fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const{packWoodStructure,resetWoodStructure,woodBondResponse,woodFailurePass,woodPosePass,woodVertexPose,woodCapVisible,woodStructureWGSL,woodPoseWGSL,woodStructureGLSL,rotateWood,woodRemainingMass,woodDonorMass,woodHierarchicalDonorMass,woodEulerIntervals,WoodStructure}=await import(pathToFileURL(resolve(process.env.FIRE_STUDIO_ROOT||root,'wood-structure.js')).href);
const graph=()=>packWoodStructure({nodes:new Float32Array([0,0,0,0,1,0,1,1,0,2,1,0,1,2,0]),parent:new Int32Array([-1,0,1,2,2]),radius:new Float32Array([.2,.15,.08,.04,.03])});
const cold=()=>({stock:[1,0,0,0],wear:[.06,0,0,1]});
const spent=()=>({stock:[.0001,1,0,.05],wear:[0,1,.9,.01]});
function half(v){const sign=v&32768?-1:1,e=(v>>10)&31,m=v&1023;return sign*(e===0?m*2**-24:e===31?(m?NaN:Infinity):(1+m/1024)*2**(e-15));}

test('fixed graph packing retains physical mass and parent order while rejecting malformed skeletons',()=>{
 const g=graph();assert.equal(g.data.byteLength,g.count*64);assert.equal(g.maxDepth,3);
 let own=0;for(let i=0;i<g.count;i++)own+=g.data[i*16+8];assert.ok(Math.abs(own-g.data[9])<1e-5);
 assert.equal(g.data[11],1);assert.equal(g.data[3],-1);assert.equal(g.layoutVersion,1);
 assert.throws(()=>packWoodStructure({nodes:[0,0,0,0,0,0],parent:[-1,1],radius:[1,1]}));
 assert.throws(()=>packWoodStructure({nodes:[0,0,0,0,0,0],parent:[-1,0],radius:[1,1]}));
 const scaled=woodBondResponse(g,2,cold,{worldScale:2}),normal=woodBondResponse(g,2,cold);
 assert.ok(Math.abs(scaled.remainingMass/normal.remainingMass-8)<1e-9);assert.ok(Math.abs(scaled.capacity/normal.capacity-8)<1e-9);assert.ok(Math.abs(scaled.ratio/normal.ratio-2)<1e-9);
});
test('cold tree has no age-driven fracture and heat alone cannot break an unloaded axial beam',()=>{
 const g=graph();let s=resetWoodStructure(g);
 for(let i=0;i<300;i++)s=woodPosePass(g,woodFailurePass(g,s,cold,{dt:1/30}),{dt:1/30});
 assert.deepEqual(s,resetWoodStructure(g));
 const vertical=packWoodStructure({nodes:[0,0,0,0,1,0,0,2,0],parent:[-1,0,1],radius:[.2,.1,.05]});
 const unloaded=()=>({stock:[0,1,0,0],wear:[0,1,1,0]}),response=woodBondResponse(vertical,1,unloaded,{subtreeMass:0});assert.equal(response.moment,0);assert.equal(response.ratio,0);
 assert.equal(woodFailurePass(vertical,resetWoodStructure(vertical),unloaded,{dt:1/30})[31],0);
});
test('axial upright supports fail under healthy child weight after section loss; cold supports survive',()=>{
 const g=packWoodStructure({nodes:[0,0,0,0,1,0,0,2,0],parent:[-1,0,1],radius:[.2,.1,.08]}),s=resetWoodStructure(g);
 const dry=woodBondResponse(g,1,cold);assert.equal(dry.bendingRatio,0);assert.ok(dry.axialRatio>0&&dry.axialRatio<1);assert.equal(woodFailurePass(g,s,cold,{dt:1/30})[31],0);
 const sampler=(p,i)=>i===1?{stock:[0,1,0,0],wear:[0,1,1,0]}:cold(),mass=woodRemainingMass(g,sampler),weak=woodBondResponse(g,1,sampler,{subtreeMass:mass[1]});assert.equal(weak.bendingRatio,0);assert.ok(mass[1]>0);assert.ok(weak.axialRatio>1);assert.equal(woodFailurePass(g,s,sampler,{dt:1/30})[31],1);
 const tensile=woodBondResponse(g,1,cold,{subtreeMass:0,externalForce:[0,10,0]}),compressive=woodBondResponse(g,1,cold,{subtreeMass:0,externalForce:[0,-10,0]});assert.equal(tensile.axialCapacity/compressive.axialCapacity,2);
 // A force through the joint has no bending moment, but still has shear.
 g.data.set(g.data.slice(16,19),28);const shear=woodBondResponse(g,1,cold,{subtreeMass:0,externalForce:[1e6,0,0]});assert.equal(shear.bendingRatio,0);assert.equal(shear.axialRatio,0);assert.ok(shear.shearRatio>1);
});
test('zero-air samples do not weaken cold beams; unresolved material remains healthy without inventing heat',()=>{
 const g=graph(),full=woodBondResponse(g,2,cold);let calls=0;
 const partial=woodBondResponse(g,2,()=>calls++===0?cold():({stock:[0,0,0,0],wear:[0,0,0,0]}));
 assert.equal(partial.validSamples,1);assert.equal(partial.ratio,full.ratio);assert.equal(partial.capacity,full.capacity);
 const absent=woodBondResponse(g,2,()=>({stock:[0,0,0,0],wear:[0,0,0,0]}));assert.equal(absent.validSamples,0);assert.equal(absent.heat,0);assert.equal(absent.stiffness,1);
 const char=woodBondResponse(g,2,()=>({stock:[0,0,0,.05],wear:[0,0,1,0]}));assert.equal(char.validSamples,5);assert.equal(char.stiffness,0);
});
test('the full reviewed 2631-node tree stays below dry self-weight failure at its unit display scale',()=>{
 const asset=resolve(process.env.FIRE_STUDIO_ROOT||root,'pyro-gpu/objects/forest-tree/structure');const manifest=JSON.parse(readFileSync(resolve(asset,'manifest.json'))),raw=readFileSync(resolve(asset,'nodes.bin'));
 const g={data:new Float32Array(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength)),count:manifest.nodes,maxDepth:manifest.maxDepth};
 assert.equal(g.count,2631);assert.equal(g.maxDepth,54);let peak=0;
 for(let i=0;i<g.count;i++)peak=Math.max(peak,woodBondResponse(g,i,cold).ratio);
 assert.ok(peak<1,`Dry self-weight ratio ${peak}`);const old=resetWoodStructure(g),next=woodFailurePass(g,old,cold,{dt:1/30});
 for(let i=0;i<g.count;i++)assert.equal(next[i*16+15],0);
});
test('loss of load-bearing section lowers capacity and accumulated overload is irreversible',()=>{
 const g=graph(),dry=woodBondResponse(g,2,cold),char=woodBondResponse(g,2,spent);
 assert.ok(char.capacity<dry.capacity*.001);assert.ok(char.ratio>1);let s=resetWoodStructure(g);
 for(let i=0;i<10;i++)s=woodPosePass(g,woodFailurePass(g,s,spent,{dt:1/30}),{dt:1/30});
 assert.equal(s[2*16+15],1);assert.equal(s[2*16+3],2);const next=woodFailurePass(g,s,cold,{dt:1/30});assert.equal(next[2*16+15],1);
 assert.equal(s[15],0,'Anchored root never fractures');
});
test('oxidized supports still carry healthy children; already detached pieces leave ancestor load',()=>{
 const g=graph(),sampler=(p,i)=>i===2?{stock:[0,0,0,0],wear:[0,0,1,0]}:cold();
 const mass=woodRemainingMass(g,sampler),old=resetWoodStructure(g);assert.ok(mass[2]>0);assert.ok(mass[2]<g.data[2*16+9]);
 const next=woodFailurePass(g,old,sampler,{dt:1/30});assert.equal(next[2*16+15],1);
 const separated=woodRemainingMass(g,sampler,next);assert.ok(separated[1]<mass[1]);
 const e=woodEulerIntervals(g);for(let i=0;i<g.count;i++)assert.equal(e.order[e.start[i]],i);assert.equal(e.end[0],g.count);
});
test('two-pass subtree resolution keeps rigid pieces coherent and later ancestor breaks cannot rejoin them',()=>{
 const g=graph(),s=resetWoodStructure(g);s[2*16+15]=1;
 const a=woodPosePass(g,s,{dt:1/30});assert.equal(a[3*16+3],2);assert.equal(a[4*16+3],2);
 const p=woodVertexPose(g,a,3,[2,1,0]);assert.ok(Math.hypot(...p.point.map((x,i)=>x-a[3*16+i]))<1e-6);
 assert.ok(Math.abs(Math.hypot(...a.slice(2*16+4,2*16+8))-1)<1e-6);
 a[3*16+15]=1;const b=woodPosePass(g,a,{dt:1/30});assert.equal(b[3*16+3],3);assert.equal(b[4*16+3],2);
 assert.equal(woodCapVisible(b,3,2),true);assert.equal(woodCapVisible(a,3,2),false);assert.equal(woodCapVisible(b,1,0xffffffff),false);
 assert.deepEqual(resetWoodStructure(g),resetWoodStructure(g));
});
test('falling piece contact is finite and persistent; small time steps do not penetrate its beam floor',()=>{
 const g=graph();let s=resetWoodStructure(g);s[2*16+15]=1;
 for(let i=0;i<500;i++)s=woodPosePass(g,s,{dt:1/120,floorY:0});
 assert.ok(s.every(Number.isFinite));assert.ok(s[2*16+1]>=0);assert.ok(Math.abs(Math.hypot(...s.slice(2*16+4,2*16+8))-1)<1e-6);
 const long=woodPosePass(g,resetWoodStructure(g),{dt:1});assert.deepEqual(long,resetWoodStructure(g));
});
test('free fragments fall through COM; gravity adds no continuing spin after the release impulse',()=>{
 const g=graph();let s=resetWoodStructure(g);s[2*16+15]=1;const dt=1/120;let last=Infinity;
 for(let i=0;i<120;i++){s=woodPosePass(g,s,{dt});const speed=Math.hypot(...s.slice(2*16+12,2*16+15));assert.ok(speed<=last+1e-6);last=speed;}
 const q=Array.from(s.slice(2*16+4,2*16+8)),rest=Array.from(g.data.slice(2*16,2*16+3)),com=Array.from(g.data.slice(2*16+12,2*16+15));
 const offset=rotateWood(q,com.map((v,i)=>v-rest[i])),currentY=s[2*16+1]+offset[1],expectedY=com[1]-9.81*dt*dt*120*121/2;
 assert.ok(Math.abs(currentY-expectedY)<1e-4);assert.ok(Math.abs(s[2*16+9]+9.81)<1e-4);
});
test('all shipped wood companions have valid exact checksums, sealed caps and stable rest ownership',()=>{
 for(const name of ['forest-tree/structure','logs','house','wood-sigil']){
  const path=resolve(process.env.FIRE_STUDIO_ROOT||root,'pyro-gpu/objects',name),m=JSON.parse(readFileSync(resolve(path,'manifest.json')));
  assert.equal(m.caps.openInterfaceEdges,0);assert.ok(m.nodes<4096);assert.ok(m.maxDepth<256);
  for(const[file,proof]of Object.entries(m.files)){const raw=readFileSync(resolve(path,file));assert.equal(raw.byteLength,proof.bytes);assert.equal(createHash('sha256').update(raw).digest('hex'),proof.sha256);}
  const raw=readFileSync(resolve(path,'nodes.bin')),g={data:new Float32Array(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength)),count:m.nodes,maxDepth:m.maxDepth};
  let peak=0;for(let i=0;i<g.count;i++)peak=Math.max(peak,woodBondResponse(g,i,cold).ratio);assert.ok(peak<1,`${name} cold overload ${peak}`);
  const owner=readFileSync(resolve(path,'owners.bin'));assert.equal(owner.byteLength,m.partitionVertices*8);
  const caps=readFileSync(resolve(path,'cap-owner-pairs.bin'));assert.equal(caps.byteLength,m.caps.vertices*8);
  if(name==='wood-sigil'){assert.equal(m.provenance.nativePixelMaskExact,true);assert.equal(m.provenance.components,5);assert.equal(m.provenance.holes,1);assert.ok(m.provenance.proxyInventory.occupiedCells>0);assert.ok(m.provenance.proxyInventory.relativeQuantizationError<.0002);}
 }
});
test('actual corrected cold proxy fields cannot induce failure through holes or subvoxel zero-air samples',()=>{
 for(const name of ['forest-tree/structure','logs','house','wood-sigil']){
  const path=resolve(process.env.FIRE_STUDIO_ROOT||root,'pyro-gpu/objects',name),m=JSON.parse(readFileSync(resolve(path,'manifest.json'))),raw=readFileSync(resolve(path,'nodes.bin'));
  const g={data:new Float32Array(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength)),count:m.nodes,maxDepth:m.maxDepth};
  const bytes=readFileSync(resolve(path,m.thermalProxy)),field=new Uint16Array(bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
  const sample=p=>{const q=p.map(v=>Math.max(0,Math.min(63,Math.floor((v+1.5)*64/3)))),o=(q[0]+64*(q[1]+64*q[2]))*4,d=half(field[o]),capacity=half(field[o+1]),material=half(field[o+3]);const valid=capacity>0&&((material>.5&&material<2.5&&d<=0)||(material>7.5&&d<.07));return valid?cold():{stock:[0,0,0,0],wear:[0,0,0,0]};};
  const next=woodFailurePass(g,resetWoodStructure(g),sample,{dt:1/30});for(let i=0;i<g.count;i++)assert.equal(next[i*16+15],0,`${name} node${i}`);
  let sum=0;for(let i=0;i<g.count;i++)sum+=g.data[i*16+8];assert.ok(Math.abs(sum-m.massCalibration.finiteProxyMassKg)<.0001);
 }
});
test('actual four-source donor reductions conserve subtree loads and bounded microkg quantization',()=>{
 for(const name of ['forest-tree/structure','logs','house','wood-sigil']){
  const path=resolve(process.env.FIRE_STUDIO_ROOT||root,'pyro-gpu/objects',name),m=JSON.parse(readFileSync(resolve(path,'manifest.json'))),raw=readFileSync(resolve(path,'nodes.bin'));
  const g={data:new Float32Array(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength)),count:m.nodes,maxDepth:m.maxDepth};const ownerbytes=readFileSync(resolve(path,'voxel-owners.bin')),owners=new Uint32Array(ownerbytes.buffer.slice(ownerbytes.byteOffset,ownerbytes.byteOffset+ownerbytes.byteLength));const metaBytes=readFileSync(resolve(path,m.fluxMetadata)),metadata=new Float32Array(metaBytes.buffer.slice(metaBytes.byteOffset,metaBytes.byteOffset+metaBytes.byteLength)),stock=new Float32Array(metadata.length);
  for(let i=0;i<owners.length;i++)stock[i*4]=1;
  const exact=woodDonorMass(g,{owners,metadata,stock}),q=woodDonorMass(g,{owners,metadata,stock,quantized:true});assert.ok(Math.abs(exact[0]-m.massCalibration.finiteProxyMassKg)<.0001);
  assert.deepEqual(Array.from(woodHierarchicalDonorMass(g,{owners,metadata,stock}),x=>Math.round(x*1e6)),Array.from(q,x=>Math.round(x*1e6)),`${name} owner-first cold integer parity`);
  let drift=0;for(let i=0;i<g.count;i++)drift=Math.max(drift,Math.abs(q[i]-exact[i]));assert.ok(drift/exact[0]<.001,`${name} maximum node counter drift ${drift}`);
  for(let i=0;i<owners.length;i++)stock[i*4]=i%7/7;
  const hot=woodDonorMass(g,{owners,metadata,stock}),hotQ=woodDonorMass(g,{owners,metadata,stock,quantized:true});for(let i=0;i<g.count;i++)assert.ok(Math.abs(hotQ[i]-hot[i])/exact[0]<.001);
  assert.deepEqual(Array.from(woodHierarchicalDonorMass(g,{owners,metadata,stock}),x=>Math.round(x*1e6)),Array.from(hotQ,x=>Math.round(x*1e6)),`${name} owner-first fractional integer parity`);
  const state=resetWoodStructure(g);for(let i=1;i<g.count;i++)if(i%17===0&&g.data[i*16+11]<.5)state[i*16+15]=1;
  const detached=woodDonorMass(g,{owners,metadata,stock,state,quantized:true});assert.deepEqual(Array.from(woodHierarchicalDonorMass(g,{owners,metadata,stock,state}),x=>Math.round(x*1e6)),Array.from(detached,x=>Math.round(x*1e6)),`${name} owner-first detached integer parity`);
 }
});
test('shader helpers expose one stable local pose and keep wrapper resources fixed across frames/reset',async()=>{
 const code=woodStructureWGSL();assert.match(code,/@binding\(35\)/);assert.match(code,/@binding\(43\)/);assert.doesNotMatch(code,/export class|\.xyz\s*=/);
 assert.match(code,/@binding\(47\)/);assert.match(code,/fn woodMassAggregate/);const scatter=code.slice(code.indexOf('fn woodMassScatter'),code.indexOf('fn woodMassAggregate'));assert.doesNotMatch(scatter,/woodNodes\[|woodOld\[|for\(/);
 assert.match(woodPoseWGSL(),/woodInversePose/);assert.match(woodStructureGLSL(),/step<=54/);
 globalThis.GPUBufferUsage={STORAGE:1,COPY_DST:2,COPY_SRC:4,UNIFORM:8};let buffers=0,groups=0,dispatch=0,destroyed=0;
 const writes=[];const device={queue:{writeBuffer:(...a)=>writes.push(a)},createBuffer:o=>{buffers++;return{...o,destroy:()=>destroyed++}},createShaderModule:o=>o,createComputePipelineAsync:async o=>({...o,getBindGroupLayout:()=>o.compute.entryPoint}),createBindGroup:o=>{groups++;return o}};
 const g=graph(),w=await new WoodStructure(device,{nodes:g.data,count:g.count,maxDepth:g.maxDepth}).init();const handle=w.state;
 const encoder={beginComputePass:()=>({setPipeline(){},setBindGroup(){},dispatchWorkgroups(n,y,z){assert.ok(n===1||(n===16&&y===16&&z===16));dispatch++},end(){}})},skin={},wear={},owners={},metadata={};
 w.encode(encoder,{dt:1/60,skin,wear,owners,metadata,origin:[0,1,0],scale:2});w.encode(encoder,{dt:1/60,skin,wear,owners,metadata,origin:[0,1,0],scale:2});w.reset();
 assert.equal(buffers,8);assert.equal(groups,5);assert.equal(dispatch,10);assert.equal(w.state,handle);assert.equal(w.poseBindings()[1].resource.buffer,handle);
 assert.equal(w.encode(encoder,{dt:0,skin,wear}),false);assert.equal(writes.at(-1)[2].every(x=>x===0),true);w.dispose();assert.equal(destroyed,8);
});
test('partial allocation, upload and compile failures release all buffers and allow a clean retry',async()=>{
 globalThis.GPUBufferUsage={STORAGE:1,COPY_DST:2,COPY_SRC:4,UNIFORM:8};const g=graph();
 for(const mode of ['allocation','bounds-upload','compile','reset']){
  let created=0,failed=false;const destroyed=new Set();
  const device={queue:{writeBuffer(buffer){if(!failed&&((mode==='bounds-upload'&&buffer.label==='wood subtree bounds')||(mode==='reset'&&buffer.label==='wood pose stable'))){failed=true;throw Error(mode);}}},
   createBuffer(o){if(!failed&&mode==='allocation'&&created===3){failed=true;throw Error(mode);}const id=created++;return{...o,destroy(){assert.equal(destroyed.has(id),false,'No double destruction');destroyed.add(id);}};},
   createShaderModule:o=>o,async createComputePipelineAsync(o){if(!failed&&mode==='compile'&&o.compute.entryPoint==='woodFailure'){failed=true;throw Error(mode);}return{...o,getBindGroupLayout:()=>o.compute.entryPoint};}};
  const w=new WoodStructure(device,{nodes:g.data,count:g.count,maxDepth:g.maxDepth});await assert.rejects(w.init(),new RegExp(mode));assert.equal(destroyed.size,created);assert.equal(w.ready,false);assert.equal(w.state,null);w.dispose();assert.equal(destroyed.size,created);
  await w.init();assert.equal(w.ready,true);assert.equal(w.disposed,false);assert.equal(created-destroyed.size,8);w.dispose();assert.equal(destroyed.size,created);
 }
 let release;const pending=new Promise(resolve=>release=resolve),destroyed=new Set();let created=0;
 const device={queue:{writeBuffer(){}},createBuffer(o){const id=created++;return{...o,destroy(){assert.equal(destroyed.has(id),false);destroyed.add(id);}};},createShaderModule:o=>o,async createComputePipelineAsync(o){await pending;return o;}};
 const w=new WoodStructure(device,{nodes:g.data,count:g.count,maxDepth:g.maxDepth}),initializing=w.init();w.dispose();release();await assert.rejects(initializing,/disposed during initialization/);assert.equal(created,8);assert.equal(destroyed.size,8);assert.equal(w.ready,false);
});
test('120 alternating production field frames reuse both bind-group pairs and reset preserves them',async()=>{
 globalThis.GPUBufferUsage={STORAGE:1,COPY_DST:2,COPY_SRC:4,UNIFORM:8};const g=graph();let buffers=0,groups=0,dispatch=0,destroyed=0,expectedSkin,expectedWear;
 const device={queue:{writeBuffer(){}},createBuffer(o){buffers++;return{...o,destroy(){destroyed++;}};},createShaderModule:o=>o,async createComputePipelineAsync(o){return{...o,getBindGroupLayout:()=>o.compute.entryPoint};},createBindGroup(o){groups++;return o;}};
 const encoder={beginComputePass:()=>({setPipeline(){},setBindGroup(index,group){if(['woodMassScatter','woodFailure'].includes(group.layout)){assert.equal(group.entries.find(e=>e.binding===12).resource,expectedSkin);if(group.layout==='woodFailure')assert.equal(group.entries.find(e=>e.binding===15).resource,expectedWear);}},dispatchWorkgroups(){dispatch++;},end(){}})};
 const w=await new WoodStructure(device,{nodes:g.data,count:g.count,maxDepth:g.maxDepth}).init(),skins=[{},{}],wears=[{},{}],owners={},metadata={},pose=w.state;
 for(let frame=0;frame<120;frame++){const slot=frame%2;expectedSkin=skins[slot];expectedWear=wears[slot];w.encode(encoder,{dt:1/60,skin:expectedSkin,wear:expectedWear,owners,metadata});if(frame%17===0)w.reset();if(frame>=1){assert.equal(groups,7);assert.equal(buffers,8);}}
 assert.equal(dispatch,600);assert.equal(w.state,pose);assert.equal(w.fieldGroups.length,2);assert.equal(w.fieldGroups[0].pose,w.fieldGroups[1].pose);w.dispose();assert.equal(destroyed,8);assert.equal(w.fieldGroups.length,0);assert.equal(w.fixedGroups,null);
});
