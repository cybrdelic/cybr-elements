import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {PyroSolver}=await import(pathToFileURL(path.join(root,'pyro-gpu/solver.js')).href);
globalThis.GPUBufferUsage={STORAGE:1,COPY_DST:2,INDIRECT:4,COPY_SRC:8};
globalThis.GPUTextureUsage={TEXTURE_BINDING:1,STORAGE_BINDING:2,COPY_DST:4};
const fixture=()=>{
 let allocations=0;const calls=[];
 const resource=name=>({name,destroy(){}}),texture=name=>({n:256,view:resource(name)});
 const pass=()=>{let pipe,group;return {
  setPipeline(p){pipe=p;},setBindGroup(_,g){group=g;},end(){},
  dispatchWorkgroups(...work){calls.push({pipe:pipe.label,group,work});},
  dispatchWorkgroupsIndirect(buffer,offset){calls.push({pipe:pipe.label,group,buffer,offset});},
 };};
 const device={
  createTexture(settings){allocations++;return {createView:()=>resource('texture-'+allocations),destroy(){}};},
  createBuffer(settings){allocations++;return {...settings,name:'buffer-'+allocations,destroy(){}};},
  createShaderModule:()=>({getCompilationInfo:async()=>({messages:[]})}),
  createComputePipelineAsync:async settings=>({label:settings.label,getBindGroupLayout:()=>({})}),
  createBindGroup(settings){assert.equal(new Set(settings.entries.map(e=>e.binding)).size,settings.entries.length);return settings;},
  queue:{writeBuffer(){}},
 };
 const s=Object.assign(Object.create(PyroSolver.prototype),{device,N:128,D:256,pressureWork:true,resources:[],cache:new Map(),ids:new WeakMap(),nextId:0,textureId:0,
  visibleBricks:resource('visible'),light:texture('light'),sampler:resource('sampler'),v:[texture('oldv'),texture('newv'),texture('predv')],
  c:[texture('oldc'),texture('newc'),texture('predc')],vort:texture('curl'),bricks:resource('chem-work'),indirect:resource('chem-args'),
  opticalMasks:[resource('optical-a'),resource('optical-b')],
  sigilSource:texture('sigil'),objectId:null,objectModels:{},emptyObject:texture('empty'),objectSettings:resource('object'),surface:[texture('surface')],si:0,
  pipelines:Object.fromEntries(['advectVelocity','curl','correctVelocity'].map(name=>[name,{label:name,getBindGroupLayout:()=>({})}])),
 });
 return {s,calls,allocations:()=>allocations,encoder:{clearBuffer(buffer){calls.push({clear:buffer});},beginComputePass:pass}};
};
test('actual candidate allocates once and records bounded coarse/fine/dense commands without per-step allocations',async()=>{
 const {s,calls,encoder,allocations}=fixture();await s.initAdaptive();const initial=allocations();
 const base=[[0,{buffer:{}}],[1,s.sampler]];
 for(let step=0;step<1000;step++)s.adaptiveVelocity(encoder,base,step%2,step%2);
 assert.equal(allocations(),initial);
 const first=calls.slice(0,19);
 assert.equal(first[0].clear,s.flowChemArgs);
 assert.equal(first[1].pipe,'adaptive-flow-sourceWork');
 assert.equal(first[2].pipe,'adaptive-flow-restrict');
 assert.equal(first[3].clear,s.flowMask);
 assert.equal(first[4].pipe,'adaptive-flow-chemistry');
 assert.equal(first[5].pipe,'adaptive-flow-mark');
 assert.ok(first.some(c=>c.pipe==='adaptive-flow-fill'));
 assert.ok(calls.some(c=>c.pipe==='adaptive-flow-fineAdvect'&&c.offset===24));
 assert.ok(calls.some(c=>c.pipe==='advectVelocity'&&c.offset===48));
 assert.ok(calls.some(c=>c.pipe==='correctVelocity'&&c.offset===72));
 assert.equal(s.flowCommands.size,168);
 assert.deepEqual(s.coarseV.map(v=>v.n),[65,65,65]);
 assert.equal(s.adaptivePressure,undefined);
});
