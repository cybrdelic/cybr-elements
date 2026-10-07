// CPU host execution catches release-module and JS startup regressions. These
// doubles do not compile WGSL or measure GPU performance; native gates do that.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {resolve,relative} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {PyroSolver}=await import(pathToFileURL(resolve(root,'pyro-gpu/solver.js')).href);
const {volumeOptions}=await import(pathToFileURL(resolve(root,'simulation-modes.js')).href);

test('release entry module graph resolves every local static and literal dynamic import',()=>{
  const visited=new Set(),pending=[resolve(root,'pyro-gpu/app.js'),resolve(root,'studio.js')];
  while(pending.length){
    const filename=pending.pop();if(visited.has(filename))continue;
    assert.ok(fs.existsSync(filename),'Missing release module '+relative(root,filename));visited.add(filename);
    const source=fs.readFileSync(filename,'utf8');
    const imports=[...source.matchAll(/\bimport\s+(?:[^;]*?\s+from\s+)?['"]([^'"]+)['"]/g),
      ...source.matchAll(/\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g)];
    for(const [,specifier] of imports){
      if(!specifier.startsWith('.'))continue;
      const file=fileURLToPath(new URL(specifier,pathToFileURL(filename)));
      assert.ok(relative(root,file).split(/[\\/]/)[0]!=='..','Module escapes release root');
      pending.push(file);
    }
  }
  assert.ok(visited.has(resolve(root,'wood-thermo.js')));
  assert.ok(visited.has(resolve(root,'pyro-gpu/wood-flux.js')));
});

function fixture({failPipeline}={}){
  globalThis.GPUBufferUsage={MAP_READ:1,MAP_WRITE:2,COPY_SRC:4,COPY_DST:8,INDEX:16,VERTEX:32,UNIFORM:64,STORAGE:128,INDIRECT:256,QUERY_RESOLVE:512};
  globalThis.GPUTextureUsage={COPY_SRC:1,COPY_DST:2,TEXTURE_BINDING:4,STORAGE_BINDING:8,RENDER_ATTACHMENT:16};
  globalThis.GPUMapMode={READ:1};
  const resources=[],pipelines=[],dispatches=[],writes=[],requests=[];let destroyCount=0;
  const resource=(kind,desc={})=>{
    const r={kind,desc,destroyCount:0,destroy(){this.destroyCount++;},createView(settings={}){return resource('view',{texture:this,...settings});}};
    resources.push(r);return r;
  };
  const encoder=()=>({clearBuffer(){},copyBufferToBuffer(){},
    beginComputePass(){let pipeline,group;return {setPipeline(p){pipeline=p;},setBindGroup(_,g){group=g;},
      dispatchWorkgroups(...work){dispatches.push({pipeline,group,work});},dispatchWorkgroupsIndirect(buffer,offset){dispatches.push({pipeline,group,buffer,offset});},end(){}};},
    finish(){return {};}});
  const device={features:new Set(),limits:{maxTextureDimension3D:2048},lost:new Promise(()=>{}),addEventListener(){},
    createTexture(desc){return resource('texture',desc);},createBuffer(desc){return resource('buffer',desc);},
    createSampler(desc={}){return resource('sampler',desc);},
    createShaderModule(desc){return {...desc,getCompilationInfo:async()=>({messages:[]})};},
    async createComputePipelineAsync(desc){if(desc.label===failPipeline)throw Error('fixture pipeline failure');const p={...desc,getBindGroupLayout(){return {};}};pipelines.push(p);return p;},
    async createRenderPipelineAsync(desc){const p={...desc,getBindGroupLayout(){return {};}};pipelines.push(p);return p;},
    createBindGroup(desc){
      assert.equal(new Set(desc.entries.map(e=>e.binding)).size,desc.entries.length,'Duplicate explicit resource binding');
      for(const entry of desc.entries){assert.ok(entry.resource,'Missing binding '+entry.binding);if('buffer' in entry.resource)assert.ok(entry.resource.buffer,'Missing buffer '+entry.binding);}
      return desc;
    },createCommandEncoder:encoder,
    queue:{writeBuffer(buffer,offset,data){writes.push({buffer,offset,data:ArrayBuffer.isView(data)?data.slice():data});},
      writeTexture(){},copyExternalImageToTexture(){},submit(){},onSubmittedWorkDone:async()=>{}},
    destroy(){destroyCount++;},
  };
  const adapter={features:new Set(),info:{vendor:'fixture',architecture:'CPU double',device:'no GPU'},
    async requestDevice(options){requests.push(options);return device;}};
  const context={configure(){}},canvas={width:768,height:432,getContext(kind){assert.equal(kind,'webgpu');return context;}};
  return {device,adapter,canvas,resources,pipelines,dispatches,writes,requests,encoder,destroyCount:()=>destroyCount};
}
async function withEnvironment(f,run){
  const previous={fetch:globalThis.fetch,navigator:Object.getOwnPropertyDescriptor(globalThis,'navigator'),bitmap:globalThis.createImageBitmap};
  globalThis.fetch=async url=>{
    const file=fileURLToPath(url),bytes=fs.readFileSync(file);
    return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),
      json:async()=>JSON.parse(bytes.toString('utf8')),blob:async()=>({bytes})};
  };
  globalThis.createImageBitmap=async({bytes})=>({width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20),close(){}});
  Object.defineProperty(globalThis,'navigator',{configurable:true,value:{gpu:{requestAdapter:async()=>f.adapter,getPreferredCanvasFormat:()=> 'rgba8unorm'}}});
  try{return await run();}finally{
    globalThis.fetch=previous.fetch;globalThis.createImageBitmap=previous.bitmap;
    if(previous.navigator)Object.defineProperty(globalThis,'navigator',previous.navigator);else delete globalThis.navigator;
  }
}

