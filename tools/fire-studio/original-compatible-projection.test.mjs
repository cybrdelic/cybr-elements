import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/coarse-pressure.js',import.meta.url),'utf8');
const near=(a,b,tolerance=1e-10)=>assert(Math.abs(a-b)<=tolerance*Math.max(1,Math.abs(a),Math.abs(b)),`${a} != ${b}`);
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const correctionSource=source.slice(source.indexOf('const correction ='),source.indexOf('this.divergenceProgram'));

test('applied pressure D*G equals the solved anisotropic matrix on every interior and upper-adjacent cell',t=>{
 assert.doesNotMatch(correctionSource,/if\(edge\(c\)\)/);
 for(const axis of ['HX','HZ','HY'])assert(correctionSource.includes('/'+axis));
 let maxError=0,cells=0;
 for(const [n,E]of [[[9,7,5],[14,7.875,1.8]],[[7,8,6],[8,8,4]],[[6,7,9],[3,20,.5]]]){
  const index=(x,y,z)=>(z*n[1]+y)*n[0]+x,h=E.map((e,i)=>e/(n[i]-1));
  const p=new Float64Array(n[0]*n[1]*n[2]);
  for(let z=1;z<n[2]-1;z++)for(let y=1;y<n[1]-1;y++)for(let x=1;x<n[0]-1;x++)p[index(x,y,z)]=Math.sin(x*.71+y*.23-z*.47)+.1*Math.cos(x*y+z);
  const pressure=c=>c.every((v,i)=>v>=0&&v<n[i])?p[index(...c)]:0;
  const gradient=c=>h.map((spacing,axis)=>(pressure(c)-pressure(c.map((v,i)=>v-(i===axis?1:0))))/spacing);
  for(let z=1;z<n[2]-1;z++)for(let y=1;y<n[1]-1;y++)for(let x=1;x<n[0]-1;x++){
   const c=[x,y,z],g=gradient(c);let DG=0,L=0;
   for(let axis=0;axis<3;axis++){
    const plus=c.map((v,i)=>v+(i===axis?1:0)),minus=c.map((v,i)=>v-(i===axis?1:0));
    DG+=(gradient(plus)[axis]-g[axis])/h[axis];
    L+=(pressure(plus)-2*pressure(c)+pressure(minus))/(h[axis]*h[axis]);
   }near(DG,L);maxError=Math.max(maxError,Math.abs(DG-L));cells++;
  }
 }t.diagnostic(JSON.stringify({interiorAndUpperAdjacentCells:cells,maxAbsoluteMatrixError:maxError,scope:'CPU actual forward/backward equations with outer Dirichlet pressure; no GPU/half-float or physical interior floor claim'}));
});

test('upper normal gradient is retained in the exact prior boundary counterexample',()=>{
 const p=[0,1,2,3,0],g=p.map((v,i)=>v-(p[i-1]??0)),DG=[1,2,3].map(i=>g[i+1]-g[i]),L=[1,2,3].map(i=>p[i+1]-2*p[i]+p[i-1]);
 assert.deepEqual(DG,[0,0,-4]);assert.deepEqual(DG,L);
 const old=g.slice();old[0]=0;old[old.length-1]=0;assert.deepEqual([1,2,3].map(i=>old[i+1]-old[i]),[0,0,-1]);
});

const fineIndex=(p,n)=>clamp(p*n-.5,0,n-1);
const sample=(a,p)=>{const q=fineIndex(p,a.length),lo=Math.floor(q),hi=Math.min(a.length-1,lo+1);return a[lo]+(a[hi]-a[lo])*(q-lo);};
test('coarse restriction uses exact fine cell-center positions for velocity reaction and chemistry',()=>{
 assert.match(source,/p=clamp\(p,vec2\(\.5\/float\(FNX\),\.5\/float\(FNZ\)\),vec2\(1\.-\.5\/float\(FNX\),1\.-\.5\/float\(FNZ\)\)\)/);
 assert.match(source,/vec2 pixel=p\*vec2\(float\(FNX\),float\(FNZ\)\)/);
 for(const n of [360,640,504,896,384])for(const extent of [1.8,4,7.875,8,14]){
  const a=Float64Array.from({length:n},(_,i)=>.37*((i+.5)/n*extent)-.2);
  for(const p of [.13,.25,.47,.75,.91])near(sample(a,p),.37*p*extent-.2,1e-12);
  near(sample(a,0),a[0]);near(sample(a,1),a.at(-1));
 }
 // Discontinuous thin fronts must choose the same donors, including clamps.
 const front=Float64Array.from({length:640},(_,i)=>i<325?0:1);
 for(const [p,value]of [[0,0],[.5,0],[324.5/640,0],[325/640,.5],[325.5/640,1],[1,1]])near(sample(front,p),value);
});

