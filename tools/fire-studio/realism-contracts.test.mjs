import test from 'node:test';
import assert from 'node:assert/strict';
import {diffusionWeights} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/gas-transport.js';
import {gasThermoWGSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/gas-thermodynamics.js';
import {triangleOpenFraction} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/pressure-geometry.js';
import {abilityMotionWGSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-ability-motions.js';
import {shockDepositWGSL,shockAdvanceWGSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/shock-euler.js';
import {POWER_DEFINITIONS} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-powers.js';

// Evaluate production scalar shader functions; no separately tuned CPU model.
function scalar(code,name,args,extras={}){
 const start=code.indexOf('fn '+name+'(');assert.ok(start>=0,name);
 const begin=code.indexOf('{',start);let end=begin+1,depth=1;
 for(;depth;end++){if(code[end]==='{')depth++;if(code[end]==='}')depth--;}
 const body=code.slice(begin+1,end-1).replace(/\b(let|var)\s+(\w+)\s*:\s*f32/g,'let $2');
 return new Function(...args,'max','min','pow','exp',...Object.keys(extras),body);
}
test('closed diffusion conserves dose, remains positive and diffuses equally in world axes',()=>{
 for(const h of [[.022,.022,.058],[.024,.024,.024]]){
  const dt=1/120,w=diffusionWeights(h,dt),n=9,at=(x,y,z)=>x+n*(y+n*z);
  let a=new Float64Array(n**3);a[at(4,4,4)]=1;
  for(let step=0;step<20;step++){
   const b=a.slice();
   for(let z=0;z<n;z++)for(let y=0;y<n;y++)for(let x=0;x<n;x++){
    const p=[x,y,z],i=at(...p);
    for(let axis=0;axis<3;axis++)if(p[axis]+1<n){const q=p.slice();q[axis]++;const j=at(...q),flux=w[axis]*(a[j]-a[i]);b[i]+=flux;b[j]-=flux;}
   }a=b;
  }
  assert.ok(Math.abs(a.reduce((s,v)=>s+v,0)-1)<1e-12);assert.ok(a.every(v=>v>=0));
  const moments=[0,0,0];for(let z=0;z<n;z++)for(let y=0;y<n;y++)for(let x=0;x<n;x++)[x,y,z].forEach((v,k)=>moments[k]+=a[at(x,y,z)]*((v-4)*h[k])**2);
  assert.ok(Math.max(...moments)/Math.min(...moments)<1.001,JSON.stringify(moments));
 }
 assert.throws(()=>diffusionWeights([.001,.001,.001],1/30),/positivity/);
});
test('clipped face apertures complement and preserve weighted pressure symmetry',()=>{
 for(const distances of [[1,-1,-1],[2,3,-1],[.2,-.7,2],[1,2,3]]){
  const a=triangleOpenFraction(...distances),b=triangleOpenFraction(...distances.map(v=>-v));
  assert.ok(a>=0&&a<=1);assert.ok(Math.abs(a+b-1)<1e-12);
 }
 // A shared face gives a symmetric positive semidefinite pressure operator.
 const p=[1,-2,.4,3],q=[-.5,2,1,-1],faces=[.13,.7,0];
 const apply=v=>v.map((_,i)=>(i?faces[i-1]*(v[i]-v[i-1]):0)+(i<3?faces[i]*(v[i]-v[i+1]):0));
 const dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0);
 assert.ok(Math.abs(dot(p,apply(q))-dot(q,apply(p)))<1e-12);assert.ok(dot(p,apply(p))>=0);
});
test('thermal loss stays positive, finite and stronger for soot and hot gas',()=>{
 const fn=scalar(gasThermoWGSL,'coolGasTemperature',['temperature','fuel','soot','dt']);
 const cool=(T,f,s,dt)=>fn(T,f,s,dt,Math.max,Math.min,Math.pow,Math.exp);
 for(const T of [0,.01,.5,2,10])for(const dt of [1/240,1/30,1]){
  const out=cool(T,0,.5,dt);assert.ok(Number.isFinite(out)&&out>=0&&out<=T);
  assert.ok(out<=cool(T,0,0,dt));
 }
 assert.equal(cool(0,0,1,1),0);
});
test('impact release integrates exactly to one payload across arbitrary timestep partitions',()=>{
 const fn=scalar(abilityMotionWGSL,'abilityImpactRelease',['t'],{powerTimeStep:()=>0});
 for(const dt of [1/30,1/60,.007,.023]){
  let total=0;for(let lo=0;lo<.65;lo+=dt){const h=Math.min(dt,.65-lo);total+=h*fn(lo+h/2,Math.max,Math.min,Math.pow,Math.exp,()=>h);}
  assert.ok(Math.abs(total-1)<1e-12,String(total));
 }
});
test('a workgroup owns each fine combustion record exactly once',()=>{
 const owned=new Set(),D=32;
 for(let bz=0;bz<4;bz++)for(let by=0;by<4;by++)for(let bx=0;bx<4;bx++)for(let groupY=0;groupY<2;groupY++)for(let groupZ=0;groupZ<4;groupZ++)for(let lane=0;lane<64;lane++){
  const x=bx*8+groupY*4+lane%4,y=by*8+(groupZ%2)*4+Math.floor(lane/4)%4,z=bz*8+Math.floor(groupZ/2)*4+Math.floor(lane/16);
  const index=x+D*(y+D*z);assert.ok(!owned.has(index));owned.add(index);
 }
 assert.equal(owned.size,D**3);
});
test('runtime shock deposition contains all blast families without stencil source reevaluation',()=>{
 const deposit=shockDepositWGSL(32,POWER_DEFINITIONS);assert.ok(deposit.includes('blastEnergySource(x)'));
 assert.ok(!deposit.includes('ctrl.'));assert.ok(deposit.includes('shockImpact'));
 const sweep=shockAdvanceWGSL(32,0,POWER_DEFINITIONS,{gpuClock:true});
 assert.ok(!sweep.includes('energy+=blastEnergySource(x)'));assert.ok(sweep.includes('clock.dt'));
});
