import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {PyroSolver}=await import(pathToFileURL(path.join(root,'pyro-gpu/solver.js')).href);
const {initialAdaptiveFlowCommands,ADAPTIVE_FLOW_OFFSETS}=await import(pathToFileURL(path.join(root,'pyro-gpu/adaptive-flow.js')).href);
const {createBrickPool}=await import(pathToFileURL(path.join(root,'pyro-gpu/brick-pool.js')).href);

globalThis.GPUBufferUsage={STORAGE:1,COPY_DST:2,INDIRECT:4,COPY_SRC:8,MAP_READ:16,UNIFORM:32};
globalThis.GPUTextureUsage={TEXTURE_BINDING:1,STORAGE_BINDING:2,COPY_DST:4,RENDER_ATTACHMENT:8,COPY_SRC:16};
globalThis.GPUMapMode={READ:1};

// Record actual solver methods and actual pool command encoding. No GPU
// arithmetic is emulated: shader/pixel fidelity has separate native gates.
function fixture(){
 const calls=[],writes=[],modules=[],buffers=[];
 let allocations=0,groups=0;
 const resource=name=>({name,destroy(){}}),texture=name=>({n:256,view:resource(name)});
 const pipeline=name=>({label:name,getBindGroupLayout:()=>({})});
 const pass=()=>{let pipe,group;return {
  setPipeline(p){pipe=p;},setBindGroup(_,g){group=g;},end(){},
  dispatchWorkgroups(...work){calls.push({pipe:pipe.label,group,work});},
  dispatchWorkgroupsIndirect(buffer,offset){calls.push({pipe:pipe.label,group,buffer,offset});},
  draw(...draw){calls.push({pipe:pipe.label,group,draw});},
 };};
 const encoder={clearBuffer(buffer){calls.push({clear:buffer});},beginComputePass:pass,beginRenderPass:pass,
  finish(){return this;},copyBufferToBuffer(...copy){calls.push({copy});},
  copyTextureToBuffer(from,to,size){
   calls.push({pixelCopy:[from,to,size]});
   const bytes=new Uint8Array(to.buffer.data);
   for(let y=0;y<size[1];y++)for(let x=0;x<size[0]*4;x++)bytes[y*to.bytesPerRow+x]=(y*size[0]*4+x)%256;
  },
 };
 const device={
  limits:{maxTextureDimension3D:256},features:new Set(),lost:new Promise(()=>{}),addEventListener(){},
  createTexture(){allocations++;return {createView:()=>resource('texture-'+allocations),destroy(){}};},
  createBuffer(settings){
   allocations++;const buffer={...settings,name:'buffer-'+allocations,data:new ArrayBuffer(settings.size),mapState:'unmapped',destroyed:false,
    async mapAsync(){this.mapState='mapped';},getMappedRange(){return this.data;},unmap(){this.mapState='unmapped';},destroy(){this.destroyed=true;this.mapState='unmapped';}};
   buffers.push(buffer);return buffer;
  },
  createShaderModule(settings){modules.push(settings);return {...settings,getCompilationInfo:async()=>({messages:[]})};},
  createComputePipelineAsync:async settings=>pipeline(settings.label),
  createRenderPipelineAsync:async settings=>pipeline(settings.label||'volume-render'),
  createBindGroup(settings){groups++;assert.equal(new Set(settings.entries.map(e=>e.binding)).size,settings.entries.length,'no binding collisions');return settings;},
  createCommandEncoder:()=>encoder,
  queue:{writeBuffer(buffer,offset,value){writes.push({buffer,offset,value:value.slice()});},submit(command){calls.push({submit:command});},onSubmittedWorkDone:async()=>{}},
 };
 const s=Object.assign(Object.create(PyroSolver.prototype),{
 emptyShockRM:{},shockRemaining:0,measureProjection:{name:"measure-final-velocity",label:"measure-final-velocity",getBindGroupLayout(){return{};}},reactionLedger:{},reactionOffset:0,
  sourcePipelineCache:new Map(),powerKind:null,
  device,N:128,D:256,resources:[],cache:new Map(),ids:new WeakMap(),nextId:0,textureId:0,
  visibleBricks:resource('visible'),light:texture('light'),sampler:resource('sampler'),
  v:[texture('oldv'),texture('newv'),texture('predv')],c:[texture('oldc'),texture('newc'),texture('predc')],vort:texture('curl'),
  bricks:resource('chem-work'),indirect:resource('chem-args'),opticalMasks:[resource('optical-a'),resource('optical-b')],
  sigilSource:texture('sigil'),objectId:null,objectModels:{},emptyObject:texture('empty'),objectSettings:resource('object'),
  surface:[texture('surface-a'),texture('surface-b')],damage:[texture('wear-a'),texture('wear-b')],si:0,
  canvas:{width:3,height:2},stateEpoch:0,time:0,burstAge:2,shockRemaining:0,maxSpeed:1,seed:2,source:[0,.58,0],active:true,fuel:0,
  effect:[0,1,.085,1],dynamics:[1,1,1,1],chemistry:[1,1,1,1],embers:true,smoke:false,color:'natural',
  view:resource('camera'),stats:resource('stats'),groupStats:resource('group-stats'),params:Array.from({length:12},()=>resource('params')),
  frameNumber:0,completedFrames:0,inFlight:[],errors:[],telemetrySlots:[],latestTelemetry:{maxSpeed:1,sampleFrame:0,gpu:null},
  lightReady:false,roomVisible:true,usingTree:false,useLightWork:false,useLightReceivers:true,vi:0,ci:0,
  rendererFamilies:new Map(),masks:[resource('mask-a'),resource('mask-b')],emberBuffer:resource('embers'),
  lightSeeds:resource('light-seeds'),fireLights:resource('fire-lights'),roomTargets:[texture('direct-room'),texture('bounce-room')],
  lightingReceivers:resource('receivers'),dilatePipeline:pipeline('visible-bricks'),clearPipeline:pipeline('clear-state'),
  surfacePipeline:pipeline('surface-fuel'),surfaceResetPipeline:pipeline('surface-reset'),damageResetPipeline:pipeline('wood-damage-reset'),
  emberPipeline:pipeline('embers'),emberRender:pipeline('ember-render'),present:pipeline('present'),
  output:resource('output'),outputView:resource('output-view'),context:{getCurrentTexture:()=>({createView:()=>resource('swapchain')})},
  prepareSource:async()=>{},
  floorFuel:[texture('floor-a'),texture('floor-b')],floorWear:[texture('floor-wear-a'),texture('floor-wear-b')],floorDeposits:texture('floor-deposits'),floorIndex:0,hasFloorFuel:false,
  floorClear:pipeline('floor-fuel-clear'),floorWearClear:pipeline('floor-wood-wear-clear'),fuelBrush:{clear(){}},
 });
 s.pipelines=Object.fromEntries(['diffuseScalar','advectVelocity','curl','correctVelocity','rhs','project','reduceStats','buildBricks','advectScalar','correctScalar'].map(name=>[name,pipeline(name)]));
 s.levels=[{n:128,p:[texture('pressure-a'),texture('pressure-b')],b:texture('rhs'),current:0}];
 // Pressure arithmetic is not this fixture's subject; command ownership and
 // every field consumer around the borrowed pressure pass remain actual.
 s.vcycle=()=>{};
 return {s,calls,writes,modules,buffers,encoder,pipeline,texture,resource,
  allocations:()=>allocations,groups:()=>groups,
  async pool(){s.chemistryPool=await createBrickPool(device,{capacity:1024});return s.chemistryPool;},
 };
}
function bindings(call){return new Map(call.group.entries.map(({binding,resource})=>[binding,resource]));}
function assertCurrentField(call,pool,ci,render=false){
 const entry=bindings(call);
 assert.equal(entry.get(render?25:20),pool.fields[ci].view,call.pipe+' current atlas');
 assert.equal(entry.get(render?28:23).buffer,pool.pageTable,call.pipe+' current page table');
 assert.equal(entry.get(render?29:24).buffer,pool.metadata,call.pipe+' metadata');
}
function tree(f){
 const {s,texture,resource,pipeline}=f;
 s.usingTree=true;s.objectId='cybr-tree';s.objectModels['cybr-tree']=texture('tree-object');
 s.damage=[texture('damage-a'),texture('damage-b')];s.treeSurfacePipeline=pipeline('tree-surface-fuel');
 const mesh=[[18,texture('mesh-position')],[19,texture('mesh-normal')],[20,texture('mesh-color')]];
 const shadow=[[23,texture('mesh-shadow')],[24,resource('mesh-compare')]];
 s.forestMesh={render(){},shadows(){},bindings:()=>mesh,shadowBindings:()=>shadow};
}