test('fine restriction-nullspace pulse remains unresolved by any converged coarse solve',t=>{
 const n=640,c=128,v=new Float64Array(n);v[325]=.04;
 const restricted=Float64Array.from({length:c},(_,i)=>sample(v,i/(c-1)));assert.equal(Math.max(...restricted.map(Math.abs)),0);
 const D=Float64Array.from({length:n},(_,i)=>(v[(i+1)%n]-v[i])*n);
 near(Math.max(...D),25.6);near(Math.min(...D),-25.6);near(D.reduce((s,x)=>s+x,0),0);
 const F=.1,dt=1/30,factors=D.map(d=>Math.exp(-clamp(d*dt,-.5,.5))),mass=factors.reduce((s,x)=>s+F*x,0),relativeGain=(mass-n*F)/(n*F);
 near(relativeGain,.00039883114127,1e-11);
 t.diagnostic(JSON.stringify({n,c,restrictedVelocityMaximum:0,fineDivergence:[Math.min(...D),Math.max(...D)],dilutionFactorRange:[Math.min(...factors),Math.max(...factors)],constantFieldRelativeMassGain:relativeGain,scope:'Corrected coarse sampling still has a fine nullspace; this fixture exposes a limitation, not a passing fine-projection runtime gate'}));
});

function exactPeriodicFineProjection(v,h){
 // One-dimensional compatible Poisson reference: integrate Gp=v-mean(v)
 // around the periodic domain. This solves D*G p=D v to roundoff.
 const mean=v.reduce((sum,x)=>sum+x,0)/v.length,p=new Float64Array(v.length);
 for(let i=1;i<v.length;i++)p[i]=p[i-1]+h*(v[i]-mean);
 const projected=v.map((x,i)=>x-(p[i]-p[(i+v.length-1)%v.length])/h);
 return {p,projected};
}
test('compatible fine projection reference resolves that nullspace without damping or altering thermal target',t=>{
 const v=new Float64Array(640);v[325]=.04;const h=1/v.length,{projected}=exactPeriodicFineProjection(v,h);
 const residual=projected.map((x,i)=>(projected[(i+1)%v.length]-x)/h);
 const max=Math.max(...residual.map(Math.abs));assert(max<1e-10);
 near(projected.reduce((s,x)=>s+x,0),v.reduce((s,x)=>s+x,0),1e-10);
 t.diagnostic(JSON.stringify({fineNullspaceResidualMax:max,strategy:'Compatible fine-grid correction with coarse solve as preconditioner. This is CPU periodic1D reference only; no production fine solver or native performance acceptance.'}));
});

function conservativeFluxStep(F,v,dt,h){
 const flux=v.map((u,i)=>u*(u>=0?F[(i+F.length-1)%F.length]:F[i]));
 return F.map((q,i)=>q-dt/h*(flux[(i+1)%F.length]-flux[i]));
}
test('concentration flux reference closes fixed-domain inventory for the fine pulse and projected flow',()=>{
 const n=640,F=Float64Array.from({length:n},()=>.1),v=new Float64Array(n);v[325]=.04;
 const next=conservativeFluxStep(F,v,1/30,1/n);near(next.reduce((s,x)=>s+x,0),F.reduce((s,x)=>s+x,0));assert(Math.min(...next)>=0);
 const {projected}=exactPeriodicFineProjection(v,1/n),projectedNext=conservativeFluxStep(F,projected,1/30,1/n);
 for(const q of projectedNext)near(q,.1,1e-12);
});

test('sampling and boundary repair keeps budgets clocks and solver iteration policy unchanged',()=>{
 assert.match(source,/this.iterations = options.iterations \?\? 18/);
 assert.match(source,/expansion=min\(max\(reaction,0\.\)\*coefficient,64\.\)/);
 assert.match(source,/float coefficient=uThermal>\.5\?5\.5/);
 const correctionSampler=source.slice(source.indexOf('makeSamplingGLSL() {'),source.indexOf('bind(texture, unit'));
 assert.match(correctionSampler,/vec2 pixel=vec2\(\.5\)\+p\*vec2\(\$\{this.cx - 1\}\.0,\$\{this.cz - 1\}\.0\)/);
});
