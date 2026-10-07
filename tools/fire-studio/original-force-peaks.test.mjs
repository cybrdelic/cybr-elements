import test from 'node:test';
import assert from 'node:assert/strict';
import {originalPeakForceGLSL,ORIGINAL_MOTION_PEAK_ACCELERATION} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-shaders.js';

// Execute the production scalar helpers; test force units and scope independently.
function body(name){
 const start=originalPeakForceGLSL.indexOf(name+'('),open=originalPeakForceGLSL.indexOf('{',start),end=originalPeakForceGLSL.indexOf('}',open);
 assert.ok(start>=0&&end>open);return originalPeakForceGLSL.slice(open+1,end).replace(/\b(min|max)\(/g,'Math.$1(');
}
const target=new Function('emitter','effect','sourceMode',body('originalPeakForceTarget'));
const scale=new Function('worldMagnitude','maximum',body('originalPeakForceScale'));
test('peak limits retain every weak acceleration exactly and never reverse a force',()=>{
 for(const cap of [4,6])for(const magnitude of [0,.00001,.01,.1,1,3.9,4,6,12,42,1e6]){
  const factor=scale(magnitude,cap);
  assert.ok(factor>=0&&factor<=1);
  if(magnitude<=cap)assert.equal(factor,1);
  assert.ok(magnitude*factor<=cap+1e-12);
 }
 assert.equal(scale(42,0),0);assert.equal(scale(42,-1),0);
});
test('confinement peak limits are invariant to unequal world-to-domain extents',()=>{
 for(const extent of [[14,7.875,1.8],[8,8,4],[2,30,.5]])for(const world of [[.1,.2,.3],[2,-1,3],[12,0,0],[-9,17,-22]])for(const gain of [.8,3.5])for(const cap of [4,6]){
  const normalized=world.map((v,i)=>v/extent[i]);
  const magnitude=Math.hypot(...normalized.map((v,i)=>v*extent[i]))*gain;
  const factor=scale(magnitude,cap);
  const actual=normalized.map((v,i)=>v*gain*factor*extent[i]);
  const length=Math.hypot(...world)*gain;
  const expected=world.map(v=>v*gain*(length>cap?cap/length:1));
  actual.forEach((v,i)=>assert.ok(Math.abs(v-expected[i])<1e-12));
 }
});
test('constant bounded force impulse integrates over physical time rather than frame count',()=>{
 const world=[12,-7,4],cap=6,magnitude=Math.hypot(...world),factor=scale(magnitude,cap);
 const total=.4,expected=world.map(v=>v*factor*total);
 for(const steps of [1,12,24,120]){
  const dt=total/steps,velocity=[0,0,0];
  for(let step=0;step<steps;step++)world.forEach((v,i)=>velocity[i]+=v*factor*dt);
  velocity.forEach((v,i)=>assert.ok(Math.abs(v-expected[i])<1e-12));
 }
});
test('only Original cursor fire and fireball enter peak correction',()=>{
 for(let emitter=0;emitter<=45;emitter++)for(const effect of [-1,0,1,23]){
  assert.equal(target(emitter,effect,0),(emitter===0&&effect<0)||emitter===23);
  assert.equal(target(emitter,effect,1),false);
 }
 assert.equal(target(0,0,0),false,'Sooty plume retains its authored confinement');
});

const maximum=new Function('emitter',body('originalPeakForceMaximum'));
test('the selected Original source families use their reviewed force peaks',()=>{
 assert.deepEqual(ORIGINAL_MOTION_PEAK_ACCELERATION,{free:6,fireball:4});
 assert.equal(maximum(0),6);assert.equal(maximum(23),4);
 assert.equal(scale(42,maximum(0)),6/42);
 assert.equal(scale(42,maximum(23)),4/42);
});
