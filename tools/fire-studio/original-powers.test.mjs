/** Execute actual Original power startup and controls with recording GPU/DOM
 * fixtures. Native GLSL and gas-field gates are separate; no browser FPS claim. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import {resolve,relative,isAbsolute} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const root=resolve(process.env.FIRE_STUDIO_ROOT||fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url)));
const moduleURL=file=>pathToFileURL(resolve(root,file)).href;
const abortRegistrations=new WeakMap();
class Target{
 listeners=new Map();
 addEventListener(type,callback,{signal}={}){
  if(signal?.aborted)return;if(!this.listeners.has(type))this.listeners.set(type,new Set());this.listeners.get(type).add(callback);
  if(signal){if(!abortRegistrations.has(signal)){const cleanups=[];abortRegistrations.set(signal,cleanups);signal.addEventListener('abort',()=>cleanups.forEach(fn=>fn()),{once:true});}abortRegistrations.get(signal).push(()=>this.listeners.get(type)?.delete(callback));}
 }
 dispatchEvent(event){for(const callback of this.listeners.get(event.type)||[])callback(event);this['on'+event.type]?.(event);return !event.defaultPrevented;}
 get listenerCount(){return [...this.listeners.values()].reduce((sum,items)=>sum+items.size,0);}
}
class Element extends Target{
 constructor(id=''){super();Object.assign(this,{id,value:'',checked:false,disabled:false,style:{},dataset:{},attributes:new Map(),children:[],clientWidth:1280,clientHeight:720});const classes=new Set();this.classList={add:name=>classes.add(name),remove:name=>classes.delete(name),toggle:(name,force)=>force?classes.add(name):classes.delete(name)};}
 replaceChildren(...children){this.children=children;}setAttribute(name,value){this.attributes.set(name,String(value));}
 getBoundingClientRect(){return {x:0,y:0,left:0,top:0,width:this.clientWidth,height:this.clientHeight};}
 get selectedOptions(){return this.children.filter(option=>option.value===this.value);}
 matches(){return false;}click(){this.dispatchEvent(new Event('click'));}focus(){}setPointerCapture(id){this.pointerCapture=id;}releasePointerCapture(){this.pointerCapture=null;}
}
function fixture(params=''){
 const gl={},constants='CLAMP_TO_EDGE COLOR COLOR_ATTACHMENT0 COLOR_ATTACHMENT1 COMPILE_STATUS FLOAT FRAGMENT_SHADER FRAMEBUFFER FRAMEBUFFER_COMPLETE HALF_FLOAT LINEAR LINEAR_MIPMAP_LINEAR LINK_STATUS MAX_TEXTURE_SIZE NEAREST R16F R32F R8 RED REPEAT RGBA RGBA16F RGBA32F RGBA8 SRGB8_ALPHA8 TEXTURE_2D TEXTURE_3D TEXTURE_MAG_FILTER TEXTURE_MIN_FILTER TEXTURE_WRAP_R TEXTURE_WRAP_S TEXTURE_WRAP_T TEXTURE0 TEXTURE1 TEXTURE2 TEXTURE3 TEXTURE5 TEXTURE7 TEXTURE8 TEXTURE14 TEXTURE15 TRIANGLES UNPACK_ALIGNMENT UNSIGNED_BYTE VERTEX_SHADER ARRAY_BUFFER ELEMENT_ARRAY_BUFFER STATIC_DRAW UNSIGNED_INT DEPTH DEPTH_COMPONENT24 DEPTH_ATTACHMENT RENDERBUFFER DEPTH_TEST LESS POINTS';constants.split(' ').forEach((name,i)=>gl[name]=i+1);
 let serial=0,boundFramebuffer=null,currentProgram=null;const textures=[],programs=[],bound=new Map(),calls={draws:0,uniforms:[],lost:0};
 for(const name of['createFramebuffer','createVertexArray','createBuffer','createRenderbuffer'])gl[name]=()=>({kind:name,id:++serial});
 gl.createProgram=()=>{const p={id:++serial,shaders:[]};programs.push(p);return p;};gl.attachShader=(p,s)=>p.shaders.push(s);
 gl.createShader=type=>({type,id:++serial});gl.shaderSource=(s,source)=>s.source=source;
 gl.createTexture=()=>{const t={id:++serial,parameters:new Map()};textures.push(t);return t;};gl.bindTexture=(type,t)=>bound.set(type,t);
 gl.texParameteri=(type,p,v)=>bound.get(type)?.parameters.set(p,v);
 gl.texImage2D=(type,level,internal,width,height,border,format,dataType,data)=>Object.assign(bound.get(type),{internal,width,height,bytes:data?.byteLength});
 gl.texImage3D=(type,level,internal,width,height,depth,border,format,dataType,data)=>Object.assign(bound.get(type),{internal,width,height,depth,bytes:data?.byteLength});
 gl.bindFramebuffer=(target,fbo)=>{boundFramebuffer=fbo;};gl.framebufferTexture2D=(target,attachment,type,t)=>{if(boundFramebuffer){boundFramebuffer.attachments??=new Map();boundFramebuffer.attachments.set(attachment,t);}};
 gl.getExtension=name=>name==='WEBGL_lose_context'?{loseContext(){calls.lost++;}}:['EXT_color_buffer_float','OES_texture_float_linear'].includes(name)?{}:null;
 gl.getParameter=p=>p===gl.MAX_TEXTURE_SIZE?16384:0;gl.checkFramebufferStatus=()=>gl.FRAMEBUFFER_COMPLETE;
 gl.getShaderParameter=gl.getProgramParameter=()=>true;gl.getShaderInfoLog=gl.getProgramInfoLog=()=>'';gl.getUniformLocation=(p,name)=>({p,name});gl.useProgram=p=>{currentProgram=p;};
 for(const method of['uniform1f','uniform1i','uniform2f','uniform3f','uniform3fv','uniform4fv','uniform4i'])gl[method]=(location,...values)=>calls.uniforms.push({name:location?.name,values:values.map(value=>ArrayBuffer.isView(value)?Array.from(value):value)});
 gl.drawArrays=()=>{calls.draws++;const fragment=currentProgram?.shaders?.find(s=>s.type===gl.FRAGMENT_SHADER)?.source||'';if(fragment.includes('out vec4 nextStock;'))calls.woodSteps=(calls.woodSteps||0)+1;};
  for(const name of'activeTexture bindVertexArray compileShader deleteFramebuffer deleteProgram deleteShader deleteTexture deleteVertexArray drawBuffers generateMipmap linkProgram pixelStorei viewport bindRenderbuffer renderbufferStorage framebufferRenderbuffer bindBuffer bufferData enableVertexAttribArray vertexAttribPointer vertexAttribIPointer deleteBuffer deleteRenderbuffer enable disable depthFunc drawElements clearBufferfv texSubImage2D'.split(' '))gl[name]=()=>{};
  gl.texSubImage2D=(type,level,x,y,width,height,format,dataType,data)=>{if(format===gl.RED&&dataType===gl.HALF_FLOAT){calls.fuelUploads=(calls.fuelUploads||0)+1;(calls.fuelFootprints??=[]).push(data.reduce((sum,v)=>sum+(v>0?1:0),0));(calls.fuelPacketPeaks??=[]).push(data.reduce((peak,v)=>Math.max(peak,v),0));}};
 const ids=[...readFileSync(resolve(root,'index.html'),'utf8').matchAll(/\bid="([^"]+)"/g)].map(match=>match[1]);ids.push('fire-light','fire-light-value');
 const elements=new Map(ids.map(id=>['#'+id,new Element(id)]));for(const selector of['main','.stamp strong','.fire-light-control small'])elements.set(selector,new Element(selector));
 const document=new Target();document.hidden=false;document.querySelector=selector=>{assert.ok(elements.has(selector),'Missing fixture markup '+selector);return elements.get(selector);};document.querySelector('#fire').getContext=type=>type==='webgl2'?gl:null;document.querySelector('#fuel').value='gas';
 document.createElement=tag=>{assert.equal(tag,'script');return new Element();};document.head={append(script){const filename=fileURLToPath(new URL(script.src)),child=relative(root,filename);assert.ok(!child.startsWith('..')&&!isAbsolute(child));import(script.src).then(()=>script.onload(),()=>script.onerror());}};
 const events=new Target(),frames=new Map(),requested=[],failures=[];let frameId=0;
 Object.assign(globalThis,{document,location:{href:'https://fixture.invalid/firesim/?room=1&fuel=gas&'+params},HTMLElement:Element,Option:class extends Element{constructor(name,value){super();this.textContent=name;this.value=value;}},requestAnimationFrame:callback=>{const id=++frameId;frames.set(id,callback);return id;},cancelAnimationFrame:id=>frames.delete(id),addEventListener:(...args)=>events.addEventListener(...args),SceneLights:{active:false,revision:0,bind(){}},createImageBitmap:async()=>({width:1,height:1,close(){}}),fetch:async value=>{const file=resolve(root,String(value).split('?')[0]),child=relative(root,file);assert.ok(!child.startsWith('..')&&!isAbsolute(child));const bytes=await new Promise((ok,no)=>readFile(file,(error,data)=>error?no(error):ok(data)));requested.push(child.replaceAll('\\','/'));return {ok:true,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength),json:async()=>JSON.parse(bytes),blob:async()=>bytes};}});
 return {gl,calls,textures,programs,elements,frames,requested,failures,async frame(now){assert.equal(frames.size,1);const [id,callback]=frames.entries().next().value;frames.delete(id);callback(now);await new Promise(ok=>setImmediate(ok));assert.deepEqual(failures,[]);},listeners:()=>document.listenerCount+events.listenerCount+[...elements.values()].reduce((sum,e)=>sum+e.listenerCount,0)};
}

test('Original powers production runtime controls and GPU allocation lifetime',async t=>{
 // Classic helper scripts intentionally remain paired with runtime-loader's
 // module cache. Removing them would make another fixture's cached load stale.
 const names=['window','document','location','HTMLElement','Option','requestAnimationFrame','cancelAnimationFrame','addEventListener','fetch','createImageBitmap','SceneLights','FireDomain','FireOptics','WoodMaterialGLSL'];
 const previous=new Map(names.map(name=>[name,Object.getOwnPropertyDescriptor(globalThis,name)]));t.after(()=>{for(const [name,d]of previous)d?Object.defineProperty(globalThis,name,d):delete globalThis[name];});globalThis.window=globalThis;
 const {createFireDomain}=await import(moduleURL('fire-domain.js')),{LEGACY_PRESETS}=await import(moduleURL('pyro-gpu/presets.js')),{loadRuntime}=await import(moduleURL('runtime-loader.js')+'?fixture=powers');
 for(const [index,id]of['radial-blast','fireball','fire-rain','fire-tornado','floor-trail','combustion-bomb'].entries())await t.test(id,async()=>{
  const env=fixture('powerStrength=1.5&powerHeading=30&powerElevation=15'),mount=await loadRuntime('legacy');env.elements.get('#preset').replaceChildren(...LEGACY_PRESETS.map(p=>new Option(p.name,p.id.replace(/^legacy:/,''))));window.FireDomain=createFireDomain(id);window.FireOptics=window.createFireOptics();window.createFireRoom();
  const initialPowers=['fireball','floor-trail'].includes(id)?{strength:1.25,heading:-30,elevation:20}:undefined,initial=initialPowers||{strength:1.5,heading:30,elevation:15};
  const runtime=await mount({initialPreset:id,initialPowers,onRemount:key=>assert.fail('Unexpected remount '+key),onFailure:error=>env.failures.push(String(error))});
  assert.equal(runtime.snapshot().fire,'legacy:'+id);assert.deepEqual(runtime.snapshot().powers,initial,initialPowers?'The saved look overrides URL settings before the first projectile or trail dose':'The first cast consumes the shared URL settings');assert.ok(!env.requested.some(name=>name.includes('/objects/')),'Powers do not load wood geometry');
  const allocations=env.textures.length,programCount=env.programs.length,start=performance.now()+100;for(let frame=0;frame<6;frame++)await env.frame(start+frame*40);
  assert.equal(env.textures.length,allocations,'No per-frame GPU texture allocation');assert.equal(env.programs.length,programCount,'No per-frame shader compile');assert.equal(env.calls.woodSteps||0,0);
  const uniform=name=>env.calls.uniforms.filter(u=>u.name===name).at(-1)?.values;
  assert.equal(uniform('powerStrength')[0],initial.strength,'The first submitted cast uses the supplied scene settings');
  if(id==='floor-trail'){
    assert.equal(env.calls.fuelUploads,1,'A stationary floor source deposits only its single finite cast dose');
    const half=env.calls.fuelPacketPeaks[0],exponent=(half>>10)&31,peak=exponent?2**(exponent-15)*(1+(half&1023)/1024):(half&1023)*2**-24;
    assert.ok(peak>1&&peak<1.1,'The first actual fuel packet uses the saved 125% dose, rather than stale URL or default strength');
  }
  runtime.look({powers:{strength:1.75,heading:90,elevation:30}});await env.frame(start+260);assert.deepEqual(runtime.snapshot().powers,{strength:1.75,heading:90,elevation:30});
  const transient=[0,1,5].includes(index),settings=transient?initial:{strength:1.75,heading:90,elevation:30};
  assert.equal(uniform('powerStrength')[0],settings.strength,transient?'Strength remains fixed for the cast in flight':'Continuous source strength updates live');const direction=uniform('powerDirection'),h=settings.heading*Math.PI/180,e=settings.elevation*Math.PI/180;assert.ok(Math.abs(direction[0]-Math.cos(h)*Math.cos(e))<1e-6&&Math.abs(direction[1]-Math.sin(e))<1e-6&&Math.abs(direction[2]-Math.sin(h)*Math.cos(e))<1e-6,transient?'An airborne cast cannot teleport when the next aim changes':'Continuous source direction updates live');
  assert.equal(env.calls.uniforms.filter(u=>u.name==='emitterKind').at(-1).values[0],22+index);assert.equal(env.elements.get('#burst').hidden,false,'Every power exposes an explicit cast control');
  env.elements.get('#extinguish').click();await env.frame(start+300);assert.equal(env.calls.uniforms.filter(u=>u.name==='brushActive').at(-1).values[0],0);
  env.elements.get('#burst').click();await env.frame(start+340);assert.equal(env.calls.uniforms.filter(u=>u.name==='brushActive').at(-1).values[0],1,'Recasting restores finite or sustained emission');
  assert.ok(uniform('burstAge')[0]<.08,'Recast resets the simulation-age release window without clearing live gas');
  assert.equal(uniform('powerStrength')[0],1.75);assert.ok(Math.abs(uniform('powerDirection')[1]-.5)<1e-6,'The next cast consumes the edited launch settings');
  const view=env.elements.get('#view'),event=(type,clientX,clientY)=>({type,pointerId:7,pointerType:'mouse',button:0,buttons:1,clientX,clientY,preventDefault(){}});
  if(id==='fireball'){
    view.dispatchEvent(event('pointerdown',640,360));await env.frame(start+380);const origin=uniform('brushTo');
    view.dispatchEvent(event('pointermove',900,250));view.dispatchEvent(event('pointerup',900,250));await env.frame(start+420);
    assert.deepEqual(uniform('brushTo'),origin,'Holding or releasing a projectile cannot relocate its launch origin');
  }
  if(id==='floor-trail'){
    const camera=runtime.snapshot().camera,yaw=camera.angle*Math.PI/180,eye=[camera.pan[0]+Math.sin(yaw)*13,3.5+camera.pan[1],Math.cos(yaw)*13],length=Math.hypot(13,1.1),forward=[-Math.sin(yaw)*13/length,-1.1/length,-Math.cos(yaw)*13/length],right=[Math.cos(yaw),0,-Math.sin(yaw)],up=[right[1]*forward[2]-right[2]*forward[1],right[2]*forward[0]-right[0]*forward[2],right[0]*forward[1]-right[1]*forward[0]],dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
    const floor=(type,x,z)=>{const offset=[x-eye[0],.018-eye[1],z-eye[2]],depth=dot(offset,forward),tan=.3443276133/camera.zoom;return event(type,(.5+.5*dot(offset,right)/(depth*tan*16/9))*1280,(.5-.5*dot(offset,up)/(depth*tan))*720);};
    view.dispatchEvent(floor('pointerdown',-1,0));await env.frame(start+380);const first=env.calls.fuelFootprints.at(-1);
    view.dispatchEvent(event('pointermove',640,0));view.dispatchEvent(floor('pointermove',1,0));await env.frame(start+420);
    assert.ok(env.calls.fuelFootprints.at(-1)<first*1.8,'Re-entering after an invalid floor pick adds a local dose instead of bridging the unseen path');
    const uploads=env.calls.fuelUploads;view.dispatchEvent(floor('pointermove',1,0));view.dispatchEvent(floor('pointerup',1,0));await env.frame(start+460);assert.equal(env.calls.fuelUploads,uploads,'Stationary held motion and release do not refill trail inventory');
  }
  env.elements.get('#pause').click();const before=env.calls.draws;await env.frame(start+520);assert.equal(env.calls.draws,before,'Pause retains the live gas without advancing a power clock');
  if(process.env.FIRE_STUDIO_SHADER_OUTPUT){const dir=resolve(process.env.FIRE_STUDIO_SHADER_OUTPUT);mkdirSync(dir,{recursive:true});writeFileSync(resolve(dir,'startup-'+id+'.json'),JSON.stringify({preset:id,runtimeRoot:root,domain:window.FireDomain,programs:env.programs.map(p=>({id:p.id,vertex:p.shaders.find(s=>s.type===env.gl.VERTEX_SHADER)?.source,fragment:p.shaders.find(s=>s.type===env.gl.FRAGMENT_SHADER)?.source}))}));}
  await runtime.dispose();assert.equal(env.frames.size,0);assert.equal(env.listeners(),0);assert.equal(env.calls.lost,1);
 });
});