test('new architecture remains opt-in while receiver support can be enabled independently',()=>{
 const {s}=fixture();
 const actual=new PyroSolver(s.device,s.canvas,{context:{configure(){}},format:'rgba8unorm'});
 assert.equal(actual.useLightReceivers,false);assert.equal(actual.useLightWork,false);
 assert.equal(actual.useBrickPool,false);assert.equal(actual.adaptive,false);assert.equal(actual.pressureWork,false);
 const receivers=new PyroSolver(s.device,s.canvas,{context:{configure(){}},format:'rgba8unorm',lightReceivers:true});
 assert.equal(receivers.useLightReceivers,true);assert.equal(receivers.useLightWork,false);
 assert.equal(receivers.useBrickPool,false);assert.equal(receivers.adaptive,false);
});

test('reset restores GPU classifier commands, clears pooled state and allocates no resources',async()=>{
 const f=fixture(),{s,writes,calls,allocations}=f;const pool=await f.pool();await s.initAdaptive();
 const before=allocations();s.time=10;s.lightReady=true;s.stateEpoch=5;
 writes.length=0;calls.length=0;await s.reset();
 const commandWrites=writes.filter(x=>x.buffer===s.flowCommands);
 assert.equal(commandWrites.length,1);assert.equal(commandWrites[0].offset,0);
 assert.deepEqual(commandWrites[0].value,initialAdaptiveFlowCommands(s.N,s.D));
 assert.equal(commandWrites[0].value[ADAPTIVE_FLOW_OFFSETS.stickyDense/4],0);
 assert.equal(allocations(),before);assert.equal(s.time,0);assert.equal(s.lightReady,false);assert.equal(s.stateEpoch,6);
 assert.ok(calls.some(x=>x.pipe==='chemistry-pool-reset'));
 for(const mask of [...s.masks,...s.opticalMasks])assert.ok(calls.some(x=>x.clear===mask));
 assert.equal(pool.pageTable,pool.pages[0]);
});