test('actual Volume and Sparse startup work with baseline features and no eager wood-flux allocation',async()=>{
  for(const simulation of ['volume','sparse']){
    const f=fixture();await withEnvironment(f,async()=>{
      const s=await PyroSolver.create(f.canvas,volumeOptions(new URLSearchParams(),simulation));
      assert.deepEqual(f.requests,[{requiredFeatures:[]}]);
      assert.equal(s.params.length,12);assert.ok(s.params.every(p=>p.desc.size===1536));
      for(const field of [...s.surface,...s.damage,...s.floorFuel,...s.floorWear])assert.equal(field.t.desc.format,'rgba32float');
      for(const field of [...s.surface,...s.damage])assert.equal(field.t.desc.dimension,'3d');
      assert.equal(s.woodFlux,undefined,'48MiB transfer field remains lazy for default source');
      assert.equal(!!s.chemistryPool,simulation==='sparse');
      assert.ok(f.pipelines.some(p=>p.label==='floor-wood-wear-clear'));
      await s.reset();
      assert.ok(f.dispatches.some(d=>d.pipeline.label==='floor-wood-wear-clear'));
      s.destroy();assert.equal(f.destroyCount(),1);
    });
  }
});

test('shared chemistry owns one field set and migrates without read/write aliasing or new allocations',async()=>{
  const f=fixture();await withEnvironment(f,async()=>{
    const s=await PyroSolver.create(f.canvas,{brickPool:true,sharedChemistry:true});
    assert.equal(s.chemistryPool.plan.separateDenseBytes,0);
    assert.equal(s.chemistryPool.plan.atlasBytes,384*1024**2);
    assert.equal(f.resources.filter(r=>r.kind==='texture'&&r.desc.dimension==='3d'&&r.desc.size.every(n=>n===256)).length,3);
    for(let i=0;i<3;i++)assert.equal(s.c[i].t,s.chemistryPool.fields[i].texture);
    const frozen=f.resources.length;
    for(const ci of [0,1]){
      const before=f.dispatches.length;
      s.chemistryPool.encodeMigrationToDense(f.encoder(),ci,s.c[ci].view);
      const passes=f.dispatches.slice(before);
      assert.deepEqual(passes.map(d=>d.pipeline.label),['chemistry-pool-migrate','chemistry-pool-publishMigration','chemistry-pool-clearMigrationScratch','chemistry-pool-ackMigration']);
      for(const d of passes){
        const views=d.group.entries.map(e=>e.resource).filter(r=>r.kind==='view');
        assert.equal(new Set(views.map(v=>v.desc.texture)).size,views.length,'each migration pass uses distinct physical textures');
      }
    }
    assert.equal(f.resources.length,frozen);
    assert.throws(()=>s.chemistryPool.encodeImportDense(f.encoder(),0,s.c[0].view),/aliased/);
    s.destroy();
    for(const field of s.c)assert.equal(field.t.destroyCount,1,'pool fields have one owner');
  });
});

test('advected detail is reset explicitly, advances once per flow step and retains its state between frames',async()=>{
  const f=fixture();await withEnvironment(f,async()=>{
    const s=await PyroSolver.create(f.canvas,{flowDetail:true});
    await s.reset();
    const clearCount=()=>f.dispatches.filter(d=>d.pipeline.label==='clear-material-flow').length;
    assert.equal(clearCount(),2);
    const frozen=f.resources.filter(r=>r.kind==='texture').length;
    s.step(f.encoder(),1/60,0);s.step(f.encoder(),1/60,1);
    assert.equal(clearCount(),2,'ordinary advancement must not erase transported coordinates');
    const advances=f.dispatches.filter(d=>d.pipeline.label==='advected-material-flow');
    assert.equal(advances.length,2);
    for(const pass of advances){
      assert.notEqual(pass.group.entries.find(e=>e.binding===3).resource,pass.group.entries.find(e=>e.binding===4).resource);
    }
    assert.equal(f.resources.filter(r=>r.kind==='texture').length,frozen);
    assert.equal(s.materialIndex,0);
    await s.reset();assert.equal(clearCount(),4);
    s.destroy();
  });
});

