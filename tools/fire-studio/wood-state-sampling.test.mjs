import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
 '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {sampleWoodTrilinear,woodHasThermalCapacity,woodStateWGSL,objectWGSL}=await import(
 pathToFileURL(resolve(root,'pyro-gpu/objects.js')).href);
const {ForestMesh,forestMeshWGSL,forestShadowWGSL}=await import(
 pathToFileURL(resolve(root,'pyro-gpu/forest-mesh.js')).href);
const {WOOD_THERMO}=await import(pathToFileURL(resolve(root,'wood-thermo.js')).href);
const close=(actual,expected)=>actual.forEach((v,i)=>assert.ok(Math.abs(v-expected[i])<1e-12,`${actual} != ${expected}`));
const uv=(fraction,low=[20,20,20])=>fraction.map((v,i)=>(low[i]+v+.5)/64);
const valid=[-.01,1.5,1,1],air=[.01,0,0,0],empty=[0,0,0,0];
const point=p=>p.every(v=>v===20);

test('99% air coverage cannot imitate consumed wood or shrink a healthy surface',()=>{
 const stock=[1,0,0,0],wear=[WOOD_THERMO.dryMoistureFraction,0,0,1];
 const geometry=p=>point(p)?valid:air;
 for(const fraction of [[.99,0,0],[.99,.99,.99],[.9999,.9999,.9999]]){
  close(sampleWoodTrilinear(p=>point(p)?stock:empty,geometry,uv(fraction),stock),stock);
  close(sampleWoodTrilinear(p=>point(p)?wear:empty,geometry,uv(fraction),wear),wear);
 }
});

test('zero-valued occupied wood remains spent, rather than reverting to fresh fallback',()=>{
 const geometry=p=>point(p)?valid:air;
 close(sampleWoodTrilinear(()=>empty,geometry,uv([.99,.99,.99]),[1,0,0,0]),empty);
 close(sampleWoodTrilinear(()=>empty,geometry,uv([.99,.99,.99]),[.08,0,0,1]),empty);
 const mixed=p=>p[0]===20?[.2,2,.1,.3]:[.6,.5,0,.1];
 close(sampleWoodTrilinear(mixed,()=>valid,uv([.25,.7,.8]),[1,0,0,0]),[.3,1.625,.075,.25]);
});

test('capacity and foliage geometry determine support; empty coverage gets healthy stock and wear',()=>{
 assert.equal(woodHasThermalCapacity([-.01,1.5,1,1]),true);
 assert.equal(woodHasThermalCapacity([-.01,1.5,1,3]),true,'finite coating also has thermal capacity');
 assert.equal(woodHasThermalCapacity([.069,1.5,1,8]),true);
 assert.equal(woodHasThermalCapacity([.07,1.5,1,8]),false);
 assert.equal(woodHasThermalCapacity([.03,1.5,1,9]),false,'fracture cap ID is not porous foliage');
 assert.equal(woodHasThermalCapacity([-.03,0,1,1]),false);
 assert.equal(woodHasThermalCapacity([.01,1.5,1,1]),false);
 const stock=[1,0,0,0],wear=[WOOD_THERMO.dampMoistureFraction,0,0,1];
 close(sampleWoodTrilinear(()=>[0,4,1,.8],()=>air,uv([.1,.1,.1]),stock),stock);
 close(sampleWoodTrilinear(()=>[0,4,1,.8],()=>air,uv([.1,.1,.1]),wear),wear);
 // At the texture's clamped corner repeated taps still normalize identically.
 close(sampleWoodTrilinear(()=>[.4,1.2,.03,.2],()=>valid,[0,1,0],stock),[.4,1.2,.03,.2]);
});

test('normal and shadow mesh groups bind the actual current solid proxy',()=>{
 const solid={view:{}},fallback={view:{}},groups=[];
 const camera=new Float32Array(48);
 for(const base of [24,36]){camera[base+5]=-.5;camera[base+6]=.866;camera[base+7]=.8;camera[base+8]=1;}
 const solver={device:{queue:{writeBuffer(){}}},woodStructure:{ready:true},cameraValues:camera,
  objectId:'cybr-tree',objectModels:{'cybr-tree':solid},emptyObject:fallback,si:1,
  surface:[{view:{}},{view:{}}],damage:[{view:{}},{view:{}}],objectSettings:{},view:{},
  woodPoseBindings(){return [[35,{buffer:{}}],[36,{buffer:{}}]];},
  group(pipeline,entries){groups.push({pipeline,entries});return {};}};
 const mesh=Object.assign(Object.create(ForestMesh.prototype),{s:solver,ready:true,
  pipeline:{label:'normal'},shadowPipeline:{label:'shadow'},shadowViews:[{},{}],shadowCameras:[{},{}],
  targets:[{view:{}},{view:{}},{view:{}}],depth:{},draws:[],bark:{view:{}},repeat:{},micro:{view:{}},roughness:{view:{}}});
 const encoder={beginRenderPass(){return {setPipeline(){},setBindGroup(){},end(){}};}};
 mesh.render(encoder);mesh.shadows(encoder);
 assert.equal(groups.length,3);
 for(const {entries} of groups){
  assert.equal(entries.find(([binding])=>binding===11)?.[1],solid);
  assert.equal(entries.find(([binding])=>binding===12)?.[1],solver.surface[1]);
  assert.equal(entries.find(([binding])=>binding===15)?.[1],solver.damage[1]);
  assert.equal(new Set(entries.map(([binding])=>binding)).size,entries.length);
 }
 groups.length=0;solver.objectId='not-loaded';mesh.render(encoder);
 assert.equal(groups[0].entries.find(([binding])=>binding===11)?.[1],fallback);
});

test('production shaders normalize over solid capacity without requiring F32 filtering',()=>{
 assert.match(woodStateWGSL,/textureLoad\(geometry,at,0\)/);
 assert.match(woodStateWGSL,/if\(coverage>0\.\)\{return value\/coverage;\}return fallback;/);
 assert.doesNotMatch(woodStateWGSL,/textureSample|@binding/);
 assert.match(objectWGSL,/surfaceState.*woodTrilinear\(skin,solid,objectUV\(x\),vec4f\(1,0,0,0\)\)/);
 assert.match(objectWGSL,/surfaceWear.*woodTrilinear\(damage,solid,objectUV\(x\),woodFreshWear/);
 for(const shader of [forestMeshWGSL,forestShadowWGSL]){
  assert.match(shader,/@binding\(11\) var solid:texture_3d<f32>/);
  assert.match(shader,/woodTrilinear\(skin,solid,/);
  assert.match(shader,/woodTrilinear\(damage,solid,/);
  assert.doesNotMatch(shader,/woodTrilinear\(skin,(?:at|clamp)|woodTrilinear\(damage,at/);
 }
});
