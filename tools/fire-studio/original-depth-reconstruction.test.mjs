import assert from 'node:assert/strict';
import test from 'node:test';
import {readFileSync} from 'node:fs';

// Execute the scalar arithmetic actually injected into the diagnostic shader.
// This is a reconstruction gate; it does not synthesize or substitute gas fields.
const source=readFileSync(new URL('./original-powers-render-qa.py',import.meta.url),'utf8');
const glsl=source.match(/DEPTH_RECONSTRUCTION_GLSL='''([\s\S]+?)'''/)[1];
const functions={};
for(const name of ['depthSlope','depthCubic']){
 const match=glsl.match(new RegExp('float '+name+'\\(([^)]*)\\)\\{([\\s\\S]*?)\\n\\}'));
 const args=match[1].split(',').map(value=>value.trim().replace(/^float /,''));
 const body=match[2].replace(/\bfloat\b/g,'let');
 functions[name]=new Function(...args,'depthSlope','clamp','min','max',body);
}
const clamp=(value,lo,hi)=>Math.min(hi,Math.max(lo,value));
const slope=(a,b)=>functions.depthSlope(a,b,null,clamp,Math.min,Math.max);
const cubic=(a,b,c,d,f)=>functions.depthCubic(a,b,c,d,f,slope,clamp,Math.min,Math.max);

test('Depth reconstruction preserves actual layer values, constants and linear ramps',()=>{
 for(const values of [[0,0,0,0],[2,2,2,2],[0,.1,.4,.5],[.1,2,.05,.02],[0,0,1,1]]){
  assert.equal(cubic(...values,0),values[1]);assert.equal(cubic(...values,1),values[2]);
 }
 for(let i=0;i<=100;i++){
  const f=i/100;assert.ok(Math.abs(cubic(0,1,2,3,f)-(1+f))<1e-14);
  assert.equal(cubic(2,2,2,2,f),2);
 }
});

test('Depth reconstruction introduces no new extrema or negative concentration',()=>{
 let state=17;const random=()=>((state=Math.imul(state,1664525)+1013904223|0)>>>0)/2**32;
 for(let sample=0;sample<10000;sample++){
  const values=Array.from({length:4},()=>random()*3),lo=Math.min(values[1],values[2]),hi=Math.max(values[1],values[2]);
  let prior=values[1];
  for(let i=0;i<=20;i++){
   const value=cubic(...values,i/20);assert.ok(value>=lo&&value<=hi);
   if(values[1]<=values[2])assert.ok(value+1e-13>=prior);else assert.ok(value-1e-13<=prior);
   prior=value;
  }
 }
 assert.equal(slope(-1,2),0);assert.equal(slope(1,-2),0);
});

test('Depth derivative remains continuous across steep neighboring layers',()=>{
 const epsilon=1e-5;
 for(const values of [[0,.1,1.1,1.2,1.5],[1,2,0,1,2],[0,0,0,.1,3],[3,2,.1,.05,0]]){
  const left=(cubic(...values.slice(0,4),1)-cubic(...values.slice(0,4),1-epsilon))/epsilon;
  const right=(cubic(...values.slice(1,5),epsilon)-cubic(...values.slice(1,5),0))/epsilon;
  assert.ok(Math.abs(left-right)<.0003,`${left} != ${right}`);
 }
});

const rateGLSL=source.match(/RATE_RECONSTRUCTION_GLSL='''([\s\S]+?)'''/)[1],rateFunctions={};
for(const name of ['gasReactionRate','reactionResidual']){
 const match=rateGLSL.match(new RegExp('float '+name+'\\(([^)]*)\\)\\{([\\s\\S]*?)\\n\\}'));
 const args=match[1].split(',').map(value=>value.trim().replace(/^float /,''));
 rateFunctions[name]=new Function(...args,'clamp','min','max',match[2].replace(/\bfloat\b/g,'let'));
}
const rate=gas=>rateFunctions.gasReactionRate(...gas,clamp,Math.min,Math.max);
const residual=(stored,local,donor)=>rateFunctions.reactionResidual(stored,local,donor,clamp,Math.min,Math.max);
const filteredRate=(gas,stored,weights)=>{
 const value=[0,0,0];let donor=0,base=0;
 for(let i=0;i<gas.length;i++){for(let c=0;c<3;c++)value[c]+=weights[i]*gas[i][c];donor+=weights[i]*rate(gas[i]);base+=weights[i]*stored[i];}
 return residual(base,rate(value),donor);
};

