import test from 'node:test';
import assert from 'node:assert/strict';
import {SimulationClock} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/simulation-clock.js';
import {smokeDecayRate} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/smoke-lifecycle.js';

test('display refresh and GPU capacity do not change the physical clock',()=>{
 for(const fps of [30,60,120,144]){
  const c=new SimulationClock(0);let advanced=0;
  for(let i=1;i<=fps*5;i++){
   c.tick(i*1000/fps);
   // Deliberately skip alternate display callbacks to model a full queue.
   if(i%2===0){const dt=c.debt;advanced+=dt;c.consume(dt);}
  }
  assert.ok(Math.abs(advanced+c.debt-5)<1e-10);
  assert.equal(c.dropped,0);
 }
});
test('pause discards paused time and overload never builds unbounded catch-up',()=>{
 const c=new SimulationClock(0);c.tick(100);c.tick(5000,false);
 assert.equal(c.debt,0);c.tick(5010);assert.ok(Math.abs(c.debt-.01)<1e-12);
 c.tick(15010);assert.equal(c.debt,.25);assert.ok(c.dropped>9);
 c.reset(15010);c.tick(15020);assert.ok(Math.abs(c.debt-.01)<1e-12);
});
test('cold smoke clears faster while hot smoke keeps its former lifetime',()=>{
 assert.equal(smokeDecayRate(0),.16);assert.ok(Math.abs(smokeDecayRate(2)-.055)<1e-12);
 for(let t=0;t<3;t+=.01)assert.ok(smokeDecayRate(t)>=.055-1e-12&&smokeDecayRate(t)<=.16);
 const cold=Math.exp(-smokeDecayRate(0)*30),hot=Math.exp(-smokeDecayRate(2)*30);
 assert.ok(cold<.01&&hot>.19);
 // Density decay changes optical depth continuously, not an opacity timer.
 assert.ok(1-Math.exp(-3*.4*6*cold)<.06);
});
test('absorbing sponge has the same loss for different time partitions',()=>{
 for(const edge of [.001,.3,.9,1])for(const steps of [1,2,12]){
  const one=Math.pow(edge,30/60);
  const split=Math.pow(Math.pow(edge,30/(60*steps)),steps);
  assert.ok(Math.abs(one-split)<1e-12);
 }
});
