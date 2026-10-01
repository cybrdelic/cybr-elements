import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {PyroSolver}=await import(pathToFileURL(path.join(root,'pyro-gpu/solver.js')).href);
const {expandFuelDeposits}=await import(pathToFileURL(path.join(root,'pyro-gpu/floor-fuel.js')).href);
globalThis.GPUTextureUsage={TEXTURE_BINDING:1,STORAGE_BINDING:2,COPY_DST:4};
function fixture(){
 let allocations=0;const calls=[],uploads=[];
 const resource=()=>({createView(){return {id:++allocations};},destroy(){}});
 const device={lost:new Promise(()=>{}),addEventListener(){},
  createTexture(options){allocations++;const t=resource();t.options=options;return t;},
  createShaderModule({code}){return {code,getCompilationInfo:async()=>({messages:[]})};},
  async createComputePipelineAsync({compute,label}){return {label,code:compute.module.code,getBindGroupLayout(){return {};}};},
  createBindGroup({entries}){assert.equal(entries.length,new Set(entries.map(e=>e.binding)).size);return {entries};},
  queue:{writeTexture(target,data){uploads.push({target,data:data.slice()});},submit(){},},
  createCommandEncoder(){return encoder;},
 };
 const encoder={beginComputePass(){let pipeline,group;return {setPipeline(v){pipeline=v;},setBindGroup(_,v){group=v;},
  dispatchWorkgroups(...work){calls.push({label:pipeline.label,entries:group.entries,work});},end(){}};},finish(){return {};}};
 const solver=new PyroSolver(device,{}, {context:{configure(){}},format:'rgba8unorm'});
 solver.sampler={};solver.c=[{view:{id:'chem0'}},{view:{id:'chem1'}}];
 return {solver,device,encoder,calls,uploads,allocations:()=>allocations};
}
test('floor inventory has fixed small storage and cold input never writes chemistry',async()=>{
 const f=fixture(),s=f.solver;await s.initFloorFuel();const count=f.allocations();
 s.updateFloorFuel(f.encoder,{},0);assert.equal(f.calls.length,0,'skip before any fuel is placed');
 assert.equal(s.dropFuel([99,99]),false);assert.equal(s.hasFloorFuel,false,'invalid placement does not clamp into the scene');
 assert.equal(s.dropFuel([.2,.1]),true);s.updateFloorFuel(f.encoder,{},0);
 assert.equal(f.uploads.length,1);assert.ok(f.uploads[0].data.some(x=>x>0));
 assert.deepEqual(f.calls.map(c=>c.label),['floor-fuel','floor-deposits-clear']);
 assert.equal(f.calls[0].entries.find(e=>e.binding===2).resource,s.c[0].view,'heat reads current chemistry');
 assert.ok(!f.calls[0].entries.some(e=>e.binding===5&&s.c.some(c=>c.view===e.resource)),'no gas write from the deposit pass');
 assert.equal(s.floorBindings()[0][1],s.floorFuel[1]);
 for(let i=0;i<120;i++)s.updateFloorFuel(f.encoder,{},i%2);
 assert.equal(f.uploads.length,1,'mass is uploaded exactly once, not replenished while held idle');
 assert.equal(f.calls.filter(c=>c.label==='floor-deposits-clear').length,1);
 assert.equal(f.allocations(),count,'no GPU allocations during placed-fuel steps');
 assert.equal(s.resources.length,5);
});
test('clearing placed fuel clears both inventory generations and pending mass without touching gas',async()=>{
 const f=fixture(),s=f.solver;await s.initFloorFuel();s.dropFuel([0,0]);s.updateFloorFuel(f.encoder,{},0);
 s.dropFuel([1,1]);s.clearFuel();assert.equal(s.hasFloorFuel,false);assert.equal(s.floorIndex,0);
 assert.equal(s.fuelBrush.consume(),null);const clear=f.calls.at(-2);
 assert.equal(clear.label,'floor-fuel-clear');assert.deepEqual(clear.work,[16,16]);
 assert.deepEqual(clear.entries.map(e=>e.resource),[s.floorFuel[0].view,s.floorFuel[1].view,s.floorDeposits.view]);
 assert.equal(f.calls.at(-1).label,'floor-wood-wear-clear');
 assert.deepEqual(f.calls.at(-1).entries.map(e=>e.resource),s.floorWear.map(t=>t.view));
});
test('half upload expansion retains cold positive mass and rejects invalid values',()=>{
 assert.deepEqual([...expandFuelDeposits(new Uint16Array([0,1,0x3800,0x4400,0x7c00,0xbc00]),new Float32Array(6))],[0,2**-24,.5,4,0,0]);
});
test('ignition is an explicit one-step request, and source-guide changes keep cached lighting',async()=>{
 const f=fixture(),s=f.solver;await s.initFloorFuel();assert.equal(s.igniteFuel(),false);
 s.dropFuel([0,0]);assert.equal(s.floorIgnition,false,'placement has no thermal impulse');
 s.smoke=true;assert.equal(s.igniteFuel(),false,'A smoke-only source cannot consume fuel without combustion');s.smoke=false;
 assert.equal(s.igniteFuel(),true);assert.equal(s.floorIgnition,true);s.updateFloorFuel(f.encoder,{},0);
 assert.equal(s.floorIgnition,false,'only the first step receives the impulse');
 s.view={};f.device.queue.writeBuffer=()=>{};
 const camera=Array(48).fill(0);camera[19]=24;s.camera(camera);s.lightReady=true;
 camera[23]=10;s.camera(camera);assert.equal(s.lightReady,true,'substrate toggle has no extra light pass');
 camera[20]=1;s.camera(camera);assert.equal(s.lightReady,false,'actual ambient change relights');
});
