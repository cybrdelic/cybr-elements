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
      assert.equal(s.params.length,12);assert.ok(s.params.every(p=>p.desc.size===384));
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