test('Gas reaction residual retains the actual stored rate at every donor voxel',()=>{
 const gases=[[1,0,1.2],[0,1,.03],[.2,.5,.35],[.05,.1,1],[0,0,0],[.6,.8,2],[.9,.2,.1],[.1,.3,.4]];
 const stored=[0,0,.8,.04,0,1.2,0,.5];
 for(let i=0;i<8;i++)assert.equal(filteredRate(gases,stored,Array.from({length:8},(_,j)=>i===j?1:0)),stored[i]);
});

test('Gas reaction residual stays dark for cold gas or absent reactants',()=>{
 const weights=[.1,.2,.3,.4],stored=[0,0,0,0];
 for(const gases of [Array.from({length:4},(_,i)=>[i/4,1,.12]),Array.from({length:4},(_,i)=>[0,i/4,1.3]),Array.from({length:4},(_,i)=>[i/4,0,1.3])])assert.equal(filteredRate(gases,stored,weights),0);
});

test('Gas reaction residual only changes nonlinear subvoxel mixing and remains bounded by actual reactants',()=>{
 assert.ok(Math.abs(filteredRate([[.1,1,1],[.2,1,1]],[.5,.6],[.5,.5])-.55)<1e-14,'An unchanged limiting reactant gives no residual');
 const mixed=filteredRate([[1,0,1.3],[0,1,1.3]],[0,0],[.5,.5]);
 assert.ok(mixed>0&&mixed<=8*Math.min(.5,.7*.5),'Warm unresolved fuel/air mixing creates bounded local reaction');
 assert.equal(filteredRate([[1,0,1.3],[0,1,1.3]],[0,0],[1,0]),0);
 for(const stored of [0,.1,1,3])for(const local of [0,.2,1,5.6])for(const donor of [0,.4,2,5.6]){
  const value=residual(stored,local,donor);assert.ok(value>=0&&value<=stored+local);
 }
});

const cellGLSL=source.match(/CELL_AVERAGE_RECONSTRUCTION_GLSL='''([\s\S]+?)'''/)[1];
const cellKernel=cellGLSL.match(/float cellAverageWeight\(float distance\)\{([\s\S]*?)\n\}/)[1];
const weight=new Function('distance','abs','pow',cellKernel.replace(/\bfloat\b/g,'let'));
const basis=f=>[f+1,f,f-1,f-2].map(d=>weight(d,Math.abs,Math.pow));
const reconstruct=(values,f)=>basis(f).reduce((sum,w,i)=>sum+values[i]*w,0);
test('Cell average depth reconstruction has nonnegative weights, no new extrema and preserves constants',()=>{
 for(let i=0;i<=1000;i++){
  const weights=basis(i/1000);assert.ok(weights.every(w=>w>=0));
  assert.ok(Math.abs(weights.reduce((a,b)=>a+b)-1)<1e-14);
  assert.ok(Math.abs(reconstruct([2,2,2,2],i/1000)-2)<1e-14);
  for(const values of [[0,1,0,0],[3,0,1,2],[0,0,0,0]]){
   const result=reconstruct(values,i/1000);assert.ok(result>=Math.min(...values)&&result<=Math.max(...values));
  }
 }
});
test('Cell average depth reconstruction preserves integrated mass on a periodic cell sequence',()=>{
 const cells=[0,.1,2,0,1,.3,0,0,.6],count=cells.length;
 for(const f of [0,.05,.2,.5,.7,.95]){
  let total=0;for(let i=0;i<count;i++)total+=reconstruct([-1,0,1,2].map(d=>cells[(i+d+count)%count]),f);
  assert.ok(Math.abs(total-cells.reduce((a,b)=>a+b))<1e-13);
 }
});
