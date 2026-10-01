import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,'../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {PowerCastPool}=await import(pathToFileURL(resolve(root,'fire-abilities.js')).href);
const {POWER_DEFINITIONS,powerPhase}=await import(pathToFileURL(resolve(root,'fire-power-definitions.js')).href);
const setting={origin:[0,1,0],direction:[1,.1,0],target:[2,1,0],strength:1,scale:1};

test('held casts accumulate charge without releasing or reaching their source launch phase',()=>{
 for(const d of POWER_DEFINITIONS.filter(d=>d.hold)){
  const pool=new PowerCastPool(),s=pool.cast(d.id,{...setting,held:true}),out=new Float32Array(64);
  for(let i=0;i<180;i++)pool.step(1/60);
  assert.equal(s.charge,1);assert.equal(s.held,true);assert.equal(s.active,true);
  pool.write(out);assert.equal(out[10],2);assert.ok(out[3]<d.windup);
  assert.equal(powerPhase(d,s.age,true).name,'Charging');
  assert.equal(pool.release([1,1,-.5],[1,0,-.5]),true);
  assert.equal(s.age,d.windup);assert.equal(s.charge,1);assert.equal(s.held,false);
  pool.step(1/60);assert.ok(s.age>d.windup);
 }
});
test('overlapping casts keep immutable targets and independent ages in four reusable slots',()=>{
 const pool=new PowerCastPool(),refs=pool.slots.map(s=>[s,s.origin,s.direction,s.target]);
 const first=pool.cast('fireball',setting);pool.step(.2);
 for(let i=1;i<4;i++){pool.cast('fireball',{...setting,origin:[i*.1,1,0],target:[1,1,i*.1]});pool.step(.1);}
 assert.equal(pool.snapshot().active,4);assert.ok(Math.abs(first.age-.5)<1e-12);
 const olderTarget=Array.from(pool.slots[1].target),olderAge=pool.slots[1].age;
 const retired=pool.cast('fireball',{...setting,held:true});assert.equal(retired,first);
 pool.aim([-.5,1,1],[-1,0,1]);assert.deepEqual(Array.from(pool.slots[1].target),olderTarget);assert.equal(pool.slots[1].age,olderAge);
 for(let i=0;i<4;i++)for(let j=0;j<4;j++)assert.equal([pool.slots[i],pool.slots[i].origin,pool.slots[i].direction,pool.slots[i].target][j],refs[i][j]);
 assert.equal(pool.cancelHeld(),true);assert.equal(pool.snapshot().active,3);assert.notEqual(pool.snapshot().phase.name,'Ready');
});
test('continuous powers own one actor and update direction and strength live',()=>{
 const pool=new PowerCastPool();for(let i=0;i<4;i++)pool.cast('fireball',setting);
 const s=pool.cast('dragon-breath',setting);assert.equal(pool.snapshot().active,1);
 pool.move([.3,1,.5],[2,1,1],{direction:[0,1,1],strength:1.7});
 assert.deepEqual(Array.from(s.origin),[.3,1,.5]);assert.equal(s.strength,1.7);assert.ok(Math.abs(Math.hypot(...s.direction)-1)<1e-12);
 pool.step(20);assert.equal(s.active,true);pool.stop();assert.equal(pool.snapshot().active,0);
});
test('invalid cast input is atomic and target clamping uses each engine domain',()=>{
 const pool=new PowerCastPool({bounds:{min:[-3.84,.14,-1.92],max:[3.84,6.63,1.92]}}),s=pool.cast('fireball',setting);
 const before=pool.snapshot();for(const bad of [{direction:7},{target:[NaN,1,0]},{origin:[0,1]},{strength:Infinity}]){
  assert.equal(pool.cast('fireball',{...setting,...bad}),null);assert.deepEqual(pool.snapshot(),before);
 }
 const big=pool.cast('cinder-scatter',{...setting,target:[999,999,-999]});
 assert.ok(big.target[0]<=3.04&&big.target[2]>=-1.12);assert.ok(big.target[1]<=6.63);assert.ok(Math.hypot(...Array.from(big.target).map((v,i)=>v-big.origin[i]))<=3+1e-12);
 const up=pool.cast('fireball',{...setting,direction:[0,1,0],target:undefined});assert.ok(up.target[1]>1,'projectiles retain vertical aim');
 assert.equal(s.active,true);
});
test('late impacts invalidate warm pressure and have a conservative velocity bound before telemetry',()=>{
 const pool=new PowerCastPool();
 for(const d of POWER_DEFINITIONS.filter(d=>!d.continuous)){
  const s=pool.cast(d.id,{...setting,scale:1.5,strength:2});
  for(const impulse of d.impulses){s.age=impulse.at-.005;assert.equal(pool.crossesImpulse(.01),true,d.id+' '+impulse.at);assert.ok(pool.speedFloor(.01)>=impulse.speed*1.5*Math.sqrt(2)-1e-12);}
  s.age=d.duration+.01;s.active=false;
 }
});
test('uniform uploads are bounded, leave the older128-byte prefix untouched and separate targets',()=>{
 const pool=new PowerCastPool();for(let i=0;i<4;i++){pool.cast('fireball',{...setting,origin:[i*.25,1,0],target:[1,1,i*.1]});pool.step(.05);}
 const uniform=new Float32Array(96).fill(77);pool.write(uniform,32);
 assert.ok(uniform.slice(0,32).every(v=>v===77));
 assert.equal(new Set(pool.slots.map(s=>s.target[2])).size,4);
 assert.equal(new Set(pool.slots.map(s=>s.age)).size,4);
 for(let i=0;i<4;i++){const o=32+i*16,s=pool.slots[i];assert.equal(uniform[o],i*.25);assert.equal(uniform[o+3],Math.fround(s.age));assert.equal(uniform[o+8],2);assert.equal(uniform[o+10],1);
  for(let axis=0;axis<3;axis++)assert.equal(uniform[o+12+axis],Math.fround(s.target[axis]));
  assert.ok(Math.abs(s.target[0]-.64)<1e-12);assert.equal(uniform[o+14],Math.fround(i*.1));}
 pool.stop();pool.write(uniform,32);for(let i=0;i<4;i++)assert.equal(uniform[32+i*16+10],0);
 assert.throws(()=>pool.write(new Float32Array(63)),/too small/);
});
test('Original blast pressure ends with the finite release window and cannot persist or start during a held charge',()=>{
 const pool=new PowerCastPool(),s=pool.cast('combustion-bomb',setting);pool.step(1.25);assert.equal(pool.expansion(),12);
 pool.step(.3);assert.equal(pool.expansion(),0);pool.step(10);assert.equal(pool.expansion(),0);
 const held=pool.cast('fireball',{...setting,held:true});pool.step(3);assert.equal(pool.expansion(),0);
 pool.release();held.age=.9;assert.equal(pool.expansion(),12);pool.stop();assert.equal(pool.expansion(),0);
 assert.equal(s.active,false);
});
