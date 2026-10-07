import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {adaptivePressureShaders,AdaptivePressure}=await import(pathToFileURL(path.join(root,'pyro-gpu/adaptive-pressure.js')).href);
const {pressureShaders}=await import(pathToFileURL(path.join(root,'pyro-gpu/shaders.js')).href);

test('fine kernels inherit the reference operator, mixed boundaries and exact update',()=>{
 const baseline=pressureShaders(128,{cache:false}).smooth;
 const actual=adaptivePressureShaders();
 assert.equal(actual.denseSmooth,baseline);
 const update='mix(at(i),(sum(i)+textureLoad(b,i,0).x)/6.,.6666667)';
 for(const name of ['mark','sparseSmooth'])assert.ok(actual[name].includes(update));
 assert.match(actual.mark,/bitcast<u32>\(next\)!=bitcast<u32>\(previous\)/);
 assert.match(actual.build,/z=-1;z<=1/,'three sweeps receive a complete eight-cell interface halo');
 assert.ok(!JSON.stringify(actual).includes('smoke'));
 assert.throws(()=>adaptivePressureShaders(96));
 assert.throws(()=>adaptivePressureShaders(128,{sweeps:9}));
});

test('actual encodeSegment writes GPU indirect commands and completes every pressure destination',()=>{
 const calls=[];let active;
 const pass={setPipeline(pipeline){active=pipeline.name;},setBindGroup(slot,items){calls.push({name:active,items});},dispatchWorkgroups(...work){calls.at(-1).work=work;},dispatchWorkgroupsIndirect(buffer,offset){calls.at(-1).offset=offset;calls.at(-1).commands=buffer;},end(){calls.push({name:'end'});}};
 const resources=Object.fromEntries(['rawMask','mask','tiles','counters','commands'].map(name=>[name,{name}]));
 const s=Object.assign(Object.create(AdaptivePressure.prototype),resources,{B:16,sweeps:3,pipelines:Object.fromEntries(['mark','build','prepare','copyInactive','denseSmooth','sparseSmooth'].map(name=>[name,{name}])),group:(pipeline,items)=>items});
 const pressure=[{name:'p0'},{name:'p1'}],rhs={name:'rhs'};
 const current=s.encodeSegment({beginComputePass:()=>pass},pressure,rhs,0);
 assert.equal(current,1);
 assert.deepEqual(calls.map(call=>call.name),['mark','build','prepare','copyInactive','denseSmooth','sparseSmooth','copyInactive','denseSmooth','sparseSmooth','copyInactive','denseSmooth','sparseSmooth','end']);
 assert.deepEqual(calls[0].work,[16,16,16]);assert.equal(calls[0].items.find(([slot])=>slot===3)[1],s.counters);
 for(const [iteration,old] of [0,1,0].entries()){
  const segment=calls.slice(3+iteration*3,6+iteration*3);
  assert.deepEqual(segment.map(call=>call.offset),[24,0,12]);
  for(const call of segment){assert.equal(call.items.find(([slot])=>slot===0)[1],pressure[old]);assert.equal(call.items.find(([slot])=>slot===2)[1],pressure[1-old]);}
 }
 calls.length=0;s.encodeSegment(null,pressure,rhs,1,pass);
 assert.ok(!calls.some(call=>call.name==='end'),'shared pressure compute pass remains owned by caller');
});

// This CPU dependency model checks support propagation. Native WGSL fixtures
// separately test arithmetic/output equality and complete GPU command cost.
const f=Math.fround;
function model(n){
 const count=n**3,B=n/8,index=(x,y,z)=>x+n*(y+n*z),brick=(x,y,z)=>(x>>3)+B*((y>>3)+B*(z>>3));
 const at=(p,x,y,z)=>{
  const sign=(x<0||x>=n?-1:1)*(y>=n?-1:1)*(z<0||z>=n?-1:1);
  return f(sign*p[index(Math.max(0,Math.min(n-1,x)),Math.max(0,Math.min(n-1,y)),Math.max(0,Math.min(n-1,z)))]);
 };
 const next=(p,b,x,y,z)=>{
  const values=[at(p,x+1,y,z),at(p,x-1,y,z),at(p,x,y+1,z),at(p,x,y-1,z),at(p,x,y,z+1),at(p,x,y,z-1)];
  const sum=values.slice(1).reduce((value,item)=>f(value+item),values[0]);
  const goal=f(f(sum+b[index(x,y,z)])/6),weight=f(.6666667);
  return f(f(at(p,x,y,z)*f(1-weight))+f(goal*weight));
 };
 const sweep=(p,b,mask)=>{
  const out=p.slice();
  for(let z=0;z<n;z++)for(let y=0;y<n;y++)for(let x=0;x<n;x++)if(!mask||mask[brick(x,y,z)])out[index(x,y,z)]=next(p,b,x,y,z);
  return out;
 };
 const support=(p,b)=>{
  const raw=new Uint8Array(B**3),mask=raw.slice(),bits=new Uint32Array(p.buffer),after=new Uint32Array(sweep(p,b).buffer);
  for(let z=0;z<n;z++)for(let y=0;y<n;y++)for(let x=0;x<n;x++)if(bits[index(x,y,z)]!==after[index(x,y,z)])raw[brick(x,y,z)]=1;
  for(let z=0;z<B;z++)for(let y=0;y<B;y++)for(let x=0;x<B;x++)if(raw[x+B*(y+B*z)]){
   for(let dz=-1;dz<=1;dz++)for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)if(x+dx>=0&&x+dx<B&&y+dy>=0&&y+dy<B&&z+dz>=0&&z+dz<B)mask[x+dx+B*(y+dy+B*(z+dz))]=1;
  }
  return mask;
 };
 return {count,index,sweep,support};
}

test('three-sweep support closes source, interface, floor and disjoint-plume dependencies',()=>{
 const m=model(32);
 const cases=[[[15,15,15]],[[7,7,7]],[[0,0,0]],[[31,31,31]],[[4,3,4],[27,25,27]]];
 for(const sources of cases){
  let dense=new Float32Array(m.count),adaptive=dense.slice();const rhs=dense.slice();
  for(const [x,y,z]of sources)rhs[m.index(x,y,z)]=1;
  const mask=m.support(adaptive,rhs);
  for(let sweep=0;sweep<3;sweep++){dense=m.sweep(dense,rhs);adaptive=m.sweep(adaptive,rhs,mask);}
  assert.deepEqual(new Uint32Array(adaptive.buffer),new Uint32Array(dense.buffer));
 }
});
