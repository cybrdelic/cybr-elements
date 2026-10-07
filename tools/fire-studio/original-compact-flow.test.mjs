import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import {hancockReference,interpretHancockGLSL,transportReference,inventory} from './original-compact-reference.mjs';
const source=await readFile(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-fine-flow.js',import.meta.url),'utf8'),context={window:{}};vm.runInNewContext(source,context);const Flow=context.window.OriginalFineFlow,shader=interpretHancockGLSL(Flow.hancockGLSL),f=Math.fround;
let seed=57218;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
test('actual production Hancock GLSL expression order matches independent Float32 oracle exactly',t=>{
 let tested=0;for(let i=0;i<12000;i++){const q=[0,1,2].map(()=>f(random()<.15?0:random()*10**(i%7-3))),l=f((random()-.5)*2),r=f((random()-.5)*2),rate=Math.max(Math.abs(l),Math.abs(r),f(Math.max(r,0)+Math.max(-l,0))),sigma=f(.89/Math.max(rate,1e-10));for(const side of [-1,1]){const args=[...q,l,r,sigma,side],actual=shader(...args),expected=hancockReference(...args);assert.equal(actual,expected);assert(Number.isFinite(actual)&&actual>=0,JSON.stringify({args,actual}));tested++;}}t.diagnostic(JSON.stringify({exactFloat32ScalarComparisons:tested,nativeCompilerParityPending:true}));
});
test('directional schedule bounds actual Float32 CFL without clock or velocity scaling',()=>{
 for(const rates of [[0,0,0],[230.3447,137.2,58.3],[0,0,447],[1e-6,500,1],[9000,4000,3000]]){const plan=Flow.schedule(1/30,rates);assert.deepEqual(Array.from(plan,s=>s.axis),[0,1,2,1,0]);for(const s of plan){assert(s.steps>=1&&s.CFL<=.9);assert(Math.abs(s.delta*s.steps-1/30*s.fraction)<=2e-9);}}
 assert.throws(()=>Flow.schedule(0,[0,0,0]),/Invalid Hancock/);assert.throws(()=>Flow.schedule(1,[1e6,0,0]),/unsupported work/);
});
test('Float32 closed/periodic sparse and dense concentrations remain finite/nonnegative and conserve shared flux',t=>{
 const rows=[];for(const periodic of [false,true])for(const sparse of [false,true])for(const scale of [2.5,.4,5]){const n=[12,9,7],size=n.reduce((a,b)=>a*b),v=[0,1,2].map(axis=>Float32Array.from({length:size},(_,i)=>{const c=[i%n[0],Math.floor(i/n[0])%n[1],Math.floor(i/n[0]/n[1])];return !periodic&&(c[axis]===0||c[axis]===n[axis]-1)?0:(random()-.5)*.6;}));let q=Float32Array.from({length:size},()=>sparse?(random()<.08?scale*random():0):scale*(.001+random())),before=inventory(q,n,{periodic}),minFace=Infinity,minCell=Infinity;for(let k=0;k<12;k++){const out=transportReference(q,v,n,.25,Flow.schedule,{periodic,kernel:shader});q=out.q;assert(q.every(Number.isFinite));assert(out.minFace>=0&&out.minCell>=0,JSON.stringify({periodic,sparse,scale,k,...out,q:undefined}));assert.equal(out.boundaryLoss,0);minFace=Math.min(minFace,out.minFace);minCell=Math.min(minCell,out.minCell);}const relative=(inventory(q,n,{periodic})-before)/before;assert(Math.abs(relative)<3e-6);rows.push({periodic,sparse,scale,relative,minFace,minCell});}t.diagnostic(JSON.stringify(rows));
});
test('actual Float32 shader-expression sweeps match full independent CPU field oracle',()=>{
 const n=[9,7,5],size=n.reduce((a,b)=>a*b),q=Float32Array.from({length:size},(_,i)=>i%5?0:random()*2),v=[0,1,2].map(()=>Float32Array.from({length:size},()=>random()-.5));
 const a=transportReference(q,v,n,.19,Flow.schedule),b=transportReference(q,v,n,.19,Flow.schedule,{kernel:shader});assert.deepEqual(a.q,b.q);assert.equal(a.boundaryLoss,b.boundaryLoss);
});
test('open endpoint half-depth and floor faces account signed boundary flux at positive and negative velocities',t=>{
 const rows=[];for(const axis of [0,1,2])for(const sign of [-1,1]){const n=[16,8,5],size=n.reduce((a,b)=>a*b),q=Float32Array.from({length:size},(_,i)=>.1+2*Math.exp(-(((i%n[0]-12)/2)**2))),v=[0,1,2].map(a=>new Float32Array(size).fill(a===axis?sign*.3:0)),before=inventory(q,n),out=transportReference(q,v,n,.4,Flow.schedule,{floor:2,kernel:shader}),closure=inventory(out.q,n)+out.boundaryLoss-before;assert(Math.abs(closure)<2e-7);assert(out.minCell>=0&&out.minFace>=0);if(axis===1&&sign===-1)assert.equal(out.boundaryLoss,0);else assert(out.boundaryLoss>0);assert(out.sweeps.every(s=>s.CFL<=.9));rows.push({axis,sign,closure,boundaryLoss:out.boundaryLoss,minimum:out.minCell});}t.diagnostic(JSON.stringify(rows));
});
test('Float32 Hancock translation refines at unchanged physical time',t=>{
 const rows=[];for(const nx of [32,64,128]){const n=[nx,3,3],size=n.reduce((a,b)=>a*b),v=[new Float32Array(size).fill(.17),new Float32Array(size),new Float32Array(size)];let q=Float32Array.from({length:size},(_,i)=>1+.2*Math.cos(2*Math.PI*((i%nx+.5)/nx)));for(let k=0;k<30;k++)q=transportReference(q,v,n,1/30,Flow.schedule,{periodic:true}).q;rows.push({nx,error:q.reduce((s,x,i)=>s+Math.abs(x-(1+.2*Math.cos(2*Math.PI*((i%nx+.5)/nx-.17)))),0)/size});}for(let i=1;i<rows.length;i++)assert(rows[i].error<rows[i-1].error*.45);t.diagnostic(JSON.stringify(rows));
});
test('contracting Float32 blob concentrates above initial fuel maximum without a density ceiling',t=>{
 const n=[24,16,5],size=n.reduce((a,b)=>a*b),v=[0,1,2].map(axis=>Float32Array.from({length:size},(_,i)=>axis===2?0:.13*Math.sin(2*Math.PI*(axis===0?i%n[0]:Math.floor(i/n[0])%n[1])/n[axis])));
 let q=Float32Array.from({length:size},(_,i)=>2.5*Math.exp(-((((i%n[0]+.5)/n[0]-.5)**2+((Math.floor(i/n[0])%n[1]+.5)/n[1]-.5)**2)/.012))),before=inventory(q,n),initialMaximum=Math.max(...q);
 for(let k=0;k<20;k++){const out=transportReference(q,v,n,.05,Flow.schedule);assert(out.minCell>=0&&out.minFace>=0);assert.equal(out.boundaryLoss,0);q=out.q;}
 const after=inventory(q,n),maximum=Math.max(...q);assert(maximum>initialMaximum*1.5);assert(Math.abs((after-before)/before)<3e-6);t.diagnostic(JSON.stringify({initialMaximum,maximum,relativeInventoryError:(after-before)/before}));
});