test('capture copies padded output without resetting flow or changing the current field',async()=>{
 const f=fixture(),{s,writes,buffers,calls}=f;await f.pool();await s.initAdaptive();
 s.time=7;s.ci=1;s.vi=1;s.stateEpoch=3;const page=s.chemistryPool.pageTable;
 writes.length=0;calls.length=0;const bytes=await s.pixels();
 assert.deepEqual(Array.from(bytes),Array.from({length:24},(_,i)=>i));
 assert.equal(writes.some(x=>x.buffer===s.flowCommands),false);
 assert.equal(calls.some(x=>x.pipe==='chemistry-pool-reset'||x.clear),false);
 assert.equal(s.time,7);assert.equal(s.ci,1);assert.equal(s.vi,1);assert.equal(s.stateEpoch,3);
 assert.equal(s.chemistryPool.pageTable,page);assert.equal(buffers.at(-1).destroyed,true);
});

test('failed capture mappings release the temporary readback buffer',async()=>{
 const f=fixture(),{s,buffers}=f;const create=s.device.createBuffer.bind(s.device);
 s.device.createBuffer=spec=>{const b=create(spec);b.mapAsync=async()=>{throw Error('capture map rejected');};return b;};
 await assert.rejects(s.pixels(),/capture map rejected/);
 assert.equal(buffers.at(-1).destroyed,true);
 assert.equal(buffers.at(-1).mapState,'unmapped');
});

test('failed capture range access unmaps and destroys its buffer',async()=>{
 const f=fixture(),{s,buffers}=f;const create=s.device.createBuffer.bind(s.device);let unmaps=0;
 s.device.createBuffer=spec=>{
  const b=create(spec),unmap=b.unmap.bind(b);
  b.getMappedRange=()=>{throw Error('capture range rejected');};b.unmap=()=>{unmaps++;unmap();};return b;
 };
 await assert.rejects(s.pixels(),/capture range rejected/);
 assert.equal(unmaps,1);assert.equal(buffers.at(-1).destroyed,true);assert.equal(buffers.at(-1).mapState,'unmapped');
});

