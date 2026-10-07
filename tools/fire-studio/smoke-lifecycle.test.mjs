// Numerical lifetime gates. GPU execution of the assembled shader is separate.
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {advanceSmokeDecay,SMOKE_CLEAR_DENSITY,SMOKE_DECAY_TICK,smokeDecayRate}=await import(pathToFileURL(path.join(root,'smoke-lifecycle.js')).href);
const {fuelHalf}=await import(pathToFileURL(path.join(root,'fuel-ground.js')).href);
const {expandFuelDeposits}=await import(pathToFileURL(path.join(root,'pyro-gpu/floor-fuel.js')).href);
const half=value=>expandFuelDeposits(new Uint16Array([fuelHalf(value)]),new Float32Array(1))[0];
function cold(start,seconds,substeps,batch){
  const dt=1/(60*substeps);let soot=half(start),remainder=0;
  for(let i=0;i<seconds*60*substeps;i++){
    const clock=advanceSmokeDecay(remainder,dt);remainder=clock.remainder;
    soot*=Math.exp(-(batch?smokeDecayRate(0):.045)*(batch?clock.decayDt:dt));
    if(batch&&soot<SMOKE_CLEAR_DENSITY)soot=0;
    soot=half(soot);
  }return soot;
}
test('accumulated simulation time survives CFL partitions and paused ticks',()=>{
  for(const count of [1,2,3,12]){
    let remainder=0,decayed=0;
    for(let i=0;i<600*count;i++){
      const result=advanceSmokeDecay(remainder,1/(60*count));remainder=result.remainder;decayed+=result.decayDt;
    }
    assert.ok(Math.abs(decayed+remainder-10)<1e-10);
    assert.deepEqual(advanceSmokeDecay(remainder,0),{decayDt:0,remainder});
    assert.ok(remainder>=0&&remainder<SMOKE_DECAY_TICK);
  }
});
test('actual half-float plateau is reproduced and the fixed cadence dissipates visible soot',()=>{
  const initial=half(.04);
  assert.equal(cold(.04,1,3,false),initial,'Prior per-substep decay rounds completely away');
  const outcomes=[1,2,3,12].map(n=>cold(.04,1,n,true));
  for(const soot of outcomes){assert.ok(soot<initial*.86&&soot>initial*.84);assert.equal(soot,outcomes[0],'CFL subdivision must not change cold smoke lifetime');}
});
test('half-float tail clears while fresh dense smoke retains its gradual lifetime',()=>{
  assert.equal(cold(.000035,60,12,true),0);
  assert.ok(cold(.4,1,12,true)>.4*.84,'No abrupt source-off opacity wipe');
  assert.ok(SMOKE_CLEAR_DENSITY<.000033,'Cleanup remains below visible cold-soot support');
});
test('irregular timestep remainder is conserved and invalid input is refused',()=>{
  let total=0,decayed=0,remainder=0;
  for(let i=0;i<10000;i++){
    const dt=[.003,.017,.007,.026,0][i%5],clock=advanceSmokeDecay(remainder,dt);
    total+=dt;decayed+=clock.decayDt;remainder=clock.remainder;
  }
  assert.ok(Math.abs(total-decayed-remainder)<1e-9);
  for(const pair of [[0,-1],[0,NaN],[-1,.01],[Infinity,.01],[1,.01]])assert.throws(()=>advanceSmokeDecay(...pair));
});
