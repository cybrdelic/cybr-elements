import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {WOOD_FLUX,splitWoodFluxInteger,quantizeWoodFlux,woodFineKernel,advanceWoodFluxCell,
  woodFluxWorkBricks,woodFluxWorkQuery,
  woodFluxClearWGSL,woodFluxScatterWGSL,woodFluxNormalizeWGSL,woodFluxWGSL,WoodFlux}=await import(
  pathToFileURL(resolve(root,'pyro-gpu/wood-flux.js')).href);
const close=(a,b,tolerance=1e-11)=>assert.ok(Math.abs(a-b)<=tolerance,`${a} != ${b}`);

test('trilinear integer partition conserves counters above the u32 limit',()=>{
  let seed=4271;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/2**32;};
  for(let i=0;i<1000;i++){
    const f=[random(),random(),random()],weights=[];
    for(let k=0;k<8;k++)weights.push(f.reduce((w,x,axis)=>w*((k>>axis)&1?x:1-x),1));
    const total=(1n<<45n)+BigInt(i*7919),parts=splitWoodFluxInteger(total,weights);
    assert.equal(parts.reduce((a,b)=>a+b,0n),total);
    assert.ok(parts.every(x=>x>=0n));
    for(let k=0;k<7;k++)assert.ok(Math.abs(Number(parts[k])/Number(total)-weights[k])<1e-12);
  }
  assert.deepEqual(splitWoodFluxInteger(13n,[0,0,0,0,0,0,0,1]),[0n,0n,0n,0n,0n,0n,0n,13n]);
});

test('subquantum mass and sensible energy are retained and eventually released',()=>{
  for(const scale of [WOOD_FLUX.massUnitsPerKg,WOOD_FLUX.energyUnitsPerJ]){
    const amount=.00037/scale;let residual=0,emitted=0n;
    for(let i=0;i<10000;i++){
      const next=quantizeWoodFlux(amount,residual,scale);residual=next.remainder;emitted+=next.units;
      assert.ok(residual>=-1e-18 && residual<1/scale);
    }
    assert.equal(emitted,3n);
    close(Number(emitted)/scale+residual,amount*10000,1e-12/scale);
  }
});

// Independently evaluate the consumer lattice, rather than assuming that a
// producer whose weights sum to1 necessarily matches filtered fine samples.
function basisWeight(coarse,fine){
  const q=fine.map(x=>(x+.5)/2-.5),low=q.map(Math.floor);
  return q.reduce((w,x,axis)=>{
    const f=x-low[axis];return w*(coarse[axis]===low[axis]?1-f:coarse[axis]===low[axis]+1?f:0);
  },1);
}
test('masked 128→256 transfer preserves volume-integrated mass at walls and solid interfaces',()=>{
  for(const coarse of [[64,32,32],[0,0,0],[127,127,127],[0,63,127]]){
    for(const fluid of [()=>true,p=>p[0]%3!==0,p=>p[1]>2*coarse[1],()=>false]){
      const kernel=woodFineKernel(coarse,128,fluid);let mass=0;
      for(const entry of kernel.entries){
        close(basisWeight(coarse,entry.fine),entry.weight);
        mass+=entry.weight*kernel.reciprocal/8; // fine volume = coarse volume /8
      }
      close(mass,kernel.blocked?0:1);
      assert.equal(kernel.blocked,kernel.entries.length===0);
      assert.ok(kernel.volumeFraction>=0&&kernel.volumeFraction<=1);
    }
  }
  const full=woodFineKernel([20,20,20]);assert.equal(full.entries.length,64);
  close(full.volumeFraction,1);close(full.reciprocal,1);
});

test('many blocked generations accumulate once, then release exactly once when fluid opens',()=>{
  let state={mass:0n,energy:0n,blocked:false},emittedMass=0n,emittedEnergy=0n;
  const addedMass=(1n<<40n)+12345n,addedEnergy=(1n<<42n)+321n;
  for(let frame=0;frame<100;frame++){
    const next=advanceWoodFluxCell(state,{mass:addedMass,energy:addedEnergy},0);
    state=next.state;emittedMass+=next.delivered.mass;emittedEnergy+=next.delivered.energy;
    assert.equal(state.mass,addedMass*BigInt(frame+1));assert.equal(state.energy,addedEnergy*BigInt(frame+1));
    assert.equal(next.retained.mass,state.mass);assert.equal(emittedMass,0n);assert.equal(emittedEnergy,0n);
  }
  // Source has STOPPED. Retained fuel still delivers when its fluid kernel opens.
  const opened=advanceWoodFluxCell(state,{mass:0n,energy:0n},.125);
  emittedMass+=opened.delivered.mass;emittedEnergy+=opened.delivered.energy;state=opened.state;
  assert.equal(emittedMass,addedMass*100n);assert.equal(emittedEnergy,addedEnergy*100n);
  assert.equal(opened.retained.mass,0n);assert.equal(opened.retained.energy,0n);
  const later=advanceWoodFluxCell(state,{mass:17n,energy:31n},1);
  assert.equal(later.delivered.mass,17n);assert.equal(later.delivered.energy,31n,'the old generation never reappears');
  const empty=advanceWoodFluxCell(later.state,{mass:0n,energy:0n},0);
  assert.equal(empty.state.blocked,false);assert.equal(empty.state.mass,0n);
});

