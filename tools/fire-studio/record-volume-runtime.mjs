// Record the actual production host code. Native replay checks its explicit
// bind groups and dispatches without replacing the browser or claiming FPS.
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {fileURLToPath,pathToFileURL} from 'node:url';
const args=process.argv.slice(2), name=args[0];
if(!name||!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,80}$/.test(name))
 throw Error('Provide a new recording name (letters, numbers, hyphens or underscores).');
const option=k=>args.includes('--'+k);
const value=(k,fallback)=>{const i=args.indexOf('--'+k);return i<0?fallback:args[i+1];};
const root=fileURLToPath(new URL('../../',import.meta.url));
const source=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):path.join(root,'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live');
const folder=path.join(root,'work/adaptive-volume-qa',name);
if(fs.existsSync(folder))throw Error('Recording already exists; use a new name.');
fs.mkdirSync(folder,{recursive:true});
const resources=[],operations=[];let nextId=1,nextData=0;
const ref=v=>v?.__rid?{$ref:v.__rid}:Array.isArray(v)?v.map(ref):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([k,x])=>[k,ref(x)])):v;
function resource(kind,desc,methods={}) {const r={__rid:nextId++,...methods};resources.push({id:r.__rid,kind,desc:ref(desc)});return r;}
function dataFile(data,offset=0,size) {
 const bytes=Buffer.from(data instanceof ArrayBuffer?data:data.buffer,data instanceof ArrayBuffer?offset:data.byteOffset+offset,size??(data.byteLength-offset));
 const file=`data-${nextData++}.bin`;fs.writeFileSync(path.join(folder,file),bytes);return file;
}
function commandEncoder(){const commands=[];return {
 clearBuffer(buffer,offset=0,size){commands.push({kind:'clearBuffer',buffer:buffer.__rid,offset,size});},
 copyBufferToBuffer(src,srcOffset,dst,dstOffset,size){commands.push({kind:'copyBuffer',src:src.__rid,srcOffset,dst:dst.__rid,dstOffset,size});},
 beginComputePass(desc={}){const commandsIn=[];commands.push({kind:'compute',desc:ref(desc),commands:commandsIn});return {
  setPipeline(p){commandsIn.push({kind:'pipeline',id:p.__rid});},
  setBindGroup(index,g){commandsIn.push({kind:'group',index,id:g.__rid});},
  dispatchWorkgroups(x,y=1,z=1){commandsIn.push({kind:'dispatch',work:[x,y,z]});},
  dispatchWorkgroupsIndirect(b,offset){commandsIn.push({kind:'indirect',buffer:b.__rid,offset});},end(){},
 };},
 beginRenderPass(desc){const commandsIn=[];commands.push({kind:'render',desc:ref(desc),commands:commandsIn});return {
  setPipeline(p){commandsIn.push({kind:'pipeline',id:p.__rid});},
  setBindGroup(index,g){commandsIn.push({kind:'group',index,id:g.__rid});},
  draw(...work){commandsIn.push({kind:'draw',work});},end(){},
 };},finish(){return commands;},
};}
globalThis.GPUBufferUsage={MAP_READ:1,MAP_WRITE:2,COPY_SRC:4,COPY_DST:8,INDEX:16,VERTEX:32,UNIFORM:64,STORAGE:128,INDIRECT:256,QUERY_RESOLVE:512};
globalThis.GPUTextureUsage={COPY_SRC:1,COPY_DST:2,TEXTURE_BINDING:4,STORAGE_BINDING:8,RENDER_ATTACHMENT:16};
globalThis.GPUMapMode={READ:1};
const device={
 features:new Set(),limits:{maxTextureDimension3D:2048},lost:new Promise(()=>{}),addEventListener(){},
 createTexture(desc){let t;return t=resource('texture',desc,{createView(settings={}){return resource('view',{texture:t,...settings});},destroy(){}});},
 createBuffer(desc){return resource('buffer',desc,{destroy(){}});},
 createSampler(desc={}){return resource('sampler',desc);},
 createShaderModule(desc){return resource('module',desc,{getCompilationInfo:async()=>({messages:[]})});},
 async createComputePipelineAsync(desc){const p=resource('computePipeline',desc);p.label=desc.label;p.getBindGroupLayout=index=>({pipeline:p,index});return p;},
 async createRenderPipelineAsync(desc){const p=resource('renderPipeline',desc);p.label=desc.label;p.getBindGroupLayout=index=>({pipeline:p,index});return p;},
 createBindGroup(desc){return resource('bindGroup',desc);},createCommandEncoder:commandEncoder,
 queue:{
  writeBuffer(buffer,offset,data,dataOffset=0,size){operations.push({kind:'writeBuffer',buffer:buffer.__rid,offset,file:dataFile(data,dataOffset,size)});},
  writeTexture(target,data,layout,size){operations.push({kind:'writeTexture',target:ref(target),layout,size,file:dataFile(data)});},
  submit(buffers){operations.push({kind:'submit',commands:buffers.flat()});},onSubmittedWorkDone:async()=>{},
 },
};
globalThis.fetch=async url=>{const file=fileURLToPath(url),bytes=fs.readFileSync(file);return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};};
const {PyroSolver}=await import(pathToFileURL(path.join(source,'pyro-gpu/solver.js')).href);
const {FIRE_PRESETS,sourceOrigin}=await import(pathToFileURL(path.join(source,'pyro-gpu/presets.js')).href);
const preset=FIRE_PRESETS.find(p=>p.id===value('preset','bonfire'));if(!preset)throw Error('Unknown preset');
const sandbox={window:{}};
vm.runInNewContext(fs.readFileSync(path.join(source,'scene-lights.js'),'utf8').split('  let state=')[0]+'window.catalog=presets;})();',sandbox);
const light=sandbox.window.catalog.studio;
const canvas={width:768,height:432};let back;
const context={configure(){},getCurrentTexture(){return back;}};
const solver=new PyroSolver(device,canvas,{context,format:'rgba8unorm',adaptive:option('flow'),pressureWork:option('pressure'),brickPool:option('pool'),lightWork:option('light'),lightReceivers:option('receivers')});
await solver.init();
back=device.createTexture({size:[768,432],format:'rgba8unorm',usage:16|1});
solver.effect=[...preset.effect];solver.dynamics=[...preset.dynamics];solver.chemistry=[...preset.chemistry];
solver.source=sourceOrigin(preset);solver.objectId=preset.object||null;solver.fuel={gas:0,wood:.35,oil:1}[preset.fuel];
solver.smoke=!!preset.smokeSimulation||preset.id==='smoke-burst';solver.embers=true;
solver.ignition=preset.ignition==='crown'?2:preset.ignition==='all'?1:0;
solver.treeMoisture=preset.moisture||'dry';
// Native replay checks command correctness. Driver telemetry is not fabricated
// into a browser performance claim; both comparisons use this same CFL fixture.
solver.collectTelemetry=async slot=>{slot.pending=false;};
solver.collectPoolTelemetry=async slot=>{slot.poolPending=false;};
await solver.reset();
const normalize=v=>{const n=Math.hypot(...v);return v.map(x=>x/n);};
const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const color=c=>[1,3,5].map(i=>parseInt(c.slice(i,i+2),16)/255);
function camera(angle=16,inspect=false){
 const a=angle*Math.PI/180,eye=[Math.sin(a)*13,3.5,Math.cos(a)*13],f=normalize([-eye[0],2.4-eye[1],-eye[2]]),r=normalize(cross(f,[0,1,0])),u=cross(r,f);
 const v=[...eye,.3443276133/1.25,...r,0,...u,0,...f,0,1,+inspect,light.bounce,24,...color(light.tint).map(x=>x*light.ambient),0];
 for(const k of ['key','rim']){const az=light[k+'Az']*Math.PI/180,pos=[Math.sin(az)*5,light[k+'Height'],1.2+Math.cos(az)*3],dir=normalize([light.aimX-pos[0],light.aimY-pos[1],-pos[2]]),cone=light[k+'Beam']*Math.PI/360;
  v.push(...pos,0,...dir,Math.cos(cone),...color(light[k+'Color']).map(x=>x*light[k]),Math.cos(cone*.7));}
 solver.camera(v);
}
const frames=Number(value('frames',60));
if(!Number.isInteger(frames)||frames<1||frames>3600)throw Error('--frames must be an integer in [1,3600].');
for(let frame=0;frame<frames;frame++){
 if(option('move')&&frame===Math.floor(frames/2))solver.burst([solver.source[0]+.45,solver.source[1]+.15,solver.source[2]-.2]);
 solver.maxSpeed=3;solver.latestTelemetry.sampleFrame=solver.frameNumber;
 camera();const frameResult=await solver.frame(1/60);await solver.drain();
 operations.push({kind:'frame',index:frame,time:solver.time,
  output:solver.output.__rid,dense:solver.c[solver.ci].t.__rid,stats:solver.stats.__rid,substeps:frameResult.substeps,dt:1/60,
  pool:solver.chemistryPool?{plan:solver.chemistryPool.plan,atlas:solver.chemistryPool.fields[solver.ci].texture.__rid,
    pages:solver.chemistryPool.pageTable.__rid,metadata:solver.chemistryPool.metadata.__rid}:null,
  snapshot:frame%6===5||frame===frames-1||frame===Math.floor(frames/2)-1,
  saveField:frame===frames-1||frame===Math.floor(frames/2)-1});
}
for(const [angle,inspect] of [[-50,false],[100,false],[16,true]]){camera(angle,inspect);await solver.frame(0);await solver.drain();operations.push({kind:'frame',index:`view-${angle}-${inspect}`,time:solver.time,output:solver.output.__rid,snapshot:true});}
const target=path.join(folder,'commands.json');fs.writeFileSync(target,JSON.stringify({nativeOnly:true,options:{flow:option('flow'),pool:option('pool'),pressure:option('pressure'),light:option('light'),receivers:option('receivers'),preset:preset.id,frames,move:option('move'),fixedCFLFixture:true},resources,operations}));
console.log(JSON.stringify({target,bytes:fs.statSync(target).size,resources:resources.length,operations:operations.length,dataFiles:nextData}));
