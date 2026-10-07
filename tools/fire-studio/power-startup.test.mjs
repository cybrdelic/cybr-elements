import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {pruneShaderFunctions,specializePowerSource} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/shader-specialization.js';
import {powerSourceFor,POWER_DEFINITIONS} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-powers.js';
import {simulationShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/shaders.js';
import {PyroSolver} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/solver.js';

test('source reachability excludes unreachable functions and ignores commented calls',()=>{
 const source='// fn fake(){ bad(); }\nfn kept()->f32{return 1.;}\nfn dead()->f32{return 2.;}\n@compute @workgroup_size(1) fn main(){kept();/* dead(); } */}';
 const result=pruneShaderFunctions(source);
 assert.match(result,/fn kept/);assert.doesNotMatch(result,/fn dead/);assert.match(result,/\/\* dead\(\); } \*\//);
 assert.throws(()=>pruneShaderFunctions('fn other(){}'),/entry missing/);
});
test('static power specialization preserves dynamic conditions and helper calls',()=>{
 const source=`fn helper()->f32{return 2.;}
 fn powerCastSource(kind:f32,age:f32)->f32{if(kind<1.5){return 1.;}if(kind<2.5){if(age<.2){return helper();}return 3.;}return 4.;}
 fn powerCastSupport(kind:f32)->bool{return kind>0.;}
 fn powerCastAcceleration(kind:f32)->f32{return 0.;}
 fn powerCastExpansion(kind:f32)->f32{return 4.;}`;
 const result=specializePowerSource(source,2);
 assert.match(result,/if\(age<\.2\)/);assert.match(result,/return helper\(\)/);
 assert.doesNotMatch(result,/return 1\.;|return 4\.;}\n fn powerCastSupport/);
 assert.throws(()=>specializePowerSource(source,25),/Unknown power/);
});
test('all 24 selected powers are bounded and retain the exported source interface',()=>{
 for(const power of POWER_DEFINITIONS){
  const source=powerSourceFor(power.kind);
  assert.ok(source.length<24000,power.id);
  for(const name of ['powerCastSource','powerCastSupport','powerCastAcceleration','powerCastExpansion'])assert.match(source,new RegExp('fn '+name+'\\('));
  const glsl=powerSourceFor(power.kind,'glsl');assert.doesNotMatch(glsl,/\bfn\s|\bvec[234]f\b|\b(?:let|var)\s/);
 }
});
test('transport and global pressure shader text is independent of the selected power',()=>{
 const hash=source=>createHash('sha256').update(source.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'').replace(/\s+/g,'')).digest('hex');
 const normal=simulationShaders(128,256,{hasPowers:false});
 for(const power of POWER_DEFINITIONS){
  const selected=simulationShaders(128,256,{hasPowers:true,powerKind:power.kind});
  for(const name of ['advectVelocity','curl','advectScalar','rhs','project','reduceStats']){
   assert.equal(hash(selected[name]),hash(normal[name]),power.id+' '+name);
   assert.doesNotMatch(selected[name],/fn powerCastSource/);
  }
 }
});
test('switching source kernels keeps the device and reuses cached families',async()=>{
 const solver=Object.create(PyroSolver.prototype),device={};
 Object.assign(solver,{powerKind:null,hasPowers:false,device,pipelines:{},sourcePipelineCache:new Map(),adaptive:false,powerContacts:{select:async()=>{}}});
 const names=['correctVelocity','correctScalar','buildBricks'];let compilations=0;
 solver.simulationShaderSet=kind=>Object.fromEntries(names.map(name=>[name,kind+':'+name]));
 solver.pipeline=async(code,label)=>{compilations++;return {code,label};};
 solver.sourcePipelineCache.set(null,Object.fromEntries(names.map(name=>[name,{code:'normal:'+name}])));
 await solver.selectPowerKind(2);const fireball=solver.pipelines.correctVelocity;
 await solver.selectPowerKind(null);await solver.selectPowerKind(2);
 assert.equal(compilations,3);assert.equal(solver.device,device);assert.equal(solver.pipelines.correctVelocity,fireball);
});
test('failed compilation leaves the running source family intact and can retry',async()=>{
 const solver=Object.create(PyroSolver.prototype),previous={};
 Object.assign(solver,{powerKind:null,hasPowers:false,pipelines:{correctVelocity:previous},sourcePipelineCache:new Map(),adaptive:false});
 solver.simulationShaderSet=()=>({correctVelocity:'v',correctScalar:'c',buildBricks:'b'});
 solver.pipeline=async()=>{throw Error('compile rejected');};
 await assert.rejects(solver.selectPowerKind(2),/compile rejected/);
 assert.equal(solver.powerKind,null);assert.equal(solver.pipelines.correctVelocity,previous);assert.equal(solver.sourcePipelineCache.has(2),false);
});