test('overlapping normalized kernels remain additive across obstructed fluid regions',()=>{
  const source=[[0,0,0],[1,0,0],[1,1,0],[1,1,1]],masses=[.3,.7,2,4],samples=new Map();
  const fluid=p=>(p[0]+p[1]+p[2])%3!==0;
  for(let i=0;i<source.length;i++){
    const kernel=woodFineKernel(source[i],128,fluid);
    for(const {fine,weight} of kernel.entries){const key=fine.join(',');
      samples.set(key,(samples.get(key)||0)+masses[i]*weight*kernel.reciprocal/8);}
  }
  close([...samples.values()].reduce((a,b)=>a+b,0),masses.reduce((a,b)=>a+b,0));
});

function sampleWorkCoverage(coarse,isFluid=()=>true){
  const kernel=woodFineKernel(coarse,128,isFluid);
  const flags=new Set(woodFluxWorkBricks(coarse,kernel.volumeFraction));
  if(kernel.blocked){assert.equal(flags.size,0);return;}
  assert.ok(flags.size<=8,'one basis has at most eight fine work bricks');
  for(const {fine} of kernel.entries){
    // This support ID is obtained from the consumer sample, independently of
    // the producer's coarse footprint bounds.
    const at=fine.map(v=>Math.floor(v/8)),id=at[0]+32*(at[1]+32*at[2]);
    assert.ok(flags.has(id),`missed fine sample ${fine} from donor ${coarse}`);
    for(const count of [32,16,8]){
      const half=3/count,index=fine.map(v=>Math.floor(v/(256/count)));
      const world=index.map((v,axis)=>(axis===1?0:-3)+(v+.5)*6/count);
      const queried=woodFluxWorkQuery(world,half);
      assert.ok(queried.includes(id),`B${count} misses its contained sample ${fine}`);
      assert.ok(queried.some(i=>flags.has(i)),`B${count} source support false negative`);
      if(count===32)assert.equal(queried.length,1);
      if(count===16)assert.ok(queried.length<=27);
    }
  }
}
test('source-work flags cover every kernel sample at walls, corners and changing solids',()=>{
  // All 128 one-dimensional donor positions are exercised on each axis;
  // pairwise corner/brick-boundary combinations cover the 3D OR footprint.
  for(let i=0;i<128;i++)for(const coarse of [[i,0,127],[127,i,0],[0,127,i]])
    sampleWorkCoverage(coarse);
  const boundaries=[0,1,3,4,63,64,123,124,126,127];
  for(const z of boundaries)for(const y of boundaries)for(const x of boundaries){
    const coarse=[x,y,z];sampleWorkCoverage(coarse,p=>(p[0]+2*p[1]+3*p[2])%5===0);
  }
  for(const corner of [[0,0,0],[127,127,127],[0,127,0],[127,0,127]])
    sampleWorkCoverage(corner,()=>false);
  assert.deepEqual(woodFluxWorkBricks([64,64,64],1,false),[],'empty increment never marks work');
});
test('work flags renew from retained fuel after SourceStop and follow moved donor destinations',()=>{
  let state={mass:0n,energy:0n,blocked:false};
  for(let frame=0;frame<40;frame++){
    state=advanceWoodFluxCell(state,{mass:23n,energy:41n},0).state;
    assert.deepEqual(woodFluxWorkBricks([63,0,127],0,state.mass>0n||state.energy>0n),[]);
  }
  const released=advanceWoodFluxCell(state,{mass:0n,energy:0n},.125);
  const releaseFlags=woodFluxWorkBricks([63,0,127],.125,released.delivered.mass>0n);
  assert.ok(releaseFlags.length>0,'SourceStop does not suppress retained release support');
  const next=advanceWoodFluxCell(released.state,{mass:0n,energy:0n},1);
  assert.deepEqual(woodFluxWorkBricks([63,0,127],1,next.delivered.mass>0n),[],
    'a fresh clear drops the already delivered generation');
  // Rest→posed donor destination changes scatter anchors; work support must
  // follow each new world location, including a floor and chamber-wall corner.
  for(const world of [[-2.999,.001,-2.999],[2.999,5.999,2.999],[1.25,.15,-.75],[-1.5,2.4,1.6]]){
    const q=world.map((v,axis)=>(v-(axis===1?0:-3))/(6/128)-.5),low=q.map(Math.floor);
    const movedFlags=new Set();
    for(let k=0;k<8;k++){
      const cell=low.map((v,axis)=>Math.max(0,Math.min(127,v+((k>>axis)&1))));
      woodFluxWorkBricks(cell).forEach(id=>movedFlags.add(id));
      const kernel=woodFineKernel(cell);
      for(const {fine} of kernel.entries){
        const at=fine.map(v=>Math.floor(v/8)),id=at[0]+32*(at[1]+32*at[2]);
        assert.ok(movedFlags.has(id));
      }
    }
    assert.ok(movedFlags.size>0);
  }
});