test('fused final transport keeps distinct inputs/outputs for both live field indices',async()=>{
  const f=fixture();await withEnvironment(f,async()=>{
    const s=await PyroSolver.create(f.canvas,{transport:'flux',fuseFinalFlux:true,brickPool:true,sharedChemistry:true});
    await s.reset();const original=[...s.c],field=e=>e.resource;
    for(const ci of [0,1]){
      assert.equal(s.ci,ci);
      const before=f.dispatches.length;s.step(f.encoder(),1/60,ci);
      const passes=f.dispatches.slice(before),advects=passes.filter(d=>/^advectScalar[012]$/.test(d.pipeline.label));
      assert.deepEqual(advects.map(d=>d.pipeline.label),['advectScalar0','advectScalar1']);
      const reaction=passes.find(d=>d.pipeline.label==='correctScalar');
      const value=slot=>field(reaction.group.entries.find(e=>e.binding===slot));
      assert.equal(value(3),s.c[2].view);assert.equal(value(5),s.c[1-ci].view);
      assert.notEqual(value(3),value(5));
      assert.ok(value(2));assert.ok(value(46));assert.ok(value(47));
      assert.deepEqual(new Set(s.c),new Set(original),'mixing reuses the same three storage allocations');
      assert.equal(s.ci,1-ci);
    }
    s.destroy();
  });
});

test('actual finite wooden sources load the production geometry, owners, thermal metadata and mesh',async()=>{
  const f=fixture();await withEnvironment(f,async()=>{
    const s=await PyroSolver.create(f.canvas);
    for(const [id,effect] of [['wood-sigil',[10,1,0,1]],['logs',[20,1,0,1]]]){
      s.objectId=id;s.effect=effect;s.fuel=.35;s.woodTimeScale=12;
      await s.prepareSource();
      assert.ok(s.woodStructure?.ready);assert.ok(s.woodFlux?.scatter);
      assert.equal(s.woodFluxMetadata.t.desc.dimension,'3d');
      assert.equal(s.woodFluxMetadata.t.desc.format,'rgba32float');
      assert.ok(s.woodFluxMetadata.modelMassKg>0);
      assert.ok(s.forestMesh?.ready);assert.ok(s.woodOwners.desc.size===64**3*4);
      await s.reset();s.smoke=false;s.dropFuel([0,0]);s.igniteFuel();
      const encoder=f.encoder();s.step(encoder,1/60,0);
      const params=f.writes.filter(w=>w.buffer===s.params[0]).at(-1).data;
      assert.equal(params.length,96);assert.equal(params[9],3);assert.equal(params[25],1);assert.equal(params[26],12);
      for(let i=0;i<4;i++)assert.equal(params[42+i*16],0,'ordinary wood leaves all ability records inactive');
      const floor=f.dispatches.filter(d=>d.pipeline.label==='floor-fuel').at(-1);
      assert.ok(floor.group.entries.find(e=>e.binding===6));assert.ok(floor.group.entries.find(e=>e.binding===7));
      assert.ok(f.dispatches.some(d=>d.pipeline.label==='wood-flux-normalize'));
      s.objectId=null;await s.prepareSource();
      assert.equal(s.woodFlux,null);assert.equal(s.woodStructure,null);assert.equal(s.forestMesh,null);
    }
    s.destroy();assert.equal(f.destroyCount(),1);
  });
});

test('actual startup rejects a failed shader pipeline and closes the device',async()=>{
  const f=fixture({failPipeline:'correctScalar'});await withEnvironment(f,async()=>{
    await assert.rejects(PyroSolver.create(f.canvas),/fixture pipeline failure/);
    assert.equal(f.destroyCount(),1);
  });
});

test('actual source preparation retries after metadata or mesh fetch failure',async()=>{
  for(const failedFile of ['flux-metadata.rgba32.bin','vertices.bin']){
    const f=fixture();await withEnvironment(f,async()=>{
      const s=await PyroSolver.create(f.canvas),fetchAsset=globalThis.fetch;let failed=false;
      globalThis.fetch=async url=>{
        const file=fileURLToPath(url);
        if(file.endsWith(failedFile)&&!failed){failed=true;throw Error('fixture asset failure');}
        return fetchAsset(url);
      };
      try{
        s.objectId='wood-sigil';s.effect=[10,1,0,1];s.fuel=.35;
        await assert.rejects(s.prepareSource(),/fixture asset failure/);
        await s.prepareSource();
        assert.ok(s.woodStructure?.ready,'retry must construct the full wood graph');
        assert.ok(s.woodFluxMetadata?.modelMassKg>0,'retry must load the finite source metadata');
        assert.ok(s.forestMesh?.ready,'retry must load the actual visible source mesh');
      }finally{s.destroy();}
    });
  }
});
