import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,'../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {hlleFlux,advanceEulerLine,advanceMusclEulerLine,shockAdvanceWGSL,shockInitWGSL,shockProjectWGSL,shockSubsteps,shockFlowTransferWeight,SHOCK_GRID}=await import(pathToFileURL(resolve(root,'pyro-gpu/shock-euler.js')).href);
const {simulationShaders}=await import(pathToFileURL(resolve(root,'pyro-gpu/shaders.js')).href);

test('HLLE preserves a uniform compressible state exactly',()=>{
 const state=[1,.7,0,0,2.745];
 const flux=hlleFlux(state,state),expected=[.7,.7*.7+1,0,0,(2.745+1)*.7];
 for(let i=0;i<5;i++)assert.ok(Math.abs(flux[i]-expected[i])<1e-12);
 const advanced=advanceEulerLine(Array.from({length:16},()=>state),.01,.1);
 for(const cell of advanced)for(let k=0;k<5;k++)assert.ok(Math.abs(cell[k]-state[k])<1e-12);
});

test('First-order HLLE reference remains conservative and positive on a shock tube',()=>{
 const left=[1,0,0,0,2.5],right=[.125,0,0,0,.25];
 const state=Array.from({length:64},(_,i)=>i<32?left:right),dt=.001,dx=.1;
 const before=state.reduce((sum,u)=>sum+u[0],0),next=advanceEulerLine(state,dt,dx);
 const boundary=hlleFlux(state.at(-1),state.at(-1))[0]-hlleFlux(state[0],state[0])[0];
 const after=next.reduce((sum,u)=>sum+u[0],0);
 assert.ok(Math.abs((after-before)+dt/dx*boundary)<1e-10);
 for(const u of next){assert.ok(u[0]>0);assert.ok(u[4]-u.slice(1,4).reduce((s,m)=>s+m*m,0)/(2*u[0])>0);}
 assert.ok(next.some((u,i)=>i>0&&Math.abs(u[0]-next[i-1][0])>1e-3));
});

test('3D Euler substeps obey the CFL bound and reject a hidden capped step count',()=>{
 assert.ok(shockSubsteps(1/60)<=12);
 assert.throws(()=>shockSubsteps(1/30),/CFL requires 18 substeps; maximum is 12/);
 assert.equal(SHOCK_GRID,32);
 for(const code of [shockAdvanceWGSL(),shockAdvanceWGSL(32,1),shockAdvanceWGSL(32,2)]){
  assert.match(code,/struct U\{rho:f32,mom:vec3f,energy:f32\}/);
  assert.match(code,/fn hlle\(/);
  assert.match(code,/newE\[at\]=next\.energy/);
  assert.doesNotMatch(code,/isFinite/);
 }
 assert.match(shockInitWGSL(),/totalEnergy0\[i\]=2\.5/);
 assert.match(shockProjectWGSL(),/shockVelocity\(x:vec3f\)/);
 const force=simulationShaders().correctVelocity,project=simulationShaders().project;
 assert.match(force,/binding\(60\).*shockRM/s);
 assert.match(force,/out\+=shock.xyz\*p.lifecycle.w/);
 assert.match(force,/expansion\+=shock.w\*p.lifecycle.w/);
 assert.doesNotMatch(project,/shockVelocity|binding\(60\)/,'Shock momentum enters before projection');
 const frameDt=1/60;let total=0;for(let frame=0;frame<26;frame++){
  const remaining=Math.max(0,.42-frame*frameDt);
  total+=shockFlowTransferWeight(frameDt,remaining,0);
  assert.equal(shockFlowTransferWeight(frameDt,remaining,1),0,'CFL substeps after the first do not reapply the same impulse');
 }
 assert.ok(Math.abs(total-1)<1e-9,'The full 0.42-second blast transfers exactly one shock velocity impulse');
 assert.ok(Math.abs(shockFlowTransferWeight(frameDt,.005,0)-.005/.42)<1e-12,'A final partial blast interval transfers only its remaining impulse');
 assert.doesNotMatch(simulationShaders().correctVelocity,/powerBlastExpansion/);
});

test('production MUSCL shared-face limiter conserves every Euler component through a strong blast',()=>{
 let state=Array.from({length:64},(_,i)=>[1,0,0,0,i===32?300:2.5]);
 for(let step=0;step<40;step++){
  const before=state.reduce((s,q)=>s.map((v,k)=>v+q[k]),[0,0,0,0,0]);
  const dt=.003,dx=.1875,{state:next,boundaryFluxes:[left,right]}=advanceMusclEulerLine(state,dt,dx);
  const after=next.reduce((s,q)=>s.map((v,k)=>v+q[k]),[0,0,0,0,0]);
  for(let k=0;k<5;k++)assert.ok(Math.abs(after[k]-before[k]+dt/dx*(right[k]-left[k]))<1e-9);
  for(const q of next){assert.ok(q[0]>1e-5);assert.ok(q[4]-q.slice(1,4).reduce((s,m)=>s+m*m,0)/(2*q[0])>1e-5);}
  state=next;
 }
 assert.ok(state.some((q,i)=>i!==32&&q[4]>3),'energy propagates instead of rejecting individual cells');
});