test('capture preserves submitted dimensions while a viewport resize awaits mapping',async()=>{
 const f=fixture(),{s}=f;const create=s.device.createBuffer.bind(s.device);let resolveMap;
 s.device.createBuffer=spec=>{
  const b=create(spec);b.mapAsync=()=>new Promise(resolve=>{resolveMap=()=>{b.mapState='mapped';resolve();};});return b;
 };
 const pending=s.pixels();assert.ok(resolveMap);
 s.canvas.width=1;s.canvas.height=1;resolveMap();
 assert.deepEqual(Array.from(await pending),Array.from({length:24},(_,i)=>i));
});

test('the actual app snapshot caller uses captured dimensions after a resize',async()=>{
 const app=fs.readFileSync(path.join(root,'pyro-gpu/app.js'),'utf8');
 const start=app.indexOf('  async function snapshot(name) {'),end=app.indexOf("  $('#benchmark').onclick",start);
 assert.ok(start>=0&&end>start,'actual snapshot function boundaries');
 const captured=[],canvas={width:3,height:2};let resolvePixels;
 const solver={pixels:()=>new Promise(resolve=>{resolvePixels=resolve;})};
 const document={createElement(name){assert.equal(name,'canvas');return {width:0,height:0,
  getContext(type){assert.equal(type,'2d');return {putImageData(data){captured.push(['image',data.width,data.height]);},drawImage(source){captured.push(['draw',source.width,source.height]);}};},
  toBlob(done){done({png:true});},
 };}};
 const ImageData=class{constructor(data,width,height){assert.equal(data.length,width*height*4);this.width=width;this.height=height;}};
 const save=async(name,blob,type)=>captured.push(['save',name,blob.png,type]);
 const snapshot=new Function('document','canvas','solver','ImageData','save',app.slice(start,end)+'\nreturn snapshot;')(document,canvas,solver,ImageData,save);
 const pending=snapshot('resize');assert.ok(resolvePixels);canvas.width=1;canvas.height=1;
 resolvePixels(new Uint8ClampedArray(24));await pending;
 assert.deepEqual(captured,[['image',3,2],['draw',3,2],['save','resize',true,'png']]);
});

test('dense and adaptive steps bind the current pooled field to surface, velocity and embers',async()=>{
 for(const adaptive of [false,true])for(const ci of [0,1]){
  const f=fixture(),{s,calls,encoder}=f,pool=await f.pool();
  const previousPages=pool.pageTable,previousFields=[...pool.fields];
  s.adaptive=adaptive;s.objectId='car';s.objectModels.car=f.texture('car');s.ci=ci;
  if(adaptive)await s.initAdaptive();calls.length=0;s.step(encoder,1/60,0);
  const beforeCorrection=calls.filter(x=>['surface-fuel','correctVelocity','adaptive-flow-coarseCorrect','adaptive-flow-fineCorrect'].includes(x.pipe));
  assert.equal(beforeCorrection.length,adaptive?4:2);
  for(const call of beforeCorrection)assertCurrentField(call,{...pool,fields:previousFields,pageTable:call.pipe==='surface-fuel'?previousPages:pool.pageTable},ci);
  const ember=calls.find(x=>x.pipe==='embers');assert.ok(ember);assertCurrentField(ember,pool,1-ci);
  const predict=bindings(calls.find(x=>x.pipe==='advectScalar'));
  assert.equal(predict.get(20),pool.fields[ci].view);assert.equal(predict.get(21),pool.fields[2].view);
  const correct=bindings(calls.find(x=>x.pipe==='correctScalar'));
  assert.equal(correct.get(22),pool.fields[1-ci].view);assert.equal(s.ci,1-ci);
 }
});

test('normal and tree renderer families retain pooled consumers and precise receiver bindings',async()=>{
 for(const isTree of [false,true])for(const ci of [0,1]){
  const f=fixture(),{s,calls,modules}=f,pool=await f.pool();
  if(isTree)tree(f);s.ci=ci;await s.prepareRenderer(isTree);calls.length=0;
  await s.frame(0);
  const prefix=isTree?'tree-':'';
  const dilate=bindings(calls.find(x=>x.pipe==='visible-bricks'));
  assert.equal(dilate.get(2).buffer,s.lightingReceivers);
  const names=['gatherPipeline','gatherAdaptivePipeline','roomPipeline','bouncePipeline','lightReceiverPipeline'].map(x=>prefix+x);
  for(const name of names){const call=calls.find(x=>x.pipe===name);assert.ok(call,name);assertCurrentField(call,pool,ci,true);}
  const light=bindings(calls.find(x=>x.pipe===prefix+'lightReceiverPipeline'));
  assert.equal(light.get(30).buffer,s.lightingReceivers);
  assert.equal(light.has(26),false);assert.equal(light.has(27),false);
  const volume=calls.find(x=>x.pipe==='volume-render');assertCurrentField(volume,pool,ci,true);
  const ember=calls.find(x=>x.pipe==='ember-render');assertCurrentField(ember,pool,ci);
  if(isTree){assert.ok(light.has(23));assert.ok(light.has(24));assert.ok(bindings(volume).has(20));}
  assert.ok(modules.some(x=>x.code.includes('@binding(30)')&&x.code.includes('@binding(25)')&&x.code.includes('coupledChemSample')));
 }
});

