/** Record actual Original host GL commands for native GLES replay.
 * No browser, fake gas field, or reduced simulation grid. Default is untouched
 * production; an explicit diagnostic step option only changes the host clock.
 * Commands and binary uploads stay on disk. Native execution is a separate gate. */
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {fileURLToPath,pathToFileURL} from 'node:url';
const repo=fileURLToPath(new URL('../../',import.meta.url));
const root=path.resolve(process.env.FIRE_STUDIO_ROOT||path.join(repo,'outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const args=process.argv.slice(2),option=(name,fallback)=>{const i=args.indexOf('--'+name);return i<0?fallback:args[i+1];};
const out=path.resolve(option('out','work/original-powers-visual/baseline'));
const enums=JSON.parse(fs.readFileSync(option('enums',path.join(out,'gl-enums.json')),'utf8'));
fs.mkdirSync(path.join(out,'uploads'),{recursive:true});
let serial=0,clock=0,sink=null,commands=0,draws=0;
function encode(value){
 if(value?.resource)return {$ref:value.id};
 if(value?.uniform)return {$uniform:value.program.id,name:value.name};
 if(ArrayBuffer.isView(value)){
  if(value.length<=64)return {$typed:value.constructor.name,data:Array.from(value)};
  const bytes=Buffer.from(value.buffer,value.byteOffset,value.byteLength),sha=createHash('sha256').update(bytes).digest('hex');
  const file='uploads/'+sha+'.bin';if(!fs.existsSync(path.join(out,file)))fs.writeFileSync(path.join(out,file),bytes);
  return {$binary:file,type:value.constructor.name,length:value.length};
 }
 if(Array.isArray(value))return value.map(encode);
 return value;
}
function record(name,values,result){const command={name,args:values.map(encode)};if(result)command.result=result.id;fs.writeSync(sink,JSON.stringify(command)+'\n');commands++;if(name==='drawArrays'||name==='drawElements')draws++;}
const gl=new Proxy(enums,{get(target,key){
 if(key in target)return target[key];
 if(key==='getExtension')return name=>name==='WEBGL_lose_context'?{loseContext(){}}:['EXT_color_buffer_float','OES_texture_float_linear'].includes(name)?{}:null;
 if(key==='getParameter')return name=>name===enums.MAX_TEXTURE_SIZE?16384:0;
 if(key==='getShaderParameter'||key==='getProgramParameter')return ()=>true;
 if(key==='getShaderInfoLog'||key==='getProgramInfoLog')return ()=>'';
 if(key==='checkFramebufferStatus')return ()=>enums.FRAMEBUFFER_COMPLETE;
 if(key==='getUniformLocation')return (program,name)=>({uniform:true,program,name});
 if(key==='getError')return ()=>0;
 if(String(key).startsWith('create'))return (...values)=>{const resource={resource:true,id:++serial};record(key,values,resource);return resource;};
 return (...values)=>record(key,values);
}});
const aborts=new WeakMap();
class Target{
 listeners=new Map();
 addEventListener(type,callback,{signal}={}){if(signal?.aborted)return;if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(callback);if(signal){if(!aborts.has(signal)){const cleanup=[];aborts.set(signal,cleanup);signal.addEventListener('abort',()=>cleanup.forEach(fn=>fn()),{once:true});}aborts.get(signal).push(()=>this.listeners.get(type)?.delete(callback));}}
 dispatchEvent(e){for(const callback of this.listeners.get(e.type)||[])callback(e);this['on'+e.type]?.(e);return true;}
}
class Element extends Target{
 constructor(id=''){super();Object.assign(this,{id,value:'',checked:false,style:{},dataset:{},children:[],clientWidth:1280,clientHeight:720,classList:{add(){},remove(){},toggle(){}}});}
 replaceChildren(...children){this.children=children;}setAttribute(){}getBoundingClientRect(){return {left:0,top:0,width:1280,height:720};}
 get selectedOptions(){return this.children.filter(option=>option.value===this.value);}matches(){return false;}click(){this.dispatchEvent(new Event('click'));}focus(){}setPointerCapture(){}releasePointerCapture(){}
}
const ids=[...fs.readFileSync(path.join(root,'index.html'),'utf8').matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);ids.push('fire-light','fire-light-value');
const elements=new Map(ids.map(id=>['#'+id,new Element(id)]));for(const name of['main','.stamp strong','.fire-light-control small'])elements.set(name,new Element(name));
const document=new Target();document.hidden=false;document.querySelector=name=>{if(!elements.has(name))throw Error('Missing markup '+name);return elements.get(name);};
document.querySelector('#fire').getContext=type=>type==='webgl2'?gl:null;
document.createElement=()=>new Element();document.head={append(script){import(script.src).then(()=>script.onload(),()=>script.onerror());}};
const frames=new Map();let frameId=0;const events=new Target(),failures=[];
Object.assign(globalThis,{window:globalThis,document,location:{href:'https://native-fixture.invalid/firesim/?room='+option('room','1')},HTMLElement:Element,
 Option:class extends Element{constructor(name,value){super();this.textContent=name;this.value=value;}},performance:{now:()=>clock},
 requestAnimationFrame:fn=>{frames.set(++frameId,fn);return frameId;},cancelAnimationFrame:id=>frames.delete(id),addEventListener:(...args)=>events.addEventListener(...args),
 SceneLights:{active:false,revision:0,bind(){}},createImageBitmap:async()=>({width:1,height:1,close(){}}),
 fetch:async value=>{const filename=fileURLToPath(new URL(String(value),pathToFileURL(root+'/')));const relative=path.relative(root,filename);if(relative.startsWith('..'))throw Error('Fetch escaped runtime');const bytes=fs.readFileSync(filename);return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),json:async()=>JSON.parse(bytes),blob:async()=>bytes};}});
