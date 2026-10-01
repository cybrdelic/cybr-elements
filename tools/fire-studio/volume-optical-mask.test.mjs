import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {PyroSolver}=await import(pathToFileURL(path.join(root,'pyro-gpu/solver.js')).href);
const {simulationShaders}=await import(pathToFileURL(path.join(root,'pyro-gpu/shaders.js')).href);
const {rendererShaders,dilateWGSL}=await import(pathToFileURL(path.join(root,'pyro-gpu/renderer.js')).href);
const resource=name=>({name});
const texture=name=>({name,view:resource(name),n:256});

function fixture(){
 const calls=[];
 const encoder={clearBuffer(buffer){calls.push({label:'clear',buffer});},beginComputePass(){return {setPipeline(){},setBindGroup(){},dispatchWorkgroups(){},end(){}};},finish(){return {};}};
 const s=Object.assign(Object.create(PyroSolver.prototype),{
  device:{queue:{writeBuffer(){},submit(){},onSubmittedWorkDone:()=>Promise.resolve()},createCommandEncoder:()=>encoder},
  query:null,N:128,D:256,source:[0,.58,0],effect:[1,1,.1,1],dynamics:[1,1,1,1],chemistry:[1,1,1,1],
  time:0,burstAge:1,previousDt:0,active:true,smoke:false,seed:2,fuel:0,embers:false,
  params:Array.from({length:12},(_,i)=>resource('params-'+i)),objectId:null,objectModels:{},emptyObject:texture('solid'),
  surface:[texture('surface-a'),texture('surface-b')],si:0,vi:0,ci:0,v:[texture('v-a'),texture('v-b'),texture('v-pred')],
  c:[texture('chem-a'),texture('chem-b'),texture('chem-pred')],vort:texture('vorticity'),
  masks:[resource('transport-a'),resource('transport-b')],opticalMasks:[resource('optical-a'),resource('optical-b')],
  objectSettings:resource('object-settings'),stats:resource('stats'),groupStats:resource('group-stats'),bricks:resource('bricks'),
  indirect:resource('indirect'),sampler:resource('sampler'),sigilSource:texture('sigil'),emberBuffer:resource('embers'),
  stateEpoch:0,frameNumber:7,
  levels:[{n:128,current:0,p:[texture('pressure-a'),texture('pressure-b')],b:texture('rhs')}],
  clearPipeline:resource('clear-state'),
  floorFuel:[texture('floor-a'),texture('floor-b')],floorWear:[texture('floor-wear-a'),texture('floor-wear-b')],floorDeposits:texture('floor-deposits'),floorIndex:0,hasFloorFuel:false,
  floorClear:resource('floor-fuel-clear'),floorWearClear:resource('floor-wood-wear-clear'),fuelBrush:{clear(){}},
  group:(pipeline,items)=>({pipeline,items}),
  dispatch(encoder,pipeline,items,n){calls.push({label:pipeline.name,items,n});},
  sparse(encoder,pipeline,items){calls.push({label:pipeline.name,items});},
  vcycle(){calls.push({label:'pressure-cycle'});},
  resetSurface(){calls.push({label:'surface-reset'});},
 });
 s.pipelines=Object.fromEntries(['advectVelocity','curl','correctVelocity','rhs','project','reduceStats','buildBricks','advectScalar','correctScalar'].map(name=>[name,resource(name)]));
 return {s,calls,encoder};
}

test('actual scalar steps retain transport masks and clear/write optical destination in both ping-pong phases',()=>{
 const {s,calls,encoder}=fixture();
 for(const old of [0,1]){
  calls.length=0;assert.equal(s.ci,old);
  s.step(encoder,1/60,0);
  const destination=1-old;
  const build=calls.find(call=>call.label==='buildBricks');
  const correct=calls.find(call=>call.label==='correctScalar');
  const binding=(call,index)=>call.items.find(([slot])=>slot===index)?.[1];
  assert.equal(binding(build,2).buffer,s.masks[old]);
  assert.equal(binding(build,3).buffer,s.masks[destination]);
  assert.equal(binding(correct,7).buffer,s.masks[destination]);
  assert.equal(binding(correct,10).buffer,s.opticalMasks[destination]);
  assert.ok(calls.findIndex(call=>call.label==='clear'&&call.buffer===s.opticalMasks[destination])<calls.indexOf(correct));
  assert.ok(!calls.some(call=>call.label==='clear'&&call.buffer===s.opticalMasks[old]));
  assert.equal(s.ci,destination);
 }
});

