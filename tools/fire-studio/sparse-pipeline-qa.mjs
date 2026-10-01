// Native Dawn module AND backend pipeline validation. No browser, resources,
// bind groups, dispatch or queue submission; this is not a frame-rate test.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
const repo=fileURLToPath(new URL('../../',import.meta.url)),args=process.argv.slice(2);
const option=(key,fallback)=>{const i=args.indexOf('--'+key);return i<0?fallback:args[i+1];};
const runtime=path.resolve(process.env.FIRE_STUDIO_ROOT||path.join(repo,'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const out=path.resolve(repo,option('out','work/sparse-startup-qa/pipelines'));
if(fs.existsSync(out))throw Error('Preserve previous evidence: choose a new --out.');
fs.mkdirSync(out,{recursive:true});
const backend=option('backend','null');
if(!['null','d3d12','vulkan'].includes(backend))throw Error('Unsupported native QA backend');
const packageRoot=path.resolve(repo,option('dawn','work/dawn-qa/node_modules/webgpu'));
const {create,globals}=await import(pathToFileURL(path.join(packageRoot,'index.js')).href);
Object.assign(globalThis,globals);
const settings=['backend='+backend];if(args.includes('--fxc'))settings.push('disable-dawn-features=use_dxc');
let provider=create(settings);
const report={runtime,backend,fxcRequested:args.includes('--fxc'),nativePackage:JSON.parse(fs.readFileSync(path.join(packageRoot,'package.json'))).version,
  browser:false,submittedCommands:0,modules:[],passed:false};let device;
try{
 const adapter=await provider.requestAdapter({powerPreference:option('adapter','discrete')==='integrated'?'low-power':'high-performance'});
 if(!adapter)throw Error('Native adapter unavailable');
 report.adapter={vendor:adapter.info.vendor,device:adapter.info.device,description:adapter.info.description};
 if(backend==='null'&&adapter.info.device!=='null-backend')throw Error('Null backend did not select null adapter');
 device=await adapter.requestDevice();
 for(const method of ['createBuffer','createTexture','createCommandEncoder','createBindGroup'])
  device[method]=()=>{throw Error('Pipeline-only QA forbids '+method);};
 device.queue.submit=()=>{throw Error('Pipeline-only QA forbids queue submission');};
 const uncaptured=[];device.addEventListener('uncapturederror',e=>uncaptured.push(e.error.message));
 const {planBrickPool,brickPoolKernels}=await import(pathToFileURL(path.join(runtime,'pyro-gpu/brick-pool.js')).href);
 for(const options of [{brick:16,capacity:1024},{brick:16,capacity:512},{brick:16,capacity:4},{brick:32,capacity:64}]){
  const plan=planBrickPool({...options,maxTextureDimension3D:device.limits.maxTextureDimension3D});
  for(const [name,code] of Object.entries(brickPoolKernels(plan))){
   const label=`${options.brick}-${options.capacity}-${name}`,file=label+'.wgsl';fs.writeFileSync(path.join(out,file),code);
   const result={label,file,sha256:createHash('sha256').update(code).digest('hex')};
   device.pushErrorScope('validation');
   try{
    const module=device.createShaderModule({code,label:'chemistry-pool-'+name});
    result.messages=(await module.getCompilationInfo()).messages.map(m=>({type:m.type,lineNum:m.lineNum,linePos:m.linePos,message:m.message}));
    if(result.messages.some(m=>m.type==='error'))throw Error('Shader-module validation failed');
    await device.createComputePipelineAsync({label,layout:'auto',compute:{module,entryPoint:'main'}});
    result.pipelineCreated=true;
   }catch(error){result.error=String(error.message||error).slice(0,12000);}
   finally{const scoped=await device.popErrorScope();if(scoped)result.validation=String(scoped.message).slice(0,12000);}
   report.modules.push(result);
  }
 }
 report.uncaptured=uncaptured;
 report.passed=!uncaptured.length&&report.modules.length===40&&report.modules.every(m=>m.pipelineCreated&&!m.error&&!m.validation);
}catch(error){report.failure=String(error.message||error).slice(0,12000);}
finally{device?.destroy();provider=null;fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));}
console.log(JSON.stringify({report:path.join(out,'report.json'),backend,passed:report.passed,modules:report.modules.length,
  failed:report.modules.filter(m=>m.error||m.validation).map(m=>({label:m.label,error:m.error,validation:m.validation})),failure:report.failure||null}));
if(!report.passed)process.exitCode=1;