const load=file=>import(pathToFileURL(path.join(root,file)).href);
const {createFireDomain}=await load('fire-domain.js'),{LEGACY_PRESETS}=await load('pyro-gpu/presets.js'),{POWER_DEFINITIONS}=await load('fire-powers.js'),{loadRuntime}=await load('runtime-loader.js');
elements.get('#preset').replaceChildren(...LEGACY_PRESETS.map(p=>new Option(p.name,p.id.replace(/^legacy:/,''))));
let mount=await loadRuntime('legacy');
const sourceSamples=Number(option('diagnostic-source-samples','1'));if(![1,2,3].includes(sourceSamples))throw Error('Diagnostic source samples must be1,2 or3');
if(sourceSamples>1){
 const factory=window.createFireEmitters;
 const line='vec4 release=powerCastSource(kindScale.x,world,originAge.xyz,kindScale.y,originAge.w,clock+kindScale.w*11.37,directionStrength.xyz,directionStrength.w,targetCharge.xyz,targetCharge.w);';
 window.createFireEmitters=(...args)=>{
  const glsl=factory(...args);if(!glsl.includes(line))throw Error('Unexpected production power source integration schema');
  return glsl.replace(line,`vec4 release=vec4(0);vec3 momentum=vec3(0);
        for(int temporal=0;temporal<${sourceSamples};temporal++){
          float previous=delta*(float(temporal)+.5)/${sourceSamples}.;
          vec4 packet=powerCastSource(kindScale.x,world,originAge.xyz,kindScale.y,originAge.w-previous,clock+kindScale.w*11.37-previous,directionStrength.xyz,directionStrength.w,targetCharge.xyz,targetCharge.w);
          release.w+=packet.w;momentum+=packet.xyz*packet.w;
        }
        release.xyz=momentum/max(release.w,.00001);release.w/=${sourceSamples}.;`);
 };
}
const stepHz=Number(option('diagnostic-step-hz','30'));if(![30,60].includes(stepHz))throw Error('Diagnostic host step must be30 or60Hz');
const spatialAir=option('diagnostic-spatial-air','0')==='1';
let diagnosticHostHash=null;
if(stepHz!==30||spatialAir){
 const original=fs.readFileSync(path.join(root,'fire.js'),'utf8');
 if(!original.includes('const STEP = 1 / 30, DURATION = 9.8;'))throw Error('Unexpected production host timestep schema');
 let patched=original.replace('const STEP = 1 / 30, DURATION = 9.8;',`const STEP = 1 / ${stepHz}, DURATION = 9.8;`);
 if(spatialAir){
  if(!patched.includes('if(emitterKind!=6)oxygen=mix(oxygen,1.0,'))throw Error('Unexpected production oxygen mixing schema');
  patched=patched.replace('if(emitterKind!=6)oxygen=mix(oxygen,1.0,','if(emitterKind!=6&&!(emitterKind>=22&&emitterKind<=${MAX_POWER_EMITTER}))oxygen=mix(oxygen,1.0,');
 }
 patched=patched.replace(/from\s*(['"])(\.[^'"]+)\1/g,(match,quote,specifier)=>'from '+quote+new URL(specifier,pathToFileURL(path.join(root,'fire.js'))).href+quote);
 diagnosticHostHash=createHash('sha256').update(patched).digest('hex');
 mount=(await import('data:text/javascript;base64,'+Buffer.from(patched).toString('base64'))).mountLegacy;
}
const requested=option('powers','radial-blast,fireball,fire-rain,fire-tornado,floor-trail,combustion-bomb'),selected=requested==='all'?POWER_DEFINITIONS.map(power=>power.id):requested.split(',');
for(const id of selected)if(!POWER_DEFINITIONS.some(power=>power.id===id))throw Error('Unknown power '+id);
const checkpoints=option('times','.10,.30,.60,1.0,1.3,1.6,2.2,3.0').split(',').map(Number);
const scenario=option('scenario','single');if(!['single','overlap','charge'].includes(scenario))throw Error('Unknown capture scenario '+scenario);
const sourceFiles=['fire.js','fire-emitters.js','fire-optics.js','fire-room.js','fire-powers.js','fire-power-definitions.js','fire-abilities.js','fire-ability-motions.js','coarse-pressure.js','corrected-advection.js','pyro-gpu/presets.js'];
const sourceHashes=Object.fromEntries(sourceFiles.map(file=>[file,createHash('sha256').update(fs.readFileSync(path.join(root,file))).digest('hex')]));
const report={runtimeRoot:root,scenario,sourceHashes,diagnosticHostHash,diagnosticSpatialAir:spatialAir,simulationHz:stepHz,diagnosticSourceSamples:sourceSamples,scope:`Actual production host GL replay; same simulation grids, ${stepHz}Hz host step${stepHz===30?'':' (explicit diagnostic override)'}, ${sourceSamples} source samples${sourceSamples===1?'':' (explicit diagnostic override)'}, actual gas/pressure/vorticity/light/projection/presentation. Browser pacing not measured.`,cases:[]};
for(const id of selected){
 const definition=POWER_DEFINITIONS.find(power=>power.id===id);if(scenario==='charge'&&!definition.hold)throw Error(id+' does not support a held charge');
 const trace=path.join(out,id+'.ndjson');if(fs.existsSync(trace))throw Error('Preserve previous captures; choose a new --out directory.');sink=fs.openSync(trace,'w');commands=0;draws=0;
 window.FireDomain=createFireDomain(id);window.FireOptics=window.createFireOptics();window.createFireRoom();
 const runtime=await mount({initialPreset:id,initialPowers:{strength:1,heading:Number(option('heading',String(definition.defaultHeading??0))),elevation:14},onRemount:key=>{throw Error('Unexpected remount '+key);},onFailure:e=>failures.push(String(e))});
 const requestedFuel=option('fuel','preset'),look={room:option('room','1')==='1',camera:{zoom:Number(option('zoom','1.4')),angle:Number(option('angle','16')),pan:[0,0]},color:'natural'};
 if(requestedFuel!=='preset')look.fuel=requestedFuel;
 runtime.look(look);
 const controls=runtime.snapshot(),captureTimes=[];const steps=Math.ceil(Math.max(...checkpoints)*30);let checkpoint=0;
 const view=elements.get('#view');
 const pointer=(type,x,z)=>{const c=runtime.snapshot().camera,yaw=c.angle*Math.PI/180,eye=[Math.sin(yaw)*13,3.5,Math.cos(yaw)*13],length=Math.hypot(13,1.1),forward=[-Math.sin(yaw)*13/length,-1.1/length,-Math.cos(yaw)*13/length],right=[Math.cos(yaw),0,-Math.sin(yaw)],up=[-Math.sin(yaw)*1.1/length,13/length,-Math.cos(yaw)*1.1/length],offset=[x-eye[0],.018-eye[1],z-eye[2]],dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0),depth=dot(offset,forward),tan=.3443276133/c.zoom;
  view.dispatchEvent({type,pointerId:7,pointerType:'mouse',button:0,buttons:1,clientX:(.5+.5*dot(offset,right)/(depth*tan*16/9))*1280,clientY:(.5-.5*dot(offset,up)/(depth*tan))*720,preventDefault(){}});};
 if(id==='floor-trail')pointer('pointerdown',-2,0);
 const aimPointer=(type,x,y)=>view.dispatchEvent({type,pointerId:9,pointerType:'mouse',button:0,buttons:1,clientX:x,clientY:y,preventDefault(){}});
 if(scenario==='charge')aimPointer('pointerdown',580,350);
 for(let step=1;step<=steps;step++){
  if(id==='floor-trail'&&step<=36)pointer('pointermove',-2+step/9,.30*Math.sin(step*.20));
  if(id==='floor-trail'&&step===37)pointer('pointerup',2,.30*Math.sin(36*.20));
  if(scenario==='overlap'&&!definition.continuous&&[10,21,29].includes(step)){
   runtime.look({powers:{heading:step===10?-25:step===21?25:0,elevation:step===29?22:14}});runtime.castPower();
  }
  if(scenario==='charge'&&step<40)aimPointer('pointermove',580+step*5,350-step*2);
  if(scenario==='charge'&&step===40)aimPointer('pointerup',780,270);
  clock+=1000/30+.001;const entry=frames.entries().next().value;if(!entry)throw Error('Runtime lost frame ownership');frames.delete(entry[0]);entry[1](clock);await new Promise(ok=>setImmediate(ok));
  if(failures.length)throw Error(failures.join('; '));
  while(checkpoint<checkpoints.length&&step/30+1e-6>=checkpoints[checkpoint]){const t=step/30;record('$capture',[{preset:id,time:t,file:id+'-'+t.toFixed(2)+'.png',ability:runtime.abilityState?.()||runtime.snapshot().ability}]);captureTimes.push(t);checkpoint++;}
  record('$frame',[step/30]);
 }
 const lastSnapshot=runtime.snapshot();record('$end',[]);fs.closeSync(sink);sink=null;
 // Dispose recordings are not replayed: they do not change the captured image.
 sink=fs.openSync(path.join(out,'dispose.ndjson'),'a');await runtime.dispose();fs.closeSync(sink);sink=null;
 report.cases.push({id,trace:path.basename(trace),domain:window.FireDomain,controls,captureTimes,lastSnapshot,commands,draws});
}
fs.writeFileSync(path.join(out,'capture-manifest.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify({manifest:path.join(out,'capture-manifest.json'),cases:report.cases.length,commands:report.cases.reduce((n,c)=>n+c.commands,0),draws:report.cases.reduce((n,c)=>n+c.draws,0)}));