function fixture({compileFailure=false,writeFailure=false}={}){
  globalThis.GPUBufferUsage={STORAGE:1,COPY_DST:2,COPY_SRC:4};
  globalThis.GPUTextureUsage={TEXTURE_BINDING:1,COPY_DST:2};
  const buffers=[],textures=[],groups=[],commands=[];
  const resource=label=>({label,destroyCount:0,destroy(){this.destroyCount++;},createView(){return {label:this.label+' view'};}});
  const device={
    queue:{writeBuffer(){},writeTexture(){if(writeFailure)throw Error('upload failed');}},
    createBuffer(desc){const r=Object.assign(resource(desc.label),desc);buffers.push(r);return r;},
    createTexture(desc){const r=Object.assign(resource(desc.label),desc);textures.push(r);return r;},
    createShaderModule(desc){return desc;},
    async createComputePipelineAsync(desc){if(compileFailure&&desc.label==='wood-flux-normalize')throw Error('compile failed');return {label:desc.label,getBindGroupLayout(){return {};}};},
    createBindGroup(desc){groups.push(desc);return desc;},
  };
  const encoder={clearBuffer(r,offset=0,size){commands.push(['clear',r.label,offset,size]);},beginComputePass(){
    let label;return {setPipeline(p){label=p.label;commands.push(['pipeline',label]);},
      setBindGroup(){commands.push(['bind',label]);},dispatchWorkgroups(...dims){commands.push(['dispatch',label,...dims]);},end(){commands.push(['end',label]);}};
  }};
  const options={params:{},settings:{},skin:{view:{}},metadata:{view:{}},normalizationBindings:[[1,{}],[11,{view:{}}],[13,{buffer:{}}],[40,{buffer:{}}],[43,{buffer:{}}]]};
  return {device,buffers,textures,groups,commands,encoder,options};
}
test('actual class selectively clears delivered cells before scatter/normalize without resetting cumulative escape',async()=>{
  const f=fixture(),flux=await new WoodFlux(f.device).init(),sizes=f.buffers.map(b=>b.size);
  assert.equal(flux.flux.size,128**3*6*4+64+32**3*4);assert.equal(flux.residual.size,64**3*8);
  assert.equal(flux.statsOffset,128**3*6*4);
  assert.equal(flux.workOffset,flux.statsOffset+64);
  flux.encode(f.encoder,f.options);flux.encode(f.encoder,f.options);
  assert.deepEqual(f.buffers.map(b=>b.size),sizes);
  assert.equal(f.groups.length,3);
  assert.deepEqual(f.commands.slice(0,5),[['clear','wood-flux',flux.statsOffset,32],['pipeline','wood-flux-clear-delivered'],['bind','wood-flux-clear-delivered'],['dispatch','wood-flux-clear-delivered',32,32,32],['end','wood-flux-clear-delivered']]);
  assert.deepEqual(f.commands[7],['dispatch','wood-flux-scatter',16,16,16]);
  assert.deepEqual(f.commands[11],['dispatch','wood-flux-normalize',32,32,32]);
  assert.equal(WOOD_FLUX.ledger.escapedWord,8);
  const before=f.commands.length;flux.reset(f.encoder);
  assert.deepEqual(f.commands.slice(before),[['clear','wood-flux',0,undefined],['clear','wood-flux-remainder',0,undefined]]);
  assert.equal(f.buffers.length,5);flux.destroy();flux.destroy();
  assert.ok(f.buffers.every(b=>b.destroyCount===1));
});

