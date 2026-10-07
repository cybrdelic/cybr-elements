import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {interpretUpperOperator,incidence,divergence,complete} from './upper-boundary-reference.mjs';
import {interpretHancockGLSL,transportReference,inventory} from './original-compact-reference.mjs';
const code=await readFile(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-fine-flow.js',import.meta.url),'utf8'),context={window:{}};vm.runInNewContext(code,context);const Flow=context.window.OriginalFineFlow;
const near=(a,b,tolerance=1e-9)=>assert(Math.abs(a-b)<=tolerance*Math.max(1,Math.abs(a),Math.abs(b)),`${a} != ${b}`);
test('emitted upper operator equals physical-energy D W^-1 D^T including both clamped edges and floor',()=>{
 for(const [n,floor,extent] of [[[7,8],2,[14,7.875]],[[5,6],0,[3,2]],[[3,4],2,[8,1]]]){
  const g=Flow.upperBoundaryHierarchy({n:[...n,5],floor},extent)[0],stencil=interpretUpperOperator(Flow.upperBoundaryGLSL(g)),system=incidence(n,floor,extent),p=Float64Array.from({length:g.width*g.height},(_,i)=>Math.sin(i*.37));p[p.length-1]=0;
  system.cells.forEach((index,i)=>{const c={x:index%n[0],y:Math.floor(index/n[0])-floor},expected=system.cells.reduce((sum,j,k)=>sum+system.A[i][k]*p[j-floor*n[0]],0);near(stencil.operatorA(p,c),expected);near(stencil.diagonal(c),system.A[i][i]);});
  near(stencil.operatorA(p,{x:g.m,y:g.r}),0);near(stencil.diagonal({x:g.m,y:g.r}),0);
 }
});
test('least physical-energy completion closes representable sources without changing floor flux',()=>{
 const n=[7,8],floor=2,extent=[14,7.875],velocity=[0,1].map(a=>Float64Array.from({length:56},(_,i)=>Math.sin(i*.73+a)*.2));for(let x=0;x<n[0];x++)velocity[1][floor*n[0]+x]=0;
 for(const source of [new Float64Array(56),Float64Array.from({length:56},(_,i)=>i===55?0:.1*Math.cos(i))]){
  const fixed=complete(velocity,n,floor,extent,source),d=divergence(fixed.out,n,floor);for(let i=floor*n[0];i<56;i++)near(d[i],source[i],1e-8);
  for(let x=0;x<n[0];x++)assert.equal(fixed.out[1][floor*n[0]+x],0);
  // Orthogonality to the nullspace establishes minimal physical energy.
  const random=fixed.system.faces.map((_,i)=>Math.cos(i*.8)),divRandom=fixed.system.D.map(row=>row.reduce((sum,v,i)=>sum+v*random[i],0));
  const trial=[new Float64Array(56),new Float64Array(56)];fixed.system.faces.forEach((face,k)=>trial[face.a][face.index]=random[k]);
  const nullspace=complete(trial,n,floor,extent).out,inner=fixed.system.faces.reduce((sum,face,k)=>sum+fixed.delta[k]*nullspace[face.a][face.index]*extent[face.a]**2,0);near(inner,0,1e-8);assert(divRandom.some(v=>Math.abs(v)>0));
 }
});
test('clamped corner cannot manufacture a requested expansion',()=>{
 const n=[5,6],floor=1,velocity=[new Float64Array(30),new Float64Array(30)],source=new Float64Array(30);source[29]=2;
 const fixed=complete(velocity,n,floor,[14,7.875],source);assert.equal(divergence(fixed.out,n,floor)[29],0);assert.equal(source[29],2);
 assert.match(code,/center or midpoint tolerance unmet/);assert.match(code,/rhoTolerance:\.2,etaTolerance:\.1/);
});
test('corrected upper velocities retain signed F/E/S transport inventory closure',()=>{
 const n=[7,8,5],floor=2,plane=n[0]*n[1],upper=[0,1].map(a=>Float64Array.from({length:plane},(_,i)=>.06*Math.sin(i*.51+a)));for(let x=0;x<n[0];x++)upper[1][floor*n[0]+x]=0;
 const completed=complete(upper,n,floor,[14,7.875]).out,v=[new Float32Array(plane*n[2]),new Float32Array(plane*n[2]),new Float32Array(plane*n[2])];completed.forEach((a,i)=>v[i].set(a,plane*(n[2]-1)));
 const kernel=interpretHancockGLSL(Flow.hancockGLSL);for(const scale of [.4,2.5,5]){
  const q=Float32Array.from({length:plane*n[2]},(_,i)=>scale*(.2+.1*Math.cos(i*.9))),before=inventory(q,n),out=transportReference(q,v,n,.1,Flow.schedule,{floor,kernel}),after=inventory(out.q,n);
  assert(out.minCell>=0&&out.minFace>=0);assert(Math.abs(after+out.boundaryLoss-before)/before<16*2**-23);
 }
});
