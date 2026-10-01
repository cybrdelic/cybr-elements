// Strict CPU-side Tint validation via official Dawn's null backend.
// This does not launch a browser, allocate GPU resources, create pipelines or
// submit render/compute commands. Native field/pixel gates are separate.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
const repo=fileURLToPath(new URL('../../',import.meta.url));
const runtime=path.resolve(process.env.FIRE_STUDIO_ROOT||path.join(repo,
  'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const args=process.argv.slice(2),option=(name,fallback)=>{
  const index=args.indexOf('--'+name);return index<0?fallback:args[index+1];
};
const out=path.resolve(repo,option('out','work/dawn-qa/tint-production'));
if(fs.existsSync(out))throw Error('Preserve previous evidence; choose a new --out directory.');
fs.mkdirSync(out,{recursive:true});
const load=file=>import(pathToFileURL(path.join(runtime,file)).href);
const sourceModules=new Map();
function add(label,code){
  if(typeof code!=='string'||!/@(?:compute|vertex|fragment)\b/.test(code))return;
  const sha256=createHash('sha256').update(code).digest('hex');
  if(sourceModules.has(sha256)){sourceModules.get(sha256).labels.push(label);return;}
  const file=String(sourceModules.size).padStart(3,'0')+'-'+sha256.slice(0,12)+'.wgsl';
  fs.writeFileSync(path.join(out,file),code);
  sourceModules.set(sha256,{sha256,file,labels:[label],code});
}
const addFamily=(label,shaders)=>{for(const [name,code] of Object.entries(shaders))add(label+'/'+name,code);};

const {rendererShaders,dilateWGSL,dilateReceiversWGSL}=await load('pyro-gpu/renderer.js');
const {forestMeshWGSL,forestShadowWGSL}=await load('pyro-gpu/forest-mesh.js');
const {simulationShaders,pressureShaders}=await load('pyro-gpu/shaders.js');
const {adaptiveFlowShaders}=await load('pyro-gpu/adaptive-flow.js');
const {adaptivePressureShaders}=await load('pyro-gpu/adaptive-pressure.js');
const {lightingWorkShaders}=await load('pyro-gpu/lighting-work.js');
const {planBrickPool,brickPoolScalarShaders,brickPoolKernels}=await load('pyro-gpu/brick-pool.js');
const {pooledChemistryConsumer}=await load('pyro-gpu/pooled-coupling.js');
const {woodStructureWGSL}=await load('wood-structure.js');
const pool=planBrickPool({D:256,capacity:1024,maxTextureDimension3D:2048});

for(const tree of [false,true])for(const sparse of [false,true])for(const seams of [false,true]){
  const family=rendererShaders(tree,sparse,seams);
  addFamily(`renderer/tree-${tree}/sparse-${sparse}/seams-${seams}`,family);
}
for(const tree of [false,true]){
  for(const [name,code] of Object.entries(rendererShaders(tree)))
    add(`renderer/pooled/tree-${tree}/${name}`,pooledChemistryConsumer(code,pool,
      {texture:'chem',atlasBinding:25,pagesBinding:28,metadataBinding:29}));
}
add('forest/mesh',forestMeshWGSL);add('forest/shadow',forestShadowWGSL);
add('renderer/dilate',dilateWGSL);add('renderer/dilate-receivers',dilateReceiversWGSL);
for(const flowSupport of [false,true]){
  const shaders=simulationShaders(128,256,{flowSupport});
  addFamily('solver/flow-support-'+flowSupport,shaders);
  addFamily('solver/pooled/flow-support-'+flowSupport,brickPoolScalarShaders(pool,{N:128,shaders}));
  add('solver/pooled/velocity/'+flowSupport,pooledChemistryConsumer(shaders.correctVelocity,pool,{texture:'chem'}));
}
for(let n=128;n>=4;n/=2)addFamily('pressure/'+n,pressureShaders(n));
const adaptive=adaptiveFlowShaders(128,256);
addFamily('adaptive-flow',adaptive);
for(const name of ['coarseCorrect','fineCorrect'])
  add('adaptive-flow/pooled/'+name,pooledChemistryConsumer(adaptive[name],pool,{texture:'chem'}));
addFamily('adaptive-pressure',adaptivePressureShaders());
addFamily('lighting-work',lightingWorkShaders);addFamily('brick-pool',brickPoolKernels(pool));
for(const file of ['pyro-gpu/objects.js','pyro-gpu/embers.js','pyro-gpu/floor-fuel.js',
  'pyro-gpu/wood-collision.js','pyro-gpu/wood-flux.js']){
  const module=await load(file);
  for(const [name,code] of Object.entries(module))if(name.endsWith('WGSL'))add(file+'/'+name,code);
}
add('wood-structure',woodStructureWGSL());
for(const [file,name,texture] of [
  ['pyro-gpu/objects.js','surfaceWGSL','gas'],
  ['pyro-gpu/objects.js','basicSurfaceWGSL','gas'],
  ['pyro-gpu/embers.js','emberComputeWGSL','gas'],
  ['pyro-gpu/embers.js','emberRenderWGSL','gas'],
  ['pyro-gpu/floor-fuel.js','floorFuelUpdateWGSL','chem'],
]){
  const module=await load(file);
  add('pooled/'+file+'/'+name,pooledChemistryConsumer(module[name],pool,{texture}));
}
// The two inline modules (present/clear) are constant literals in the host.
// Extract their exact source without evaluating any host JavaScript.
const solverHost=fs.readFileSync(path.join(runtime,'pyro-gpu/solver.js'),'utf8');
for(const expression of [/\bcode:\s*`([^`]+)`/g,/\bthis\.pipeline\(\s*`([^`]+)`/g]){
  for(const match of solverHost.matchAll(expression)){
    if(match[1].includes('${'))throw Error('Dynamic inline shader needs an explicit reviewed export.');
    add('solver/inline/'+match.index,match[1]);
  }
}

const packageRoot=path.resolve(repo,option('dawn','work/dawn-qa/node_modules/webgpu'));
const packageInfo=JSON.parse(fs.readFileSync(path.join(packageRoot,'package.json'),'utf8'));
const {create,globals}=await import(pathToFileURL(path.join(packageRoot,'index.js')).href);
Object.assign(globalThis,globals);
let provider=create(['backend=null']);
const adapter=await provider.requestAdapter();
if(!adapter)throw Error('Dawn null backend returned no adapter.');
if(adapter.info?.device!=='null-backend')throw Error('Compiler gate refuses any non-null adapter.');
const device=await adapter.requestDevice();
const report={kind:'Tint module validation through Dawn null backend',nativePackage:packageInfo.version,
  runtime,backend:'null',adapter:{vendor:adapter.info?.vendor,device:adapter.info?.device,
    description:adapter.info?.description},browser:false,physicalGPUWork:false,submittedCommands:0,
  positiveControl:null,negativeControl:null,modules:[],errors:0,warnings:0};
const formatMessages=info=>info.messages.map(m=>({type:m.type,lineNum:m.lineNum,
  linePos:m.linePos,message:m.message}));
// Enforce the scope even if a later edit accidentally adds host rendering.
for(const method of ['createBuffer','createTexture','createCommandEncoder','createComputePipeline',
  'createComputePipelineAsync','createRenderPipeline','createRenderPipelineAsync'])
  device[method]=()=>{throw Error('Compiler-only gate forbids '+method);};
device.queue.submit=()=>{throw Error('Compiler-only gate forbids queue submission');};
device.addEventListener('uncapturederror',()=>{});
async function compile(code,label){
  device.pushErrorScope('validation');
  const module=device.createShaderModule({code,label});
  const messages=formatMessages(await module.getCompilationInfo());
  const validation=await device.popErrorScope();
  return {messages,validation:validation?.message||null};
}
try{
  const positive=`@fragment fn fragment(@location(0) value:f32)->@location(0) vec4f{
    let gradient=dpdx(value);if(value>0.){return vec4f(gradient);}return vec4f(0);}`;
  report.positiveControl=await compile(positive,'uniform derivative positive control');
  if(report.positiveControl.messages.some(m=>m.type==='error')||report.positiveControl.validation)
    throw Error('Strict compiler positive control failed.');
  const negative=`diagnostic(error, derivative_uniformity);
    @fragment fn fragment(@location(0) value:f32)->@location(0) vec4f{
    if(value>0.){return vec4f(dpdx(value));}return vec4f(0);}`;
  report.negativeControl=await compile(negative,'divergent derivative negative control');
  if(!report.negativeControl.messages.some(m=>m.type==='error'&&/uniform|dpdx|derivative/i.test(m.message)))
    throw Error('Strict compiler did not reject the deliberately divergent derivative.');
  fs.writeFileSync(path.join(out,'positive-control.wgsl'),positive);
  fs.writeFileSync(path.join(out,'negative-control.wgsl'),negative);
  for(const item of sourceModules.values()){
    const result=await compile(item.code,item.labels[0]);
    const errors=result.messages.filter(m=>m.type==='error');
    const warnings=result.messages.filter(m=>m.type==='warning');
    report.errors+=errors.length+(result.validation&&errors.length===0?1:0);report.warnings+=warnings.length;
    report.modules.push({file:item.file,sha256:item.sha256,labels:item.labels,...result});
  }
}catch(error){report.failure=error.message;}
finally{
  device.destroy();provider=null;
  report.moduleCount=report.modules.length;
  report.sourceVariants=[...sourceModules.values()].reduce((sum,item)=>sum+item.labels.length,0);
  report.passed=!report.failure&&report.errors===0&&report.modules.length===sourceModules.size;
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));
}
console.log(JSON.stringify({report:path.join(out,'report.json'),passed:report.passed,
  modules:report.moduleCount,sourceVariants:report.sourceVariants,errors:report.errors,
  warnings:report.warnings,failure:report.failure||null}));
if(!report.passed)process.exitCode=1;
