// Execute actual Volume methods against a recording GPU contract. Native
// pipeline compilation and pixels remain separate release evidence.
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {PyroSolver}=await import(pathToFileURL(path.join(root,'pyro-gpu/solver.js')).href);
const {ForestMesh}=await import(pathToFileURL(path.join(root,'pyro-gpu/forest-mesh.js')).href);
const calls=[],resource=name=>({name}),tex=name=>({view:resource(name)});
const pipeline=label=>({label,getBindGroupLayout:()=>({label})});
const pass=kind=>{let p,b;return {setPipeline(v){p=v;},setBindGroup(_,v){b=v;},dispatchWorkgroups(...groups){calls.push({kind,label:p.label,bindings:b.entries,groups});},draw(...groups){calls.push({kind,label:p.label,bindings:b.entries,groups});},end(){}};};
const encoder=()=>({clearBuffer(){},beginComputePass(){return pass('compute');},beginRenderPass(){return pass('render');},finish(){return {};}});
const device={queue:{writeBuffer(){},submit(){},onSubmittedWorkDone:()=>Promise.resolve()},createCommandEncoder:encoder,createBindGroup({entries}){assert.equal(new Set(entries.map(x=>x.binding)).size,entries.length,'no binding collision');return {entries};}};
const s=Object.assign(Object.create(PyroSolver.prototype),{
  device,errors:[],inFlight:[],frameNumber:0,completedFrames:0,time:0,burstAge:1,maxSpeed:1,N:128,
  latestTelemetry:{sampleFrame:0},telemetrySlots:[],query:null,lightReady:false,ci:0,si:0,
  source:[0,.58,0],effect:[1,1,0,1],objectId:null,objectModels:{},objectSettings:resource('object-settings'),
  color:'natural',embers:false,smoke:false,stats:resource('stats'),c:[tex('chem-a'),tex('chem-b')],sampler:resource('sampler'),
  visibleBricks:resource('visible-mask'),masks:[resource('mask-a'),resource('mask-b')],opticalMasks:[resource('optical-a'),resource('optical-b')],view:resource('view'),
  lightSeeds:resource('seeds'),fireLights:resource('lights'),light:tex('incident'),roomTargets:[tex('direct-room'),tex('final-room')],
  emptyObject:tex('empty-solid'),surface:[tex('surface-a'),tex('surface-b')],outputView:resource('output'),
  context:{getCurrentTexture:()=>({createView:()=>resource('canvas')})},cache:new Map(),ids:new WeakMap(),nextId:0,
  prepareSource:async()=>{},
  floorFuel:[tex('floor-a'),tex('floor-b')],floorIndex:0,hasFloorFuel:false,sigilSource:tex('sigil-source'),
});
for(const [key,label] of Object.entries({dilatePipeline:'dilate',gatherPipeline:'gather',gatherAdaptivePipeline:'adaptive',roomPipeline:'room',bouncePipeline:'bounce',lightPipeline:'light',renderPipeline:'render',present:'present'}))s[key]=pipeline(label);
const forest=Object.assign(Object.create(ForestMesh.prototype),{targets:[tex('mesh-position'),tex('mesh-normal'),tex('mesh-color')],shadow:resource('tree-shadow'),compare:resource('tree-compare'),shadows(){calls.push({label:'tree-shadows'});},render(){calls.push({label:'tree-mesh'});}});
const bindings=(label)=>calls.findLast(x=>x.label===label)?.bindings;
const value=(items,slot)=>items?.find(x=>x.binding===slot)?.resource;
function camera(room=true){const data=Array(48).fill(0);data[16]=Number(room);data[19]=24;s.camera(data);}
const outcomes=[];
for(const tree of [false,true,false]){
  calls.length=0;s.usingTree=tree;s.objectId=tree?'cybr-tree':null;s.forestMesh=tree?forest:null;s.lightReady=false;camera();
  const result=await s.frame(0);
  assert.equal(result.relit,true);
  assert.ok(calls.findIndex(x=>x.label==='dilate')<calls.findIndex(x=>x.label==='room'),'fresh mask precedes room sampling');
  assert.equal(value(bindings('dilate'),0)?.buffer,s.opticalMasks[s.ci],'render halo follows optical support, not invisible chemistry');
  for(const label of ['room','bounce','light','render'])assert.equal(value(bindings(label),9)?.buffer,s.visibleBricks,label+' shares the actual conservative mask');
  for(const label of ['room','bounce','light','render'])assert.equal(value(bindings(label),13)?.buffer,s.objectSettings,label+' preserves object settings');
  if(tree){
    for(const label of ['room','light','render']){
      assert.equal(value(bindings(label),23),forest.shadow);
      assert.equal(value(bindings(label),24),forest.compare);
    }
    for(let i=0;i<3;i++)assert.equal(value(bindings('render'),18+i),forest.targets[i].view);
    assert.ok(calls.findIndex(x=>x.label==='tree-shadows')<calls.findIndex(x=>x.label==='room'));
  }else assert.equal(value(bindings('room'),23),undefined);
  calls.length=0;assert.equal((await s.frame(0)).relit,false);
  assert.ok(!calls.some(x=>['dilate','room','bounce','light'].includes(x.label)),'unchanged paused lighting remains cached');
  assert.ok(calls.some(x=>x.label==='render'),'cached lighting still presents');
  outcomes.push({tree,sharedMask:true,bindingsPreserved:true,pausedCachePreserved:true});
}
calls.length=0;camera(false);assert.equal((await s.frame(0)).relit,true);
assert.ok(!calls.some(x=>['room','bounce'].includes(x.label)),'room-off still omits room passes');
assert.equal(value(bindings('light'),9)?.buffer,s.visibleBricks);
console.log('PASS: actual Volume lighting bindings, normal/tree transitions, mask ordering, paused cache and room-off rendering.');