test('pooled renderer preparation and repeated paused frames retain fixed resource allocation',async()=>{
 const f=fixture(),{s,calls,allocations}=f;await f.pool();await s.prepareRenderer(false);
 const before=allocations();for(let i=0;i<30;i++){s.lightReady=false;await s.frame(0);}
 assert.equal(allocations(),before);
 assert.equal(calls.filter(x=>x.pipe==='lightReceiverPipeline').length,30);
 assert.equal(s.errors.length,0);
});

test('active pooled/adaptive frames retain bounded resources, groups and classifier uploads',async()=>{
 const f=fixture(),{s,writes,allocations,groups}=f;await f.pool();await s.initAdaptive();
 s.adaptive=true;await s.prepareRenderer(false);
 for(let i=0;i<24;i++)await s.frame(1/60);
 const warmAllocations=allocations(),warmGroups=groups();
 for(let i=0;i<100;i++)await s.frame(1/60);
 assert.equal(allocations(),warmAllocations);assert.equal(groups(),warmGroups);
 assert.equal(writes.filter(x=>x.buffer===s.flowCommands).length,1,'only initialization uploads classifier commands');
 assert.equal(s.errors.length,0);assert.ok(s.time>2);
});

test('asynchronous pool status rejection cannot stall or stop frame presentation',async()=>{
 const f=fixture(),{s,calls}=f;await f.pool();await s.prepareRenderer(false);
 const stats=s.device.createBuffer({size:16});new Float32Array(stats.data).set([1,0,0,1]);
 let rejectMap;const poolStatus=s.device.createBuffer({size:64});
 poolStatus.mapAsync=()=>new Promise((_,reject)=>{rejectMap=reject;});
 const slot={stats,poolStatus,pending:false,poolPending:false,queryPending:false};s.telemetrySlots=[slot];
 let statusTask;const actual=s.collectPoolTelemetry.bind(s);
 s.collectPoolTelemetry=(...args)=>(statusTask=actual(...args));
 const result=await s.frame(0);assert.ok(result);assert.ok(rejectMap);assert.equal(slot.poolPending,true);
 assert.ok(calls.some(x=>x.pipe==='present'));
 rejectMap(Error('diagnostic map rejected'));await statusTask;
 assert.equal(slot.poolPending,false);assert.equal(s.poolTelemetryAvailable,false);assert.deepEqual(s.errors,[]);
 const next=await s.frame(0);assert.ok(next);assert.deepEqual(s.errors,[]);
});

test('late pool mappings cannot overwrite telemetry after reset or a newer sample',async()=>{
 const f=fixture(),{s}=f;await f.pool();
 const slot={poolStatus:s.device.createBuffer({size:64}),poolPending:true};
 new Uint32Array(slot.poolStatus.data).set([0,4,4,4,1020,0,5,0]);
 let resolveMap;slot.poolStatus.mapAsync=()=>new Promise(resolve=>{resolveMap=()=>{slot.poolStatus.mapState='mapped';resolve();};});
 const old=s.collectPoolTelemetry(slot,2,s.stateEpoch);s.stateEpoch++;resolveMap();await old;
 assert.equal(s.latestTelemetry.brickPool,undefined);assert.equal(slot.poolPending,false);
 s.latestTelemetry.poolSampleFrame=9;const stale=s.collectPoolTelemetry(slot,8,s.stateEpoch);resolveMap();await stale;
 assert.equal(s.latestTelemetry.brickPool,undefined);
 const current=s.collectPoolTelemetry(slot,10,s.stateEpoch);resolveMap();await current;
 assert.equal(s.latestTelemetry.brickPool.mode,'sparse');assert.equal(s.latestTelemetry.poolSampleFrame,10);
 assert.equal(slot.poolStatus.mapState,'unmapped');
});