test('actual reset clears both optical buffers with transport and chemical state',async()=>{
 const {s,calls}=fixture();
 await s.reset();
 for(const mask of [...s.masks,...s.opticalMasks])assert.equal(calls.filter(call=>call.label==='clear'&&call.buffer===mask).length,1);
 assert.equal(s.time,0);
 assert.equal(s.previousDt,0);
});

test('actual WGSL camera and shadow predicates preserve separate visible and faint-soot support',()=>{
 const shader=simulationShaders(128,256).correctScalar;
 const predicate=bit=>{
  const condition=shader.match(new RegExp(`if\\(([^\\n;]+)\\)\\{atomicOr\\(&opticalAlive,${bit}u\\);\\}`))?.[1];
  assert.ok(condition,'extract the production predicate for bit '+bit);
  return new Function('c',`return ${condition.replace(/c\.([xyzw])/g,(_,component)=>`c[${'xyzw'.indexOf(component)}]`)};`);
 };
 const visible=predicate(1),shadow=predicate(2);
 assert.equal(visible([0,0,0,1]),false,'oxygen deficit alone produces no optical support');
 assert.equal(visible([0,.15,1,1]),false,'cold unburned fuel remains transport-only');
 assert.equal(visible([.000001,0,0,1]),false,'faint cold soot already takes the camera early continue');
 assert.equal(shadow([.000001,0,0,1]),true,'retain even faint cold soot in every shadow');
 assert.equal(visible([.000033,0,0,1]),true,'camera margin includes its extinction threshold');
 const hot=[0,1,0,0],fuel=[0,0,1,0];
 assert.equal(visible(hot),true,'hot support must survive even without local fuel');
 const mixed=hot.map((value,index)=>value*.6+fuel[index]*.4);
 assert.ok(mixed[1]>.35&&mixed[2]>0&&mixed[3]<1,'interpolating separate hot and fuel cells can create combustion');
 assert.equal(visible(mixed),true,'the full-brick halo keeps the mixed combustion sample');
 // Check the largest stored values that can have a false pre-write camera
 // predicate. Margins must cover binary16 rounding before interpolation.
 const positiveHalf=[];
 for(let bits=0;bits<0x7c00;bits++){
  const exponent=bits>>10,mantissa=bits&1023;
  positiveHalf.push(exponent?Math.pow(2,exponent-15)*(1+mantissa/1024):Math.pow(2,-14)*mantissa/1024);
 }
 const rounded=value=>positiveHalf.reduce((best,item)=>Math.abs(item-value)<Math.abs(best-value)?item:best,0);
 assert.ok(Math.fround(rounded(.000033)*3)<Math.fround(.0001),'false soot predicate cannot round into visible extinction');
 assert.ok(rounded(.3499)<Math.fround(.35),'false heat predicate cannot round into reaction onset');
});

test('shared mask unions independent workgroup bits and all renderer stages select their intended support',()=>{
 const scalar=simulationShaders(128,256).correctScalar;
 assert.match(scalar,/atomicOr\(&opticalOccupied\[index\],atomicLoad\(&opticalAlive\)\)/,'eight scalar chunks union their independent bits');
 assert.match(dilateWGSL,/alive\|=source\[/,'dilation preserves camera and shadow bits across neighbors');
 for(const tree of [false,true]){
  const shaders=rendererShaders(tree);
  assert.match(shaders.render,/occupied\[u32\(brick\.x\+32\*\(brick\.y\+32\*brick\.z\)\)\]&1u/,'camera uses bit 1');
  assert.match(shaders.light,/occupied\[b\.x\+32u\*\(b\.y\+32u\*b\.z\)\]&1u/,'illumination uses bit 1');
  for(const key of ['render','light','room'])assert.match(shaders[key],/occupied\[brick\.x\+32u\*\(brick\.y\+32u\*brick\.z\)\]&2u/,key+' shadows preserve all soot');
 }
});