const bytes=()=>{const data=new Float32Array(64**3*4);data[3]=.25;data[7]=.75;return data.buffer;};
test('actual metadata cache retries rejected loads and disposes uploaded textures exactly once',async()=>{
  const f=fixture(),flux=await new WoodFlux(f.device).init();let requests=0;
  const previous=globalThis.fetch;
  globalThis.fetch=async()=>{requests++;return {ok:true,arrayBuffer:async()=>requests===1?new ArrayBuffer(4):bytes()};};
  try{
    await assert.rejects(flux.loadMetadata('scene'),/size/);
    const [a,b]=await Promise.all([flux.loadMetadata('scene'),flux.loadMetadata('scene')]);
    assert.equal(a,b);assert.equal(a.modelMassKg,1);assert.equal(requests,2);assert.equal(f.textures.length,1);
    assert.equal(f.textures[0].dimension,'3d');
    flux.destroy();await Promise.resolve();assert.equal(f.textures[0].destroyCount,1);
    await assert.rejects(flux.loadMetadata('other'),/closed/);assert.equal(requests,2);
  }finally{globalThis.fetch=previous;flux.destroy();}
});
test('compile/upload/dispose-during-load failures release fixed resources without late allocation',async()=>{
  const compile=fixture({compileFailure:true}),a=new WoodFlux(compile.device);
  await assert.rejects(a.init(),/compile failed/);assert.ok(compile.buffers.every(b=>b.destroyCount===1));
  const previous=globalThis.fetch;
  try{
    globalThis.fetch=async()=>({ok:true,arrayBuffer:async()=>bytes()});
    const upload=fixture({writeFailure:true}),b=await new WoodFlux(upload.device).init();
    await assert.rejects(b.loadMetadata('scene'),/upload failed/);assert.equal(upload.textures[0].destroyCount,1);b.destroy();
    let finish;globalThis.fetch=()=>new Promise(resolve=>{finish=resolve;});
    const closing=fixture(),c=await new WoodFlux(closing.device).init(),pending=c.loadMetadata('scene');c.destroy();
    finish({ok:true,arrayBuffer:async()=>bytes()});await assert.rejects(pending,/closed/);
    assert.equal(closing.textures.length,0);assert.ok(closing.buffers.every(b=>b.destroyCount===1));
  }finally{globalThis.fetch=previous;}
});
test('production shader contracts keep active support and solid exclusion consistent',()=>{
  assert.match(woodFluxScatterWGSL,/owner!=0xffffffffu&&owner<arrayLength\(&woodNodes\)/);
  assert.match(woodFluxScatterWGSL,/world>=vec3f\(3,6,3\)/);
  assert.match(woodFluxScatterWGSL,/remainingMass=woodWordSubtract/);
  assert.match(woodFluxScatterWGSL,/residual\[donor\]=pending-/);
  assert.match(woodFluxClearWGSL,/atomicLoad\(&flux\[index\+5u\]\)==0u/);
  assert.match(woodFluxClearWGSL,/if\(all\(id<vec3u\(32\)\)\)\{atomicStore/);
  assert.match(woodFluxScatterWGSL,/woodAtomicAdd\(\d+u\+8u,mass\)/);
  assert.match(woodFluxScatterWGSL,/woodAtomicAdd\(\d+u\+10u,energy\)/);
  assert.match(woodFluxNormalizeWGSL,/objectDistance\(at\)<-\.02/);
  assert.match(woodFluxNormalizeWGSL,/8\.\/integral/);
  assert.match(woodFluxNormalizeWGSL,/index\+5u\],1u/);
  assert.match(woodFluxNormalizeWGSL,/atomicOr\(&flux\[\d+u\+x\+32u\*\(y\+32u\*z\)\],1u\)/);
  assert.match(woodFluxWGSL,/@binding\(34\) var<storage,read>/);
  assert.match(woodFluxWGSL,/fn woodFluxLive/);
  const live=woodFluxWGSL.slice(woodFluxWGSL.indexOf('fn woodFluxLive'));
  assert.match(live,/if\(halfBrick==3\.\/32\.\)/);
  assert.doesNotMatch(live,/index\+5u|128\*|vec3i\(127\)/,'support queries only the 32³ work words');
  assert.doesNotMatch(woodFluxWGSL,/p\.step\.x|textureSampleLevel/);
});
