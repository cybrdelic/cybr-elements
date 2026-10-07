import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const load=name=>import(pathToFileURL(path.join(root,'pyro-gpu',name)).href);
const [pool,coupling,sim,flow,objects,embers,renderer]=await Promise.all([
  'brick-pool.js','pooled-coupling.js','shaders.js','adaptive-flow.js','objects.js','embers.js','renderer.js',
].map(load));
const plan=pool.planBrickPool();

test('every actual chemistry consumer can route to the same generation-checked field',()=>{
  const consumers=[
    [sim.simulationShaders().correctVelocity,'chem'],
    [flow.adaptiveFlowShaders().coarseCorrect,'chem'],
    [flow.adaptiveFlowShaders().fineCorrect,'chem'],
    [objects.basicSurfaceWGSL,'gas'],[objects.surfaceWGSL,'gas'],
    [embers.emberComputeWGSL,'gas'],[embers.emberRenderWGSL,'gas'],
  ];
  for(const tree of [false,true]) for(const code of Object.values(renderer.rendererShaders(tree)))
    consumers.push([code,'chem',{atlasBinding:25,pagesBinding:28,metadataBinding:29}]);
  for(const [code,texture,options] of consumers){
    const adapted=coupling.pooledChemistryConsumer(code,plan,{texture,...options});
    assert.equal(adapted.match(/struct cpPage /g)?.length,1);
    assert.match(adapted,/cpMode\(\)==1u/);
    assert.match(adapted,/cpResident\(index,page\)/);
    assert.match(adapted,/clamp\(uv,vec3f\(0\),vec3f\(1\)\)/);
    const bindings=[...adapted.matchAll(/@group\(0\)\s*@binding\((\d+)\)/g)].map(x=>+x[1]);
    assert.equal(new Set(bindings).size,bindings.length);
  }
});

test('nested reads preserve production clamping and changed consumers fail explicitly',()=>{
  const code='let c=textureSampleLevel(gas,smp,clamp((outside-vec3f(-3,0,-3))/6.,vec3f(0),vec3f(1)),0);';
  assert.match(coupling.pooledChemistryConsumer(code,plan,{texture:'gas'}),
    /coupledUV\(clamp\(\(outside-vec3f\(-3,0,-3\)\)\/6\.,vec3f\(0\),vec3f\(1\)\)\)/);
  assert.throws(()=>coupling.pooledChemistryConsumer('let c=textureSampleLevel(gas,smp,uv,1);',plan,{texture:'gas'}),/level-zero/);
  assert.throws(()=>coupling.pooledChemistryConsumer('no_current_field',plan),/no reviewed field reads/);
});
