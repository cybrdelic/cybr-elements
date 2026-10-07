/**
 * Execute the production Original runtime and its actual helper scripts through
 * startup, its first frame, visibility changes, and disposal. The DOM and WebGL
 * fixtures record calls; they do not compile shaders or validate rendered pixels.
 * Native shader/render checks remain separate. No browser automation is used.
 *
 * node tools/fire-studio/original-startup.test.mjs
 * FIRE_STUDIO_ROOT may point at a packaged runtime directory to check that build.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readFileSync,mkdirSync,writeFileSync } from 'node:fs';
import { resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const sourceRoot = fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/', import.meta.url));
const root = resolve(process.env.FIRE_STUDIO_ROOT || sourceRoot);
const moduleURL = file => pathToFileURL(resolve(root, file)).href;

// Keep signal handling faithful without attaching one native AbortSignal listener
// for every fixture element. One handler removes all listeners owned by a scope.
const abortRegistrations = new WeakMap();
class FixtureTarget {
  listeners = new Map();
  addEventListener(type, callback, { signal } = {}) {
    if (signal?.aborted) return;
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(callback);
    if (signal) {
      if (!abortRegistrations.has(signal)) {
        const cleanups = [];
        abortRegistrations.set(signal, cleanups);
        signal.addEventListener('abort', () => cleanups.forEach(cleanup => cleanup()), { once: true });
      }
      abortRegistrations.get(signal).push(() => this.listeners.get(type)?.delete(callback));
    }
  }
  dispatchEvent(event) {
    for (const callback of this.listeners.get(event.type) || []) callback(event);
    this['on' + event.type]?.(event);
    return !event.defaultPrevented;
  }
  get listenerCount() { return [...this.listeners.values()].reduce((sum, listeners) => sum + listeners.size, 0); }
}
class FixtureElement extends FixtureTarget {
  constructor(id = '') {
    super();
    this.id = id;
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.style = {};
    this.dataset = {};
    this.attributes = new Map();
    const classes = new Set();
    this.classList = { add: name => classes.add(name), remove: name => classes.delete(name), toggle: (name, force) => force ? classes.add(name) : classes.delete(name) };
    this.children = [];
    this.clientWidth = 1280;
    this.clientHeight = 720;
  }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getBoundingClientRect() { return { x: 0, y: 0, left: 0, top: 0, width: this.clientWidth, height: this.clientHeight }; }
  get selectedOptions() { return this.children.filter(option => option.value === this.value); }
  matches() { return false; }
  click() { this.dispatchEvent(new Event('click')); }
  focus() {}
  setPointerCapture(id) { this.pointerCapture=id; }
  releasePointerCapture() { this.pointerCapture=null; }
}

function recordingGL(floatLinear=true,colorBufferFloat=true) {
  const gl = {};
  const constants = 'CLAMP_TO_EDGE COLOR COLOR_ATTACHMENT0 COLOR_ATTACHMENT1 COMPILE_STATUS FLOAT FRAGMENT_SHADER FRAMEBUFFER FRAMEBUFFER_COMPLETE HALF_FLOAT LINEAR LINEAR_MIPMAP_LINEAR LINK_STATUS MAX_TEXTURE_SIZE NEAREST R16F R32F RG32F RG R8 RED REPEAT RGBA RGBA16F RGBA32F RGBA8 SRGB8_ALPHA8 TEXTURE_2D TEXTURE_3D TEXTURE_MAG_FILTER TEXTURE_MIN_FILTER TEXTURE_WRAP_R TEXTURE_WRAP_S TEXTURE_WRAP_T TEXTURE0 TEXTURE1 TEXTURE2 TEXTURE3 TEXTURE5 TEXTURE7 TEXTURE8 TEXTURE14 TEXTURE15 TRIANGLES UNPACK_ALIGNMENT UNSIGNED_BYTE VERTEX_SHADER ARRAY_BUFFER ELEMENT_ARRAY_BUFFER STATIC_DRAW UNSIGNED_INT DEPTH DEPTH_COMPONENT24 DEPTH_ATTACHMENT RENDERBUFFER DEPTH_TEST LESS POINTS';
  constants.split(' ').forEach((name, index) => gl[name] = index + 1);
  gl.SYNC_GPU_COMMANDS_COMPLETE=10001;gl.TIMEOUT_EXPIRED=10002;gl.WAIT_FAILED=10003;gl.ALREADY_SIGNALED=10004;
  gl.fenceSync=()=>({});gl.clientWaitSync=()=>gl.ALREADY_SIGNALED;gl.deleteSync=()=>{};gl.flush=()=>{};
  let serial = 0;
  const textures = [], shaders = [],programs=[];
  const bound = new Map();
  let boundFramebuffer=null,currentProgram=null;
  const calls = { draws: 0, clears:0, clearedTextures:[], lost: 0, extensions: [] };
  for (const name of ['createFramebuffer', 'createVertexArray','createBuffer','createRenderbuffer']) gl[name] = () => ({ kind: name, id: ++serial });
  gl.createProgram=()=>{const p={kind:'createProgram',id:++serial,shaders:[]};programs.push(p);return p;};
  gl.attachShader=(p,s)=>p.shaders.push(s);
  gl.bindFramebuffer=(target,fbo)=>{boundFramebuffer=fbo;};
  gl.framebufferTexture2D=(target,attachment,type,texture)=>{if(boundFramebuffer){boundFramebuffer.attachments??=new Map();boundFramebuffer.attachments.set(attachment,texture);}};
  gl.createShader = type => { const shader = { type, id: ++serial }; shaders.push(shader); return shader; };
  gl.shaderSource = (shader, source) => shader.source = source;
  gl.createTexture = () => { const texture = { id: ++serial, parameters: new Map() }; textures.push(texture); return texture; };
  gl.bindTexture = (type, texture) => bound.set(type, texture);
  gl.texParameteri = (type, parameter, value) => bound.get(type)?.parameters.set(parameter, value);
  gl.texImage2D = (type, level, internal, width, height, border, format, dataType, data) => Object.assign(bound.get(type), { internal, width, height, bytes: data?.byteLength });
  gl.texImage3D = (type, level, internal, width, height, depth, border, format, dataType, data) => Object.assign(bound.get(type), { internal, width, height, depth, bytes: data?.byteLength });
  gl.texSubImage2D = (type, level, x, y, width, height, format, dataType, data) => {if(format===gl.RED&&dataType===gl.HALF_FLOAT)calls.fuelUploads=(calls.fuelUploads||0)+1;Object.assign(bound.get(type),{uploadBytes:data.byteLength});};
  gl.getExtension = name => {
    calls.extensions.push(name);
    if (name === 'WEBGL_lose_context') return { loseContext() { calls.lost++; } };
    if ((name === 'EXT_color_buffer_float'&&colorBufferFloat) || (name === 'OES_texture_float_linear'&&floatLinear)) return {};
    return null;
  };
  gl.getParameter = parameter => parameter === gl.MAX_TEXTURE_SIZE ? 16384 : 0;
  gl.checkFramebufferStatus = () => gl.FRAMEBUFFER_COMPLETE;
  gl.getShaderParameter = gl.getProgramParameter = () => true;
  gl.getShaderInfoLog = gl.getProgramInfoLog = () => '';
  gl.getUniformLocation = (program, name) => ({ program, name });
  gl.useProgram=p=>{currentProgram=p;};
  gl.drawArrays = () => {calls.draws++;const fragment=currentProgram?.shaders?.find(s=>s.type===gl.FRAGMENT_SHADER)?.source||'';if(fragment.includes('out vec4 capacity;'))calls.woodResets=(calls.woodResets||0)+1;if(fragment.includes('out vec4 nextStock;'))calls.woodSteps=(calls.woodSteps||0)+1;if(fragment.includes('uniform float woodDelta;'))calls.woodMechanicsDraws=(calls.woodMechanicsDraws||0)+1;};
  gl.clearBufferfv=(buffer,index)=>{calls.clears++;const texture=boundFramebuffer?.attachments?.get(gl.COLOR_ATTACHMENT0+index);if(texture)calls.clearedTextures.push(texture.id);};
  gl.readBuffer=()=>{};
  // This call-recording fixture does not execute GLSL. Native float readback
  // and projection residuals are validated separately in the browser.
  gl.readPixels=(x,y,width,height,format,type,values)=>values.fill(0);
  gl.uniform1f=(location,value)=>{if(location?.name==='groundIgnition'&&value>.5)calls.ignitionPasses=(calls.ignitionPasses||0)+1;if(location?.name==='groundCombustion')(calls.groundCombustion??=[]).push(value);if(location?.name==='woodTimeScale')(calls.woodTimeScales??=[]).push(value);if(location?.name==='powerFlame')(calls.powerOptics??=[]).push(value);};
  for (const name of 'activeTexture bindVertexArray compileShader deleteFramebuffer deleteProgram deleteShader deleteTexture deleteVertexArray drawBuffers generateMipmap linkProgram pixelStorei uniform1i uniform2f uniform3f uniform3fv uniform4fv uniform4i viewport bindRenderbuffer renderbufferStorage framebufferRenderbuffer bindBuffer bufferData enableVertexAttribArray vertexAttribPointer vertexAttribIPointer deleteBuffer deleteRenderbuffer enable disable depthFunc drawElements'.split(' ')) gl[name] = () => {};
  gl.drawElements=()=>{calls.woodMeshDraws=(calls.woodMeshDraws||0)+1;};
  return { gl, calls, textures, shaders,programs };
}

function fixture(preset, fuel = 'wood', {floatLinear=true,colorBufferFloat=true}={}) {
  const { gl, calls, textures, shaders,programs } = recordingGL(floatLinear,colorBufferFloat);
  const ids = [...readFileSync(resolve(root, 'index.html'), 'utf8').matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  // Fire illumination is inserted by studio.js before runtime mounting.
  ids.push('fire-light', 'fire-light-value');
  const elements = new Map(ids.map(id => ['#' + id, new FixtureElement(id)]));
  for (const selector of ['main', '.stamp strong', '.fire-light-control small']) elements.set(selector, new FixtureElement(selector));
  const document = new FixtureTarget();
  document.hidden = false;
  document.querySelector = selector => {
    assert.ok(elements.has(selector), 'Startup references a fixture element missing from the studio markup: ' + selector);
    return elements.get(selector);
  };
  document.querySelector('#fire').getContext = type => type === 'webgl2' ? gl : null;
  document.querySelector('#fuel').value = fuel;
  const loadedScripts = [];
  document.createElement = tag => { assert.equal(tag, 'script'); return new FixtureElement(); };
  document.head = { append(script) {
    const filename = fileURLToPath(new URL(script.src));
    const child = relative(root, filename);
    assert.ok(!child.startsWith('..') && !isAbsolute(child), 'Runtime loader keeps helper scripts inside its artifact');
    loadedScripts.push(child.replaceAll('\\', '/'));
    import(script.src).then(() => script.onload(), () => script.onerror());
  } };
  const windowEvents = new FixtureTarget();
  const frames = new Map();
  let frameId = 0;
  const requested = [];
  const failures = [];
  Object.assign(globalThis, {
    document,
    location: { href: 'https://fixture.invalid/firesim/?room=1&fuel=' + fuel },
    HTMLElement: FixtureElement,
    Option: class extends FixtureElement { constructor(name, value) { super(); this.textContent = name; this.value = value; } },
    requestAnimationFrame: callback => { const id = ++frameId; frames.set(id, callback); return id; },
    cancelAnimationFrame: id => frames.delete(id),
    addEventListener: (...args) => windowEvents.addEventListener(...args),
    fetch: async value => {
      const filename = resolve(root, String(value).split('?')[0]);
      const child = relative(root, filename);
      assert.ok(!child.startsWith('..') && !isAbsolute(child), 'Startup fetch stays inside its runtime artifact');
      const bytes = await new Promise((resolveBytes, reject) => readFile(filename, (error, data) => error ? reject(error) : resolveBytes(data)));
      requested.push(child.replaceAll('\\', '/'));
      return { ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength),json:async()=>JSON.parse(bytes.toString('utf8')),blob:async()=>bytes };
    },
    createImageBitmap:async()=>({width:1,height:1,close(){}}),
    SceneLights: { active: false, revision: 0, bind() {} },
  });
  return {
    gl, calls, textures, shaders,programs, elements, frames, requested, loadedScripts, failures, document,
    listeners: () => document.listenerCount + windowEvents.listenerCount + [...elements.values()].reduce((sum, element) => sum + element.listenerCount, 0),
    async frame(now) {
      assert.equal(frames.size, 1, 'The runtime owns exactly one pending animation frame');
      const [id, callback] = frames.entries().next().value;
      frames.delete(id);
      callback(now);
      await new Promise(resolveFrame => setImmediate(resolveFrame));
      assert.deepEqual(failures, [], 'First-frame JavaScript completed without errors');
    },
  };
}

test('Original production startup and failure regression', async t => {
  const keys = ['window', 'document', 'location', 'HTMLElement', 'Option', 'requestAnimationFrame', 'cancelAnimationFrame', 'addEventListener', 'fetch', 'SceneLights', 'FireDomain', 'FireOptics', 'createFireOptics', 'createFireRoom', 'FireRoom', 'CoarsePressure', 'OriginalFineFlow', 'MacCormackAdvection', 'FireVorticity', 'SmokeLight', 'FireEmitters', 'FireProps','WoodMaterialGLSL'];
  const previous = new Map(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  t.after(() => { for (const [key, descriptor] of previous) descriptor ? Object.defineProperty(globalThis, key, descriptor) : delete globalThis[key]; });
  globalThis.window = globalThis;
  const { createFireDomain } = await import(moduleURL('fire-domain.js'));
  const { LEGACY_PRESETS } = await import(moduleURL('pyro-gpu/presets.js'));
  const { loadRuntime } = await import(moduleURL('runtime-loader.js'));
  async function prepare(preset, fuel, options) {
    const env = fixture(preset, fuel, options);
    env.mountLegacy = await loadRuntime('legacy');
    env.elements.get('#preset').replaceChildren(...LEGACY_PRESETS.map(preset => new Option(preset.name, preset.id.replace(/^legacy:/,''))));
    window.FireDomain = createFireDomain(preset);
    window.FireOptics = window.createFireOptics();
    window.createFireRoom();
    return env;
  }

  for (const preset of ['sigil', 'bonfire', 'explosion', 'burning-house','cybr-tree']) await t.test(preset + ' executes startup, first frame and disposal', async () => {
    const env = await prepare(preset, preset === 'explosion' ? 'oil' : 'wood');
    const runtime = await env.mountLegacy({ initialPreset: preset, onRemount: key => assert.fail('Unexpected remount: ' + key), onFailure: error => env.failures.push(String(error)) });
    if(process.env.FIRE_STUDIO_SHADER_OUTPUT){
      const directory=resolve(process.env.FIRE_STUDIO_SHADER_OUTPUT);mkdirSync(directory,{recursive:true});
      writeFileSync(resolve(directory,'startup-'+preset+'.json'),JSON.stringify({preset,runtimeRoot:root,domain:window.FireDomain,programs:env.programs.map(p=>({id:p.id,
        vertex:p.shaders.find(s=>s.type===env.gl.VERTEX_SHADER)?.source,fragment:p.shaders.find(s=>s.type===env.gl.FRAGMENT_SHADER)?.source}))}));
    }
    if (preset === 'sigil') {assert.equal(env.loadedScripts.length, 9, 'Actual runtime loader loaded all nine production helper scripts');assert.ok(env.loadedScripts.some(file=>file.endsWith('original-fine-flow.js')),'Fine flow is loaded through the actual runtime loader');}
    assert.equal(runtime.snapshot().fire, 'legacy:' + preset);
    assert.ok(env.requested.includes('source/source-native.rgba8.bin'));
    assert.ok(env.requested.includes('source/halfwidth-native.r8.bin'));
    if (preset === 'burning-house') assert.ok(env.requested.includes('pyro-gpu/objects/house/solid.rgba16.bin'));
    if(preset==='cybr-tree')for(const name of['bark-color.png','bark-micro.png','bark-roughness.png','structure/vertices.bin','structure/owners.bin'])assert.ok(env.requested.includes('pyro-gpu/objects/forest-tree/'+name),'Reviewed tree asset '+name+' is retained');
    assert.ok(env.shaders.length >= 20, 'Actual helper and runtime constructors assembled their shaders');
    const domain = window.FireDomain;
    const simulationTargets = env.textures.filter(texture => texture.internal === env.gl.RGBA16F && texture.width === domain.nx * 8 && texture.height === domain.ny * domain.depth / 8);
    assert.ok(simulationTargets.length >= 4, 'Simulation texture pairs were allocated');
    for (const texture of simulationTargets) assert.equal(texture.parameters.get(env.gl.TEXTURE_MIN_FILTER), env.gl.LINEAR, 'Float capability selects linear filtering for simulation targets');
    await env.frame(performance.now() + 40);
    assert.ok(!env.calls.powerOptics,'No source selects a second optical model');
    assert.ok(env.shaders.some(s=>s.source?.includes('pow(max(reaction,0.),.95)*6.5')),'The established ordinary optical curve remains linked');
    if(preset==='explosion')assert.equal(env.calls.woodSteps||0,0,'Gas bursts do not acquire a solid wood inventory');
    else {assert.equal(env.calls.woodResets,1);assert.ok(env.calls.woodSteps>0);}
    assert.ok(env.calls.draws > 0, 'Actual first-frame simulation and rendering submitted draw calls');
    assert.equal(env.frames.size, 1);
    runtime.look({ fuel: 'oil', smoke: true, fireLight: 32, camera: { zoom: 1.4, angle: 12, pan: [.1, .2] } });
    assert.equal(runtime.snapshot().smoke, true);
    assert.equal(runtime.snapshot().fireLight, 32);
    runtime.setVisible(false);
    assert.equal(env.frames.size, 0, 'Hidden runtime cancels animation');
    runtime.setVisible(true);
    assert.equal(env.frames.size, 1, 'Visible runtime restarts one animation');
    await runtime.dispose();
    assert.equal(env.frames.size, 0, 'Disposed runtime cancels animation');
    assert.equal(env.listeners(), 0, 'Disposed runtime aborts scope listeners');
    assert.equal(env.calls.lost, 1, 'Disposed runtime releases the WebGL context');
  });

  for (const source of [
    {id:'free',scale:1.1,effect:-1,emitter:0},
    {id:'sooty-plume',scale:1.1,effect:0,emitter:0},
    {id:'campfire',scale:1,effect:15,emitter:16},
  ]) await t.test(source.id + ' sends the intended Original inlet contract to the production shader',async()=>{
    const env=await prepare(source.id,'oil');
    const uniforms=new Map();
    for(const name of ['uniform1i','uniform1f']){
      const record=env.gl[name];
      env.gl[name]=(location,value)=>{
        if(location?.name)uniforms.set(location.name,value);
        record(location,value);
      };
    }
    const runtime=await env.mountLegacy({initialPreset:source.id,onRemount:key=>assert.fail('Unexpected remount: '+key),onFailure:error=>env.failures.push(String(error))});
    try{
      await env.frame(performance.now()+40);
      assert.equal(uniforms.get('sourceScale'),source.scale,'Free fire and plume share the 1.1 inlet scale; the campfire scale stays independent');
      assert.equal(uniforms.get('sourceEffectKind'),source.effect,'The free-fire sentinel and shared preset effect reach the actual runtime shader');
      assert.equal(uniforms.get('emitterKind'),source.emitter,'Free/plume use the broad inlet while campfire keeps its finite-wood source');
      assert.equal(runtime.snapshot().fire,'legacy:'+source.id);
      assert.ok(env.calls.draws>0,'The production first frame submitted its draws');
    }finally{await runtime.dispose();}
    assert.equal(env.frames.size,0);
    assert.equal(env.listeners(),0);
  });

  await t.test('Finite sigil stock survives the old animation loop and wood time is independent of gas time',async()=>{
    const env=await prepare('sigil','wood');
    const runtime=await env.mountLegacy({initialPreset:'sigil',onFailure:error=>env.failures.push(String(error))});
    runtime.look({woodTimeScale:4});assert.equal(runtime.snapshot().woodTimeScale,4);
    const control=env.elements.get('#wood-speed');control.value=9;control.dispatchEvent(new Event('input'));assert.equal(runtime.snapshot().woodTimeScale,9);
    const start=performance.now();for(let i=1;i<=145;i++)await env.frame(start+i*80);
    assert.equal(env.calls.woodResets,1,'Elapsed artwork duration cannot regenerate virgin wood');
    assert.ok(env.calls.woodTimeScales.every(value=>value===9));
    assert.equal(control.disabled,false);
    await runtime.dispose();assert.equal(env.frames.size,0);assert.equal(env.listeners(),0);
  });

  await t.test('Original fuel tool preserves the running source and clears only finite inventory',async()=>{
    let env=await prepare('torch','gas');
    let runtime=await env.mountLegacy({initialPreset:'torch',onFailure:error=>env.failures.push(String(error))});
    assert.equal(env.elements.get('#fuel-actions').hidden,true,'An unseeded source hides fuel actions before placement');
    assert.equal(env.elements.get('#sigil-guide-control').hidden,true,'Non-sigil presets hide the sigil control');
    env.elements.get('#fuel-tool').click();assert.equal(runtime.snapshot().tool,'fuel');assert.equal(runtime.snapshot().fire,'legacy:torch');
    assert.equal(env.elements.get('#fuel-actions').hidden,false);
    assert.equal(env.elements.get('#ignite-fuel').disabled,true,'Ignition requires placed finite fuel');
    assert.equal(env.elements.get('#fire-tool').attributes.get('aria-pressed'),'false');
    const camera=runtime.snapshot().camera,yaw=camera.angle*Math.PI/180,eye=[camera.pan[0]+Math.sin(yaw)*13,3.5+camera.pan[1],Math.cos(yaw)*13],length=Math.hypot(13,1.1);
    const f=[-Math.sin(yaw)*13/length,-1.1/length,-Math.cos(yaw)*13/length],right=[Math.cos(yaw),0,-Math.sin(yaw)];
    const up=[right[1]*f[2]-right[2]*f[1],right[2]*f[0]-right[0]*f[2],right[0]*f[1]-right[1]*f[0]];
    const d=[-eye[0],.018-eye[1],-eye[2]],dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),depth=dot(d,f);
    const event=(type,clientX,clientY)=>({type,pointerId:7,pointerType:'mouse',button:0,clientX,clientY,preventDefault(){}});
    const tan=.3443276133/camera.zoom,x=(.5+.5*dot(d,right)/(depth*tan*16/9))*1280,y=(.5-.5*dot(d,up)/(depth*tan))*720;
    let view=env.elements.get('#view');view.dispatchEvent(event('pointerdown',x,y));view.dispatchEvent(event('pointerup',x,y));
    await env.frame(performance.now()+80);assert.equal(env.calls.fuelUploads,1,'One bounded R16F packet uploads the click mass');
    assert.equal(env.elements.get('#ignite-fuel').disabled,false);
    assert.equal(runtime.snapshot().fire,'legacy:torch','Dropping fuel does not reset or replace the source');
    assert.equal(env.calls.ignitionPasses||0,0,'Dropping fuel does not inject ignition');
    const inspect=env.elements.get('#smoke-only');inspect.checked=true;inspect.dispatchEvent(new Event('change'));
    assert.equal(runtime.snapshot().smoke,true);assert.equal(env.elements.get('#ignite-fuel').disabled,false,'Hiding visible flame does not disable real combustion ignition');
    env.elements.get('#ignite-fuel').click();await env.frame(performance.now()+120);
    assert.equal(env.calls.ignitionPasses,1,'Explicit ignition adds one thermal pulse');
    await env.frame(performance.now()+160);assert.equal(env.calls.ignitionPasses,1,'The pulse is consumed after one physics step');
    const clears=env.calls.clears;env.elements.get('#clear-fuel').click();assert.equal(env.calls.clears-clears,4,'Only the two finite mass and two wood wear targets clear');
    assert.equal(runtime.snapshot().fire,'legacy:torch');
    view.dispatchEvent(event('pointerdown',x,0));view.dispatchEvent(event('pointerup',x,0));await env.frame(performance.now()+200);
    assert.equal(env.calls.fuelUploads,1,'Invalid floor picks are refused without clamping or uploading');
    runtime.look({sourceGuide:false,tool:'fire'});assert.equal(runtime.snapshot().sourceGuide,false);assert.equal(runtime.snapshot().tool,'fire');
    assert.equal(env.elements.get('#fuel-actions').hidden,true,'Clear inventory and leaving the fuel tool hides the actions');
    await runtime.dispose();assert.equal(env.frames.size,0);assert.equal(env.listeners(),0);
    env=await prepare('sigil','wood');runtime=await env.mountLegacy({initialPreset:'sigil',onFailure:error=>env.failures.push(String(error))});runtime.look({camera,tool:'fuel'});view=env.elements.get('#view');
    assert.equal(env.elements.get('#sigil-guide-control').hidden,false,'Sigil guide remains available after switching source');
    view.dispatchEvent(event('pointerdown',x,y));view.dispatchEvent(event('pointerup',x,y));
    const start=performance.now()+200;
    for(let i=1;i<=156;i++)await env.frame(start+i*80);
    const gasTextureIds=new Set(env.textures.filter(t=>t.internal===env.gl.RGBA16F&&t.width===window.FireDomain.nx*8&&t.height===window.FireDomain.ny*window.FireDomain.depth/8).map(t=>t.id));
    const gasClears=()=>env.calls.clearedTextures.filter(id=>gasTextureIds.has(id)).length;
    const lateClears=env.calls.clears,lateGasClears=gasClears();env.elements.get('#clear-fuel').click();assert.equal(env.calls.clears-lateClears,4);
    await env.frame(start+157*80);assert.equal(gasClears(),lateGasClears,'Clearing fuel after the sigil loop duration must not reset gas');
    await runtime.dispose();assert.equal(env.listeners(),0);assert.equal(env.frames.size,0);
  });

  await t.test('Creating free fire from native sigil stops cached wood mechanics and hides its old mesh',async()=>{
    const env=await prepare('sigil','wood');const runtime=await env.mountLegacy({initialPreset:'sigil',onFailure:error=>env.failures.push(String(error))});
    const start=performance.now()+100;await env.frame(start);assert.ok(env.calls.woodMeshDraws>0);assert.ok(env.calls.woodMechanicsDraws>0);
    const picker=env.elements.get('#preset');picker.replaceChildren(...picker.children.filter(option=>option.value!=='free'));
    const mesh=env.calls.woodMeshDraws,mechanics=env.calls.woodMechanicsDraws,view=env.elements.get('#view');
    const event=type=>({type,pointerId:9,pointerType:'mouse',button:0,clientX:640,clientY:360,preventDefault(){}});
    view.dispatchEvent(event('pointerdown'));view.dispatchEvent(event('pointerup'));await env.frame(start+80);
    assert.equal(runtime.snapshot().fire,'legacy:free');assert.equal(env.calls.woodMeshDraws,mesh,'Previous sigil substrate cannot float around with free fire');assert.equal(env.calls.woodMechanicsDraws,mechanics,'An inactive cached wood graph consumes no per-step work');assert.equal(env.elements.get('#extinguish').textContent,'Stop fuel');
    await runtime.dispose();assert.equal(env.frames.size,0);assert.equal(env.listeners(),0);
  });

  for(const preset of ['smoke-column','smoke-pair','smoke-burst'])await t.test(preset+' keeps fuel cold and disables ignition independently of inspection',async()=>{
    const env=await prepare(preset,'oil');
    const runtime=await env.mountLegacy({initialPreset:preset,onFailure:error=>env.failures.push(String(error))});
    env.elements.get('#fuel-tool').click();
    const camera=runtime.snapshot().camera,yaw=camera.angle*Math.PI/180,eye=[camera.pan[0]+Math.sin(yaw)*13,3.5+camera.pan[1],Math.cos(yaw)*13],length=Math.hypot(13,1.1);
    const forward=[-Math.sin(yaw)*13/length,-1.1/length,-Math.cos(yaw)*13/length],right=[Math.cos(yaw),0,-Math.sin(yaw)],up=[right[1]*forward[2]-right[2]*forward[1],right[2]*forward[0]-right[0]*forward[2],right[0]*forward[1]-right[1]*forward[0]];
    const d=[-eye[0],.018-eye[1],-eye[2]],dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0),depth=dot(d,forward),tan=.3443276133/camera.zoom;
    const clientX=(.5+.5*dot(d,right)/(depth*tan*16/9))*1280,clientY=(.5-.5*dot(d,up)/(depth*tan))*720;
    const view=env.elements.get('#view'),event=type=>({type,pointerId:7,pointerType:'mouse',button:0,clientX,clientY,preventDefault(){}});
    view.dispatchEvent(event('pointerdown'));view.dispatchEvent(event('pointerup'));await env.frame(performance.now()+80);
    assert.equal(env.calls.fuelUploads,1);assert.equal(env.elements.get('#ignite-fuel').disabled,true);
    assert.equal(env.elements.get('#ignite-fuel').title,'Choose a fire source to ignite fuel.');
    runtime.look({smoke:false});env.elements.get('#ignite-fuel').click();await env.frame(performance.now()+120);
    assert.equal(env.elements.get('#message').textContent,'Choose a fire source to ignite fuel.');
    assert.equal(env.calls.ignitionPasses||0,0);assert.ok(env.calls.groundCombustion.length>0);
    assert.ok(env.calls.groundCombustion.every(value=>value===0),'Actual smoke sources cannot consume fuel or release unburnable vapor');
    await runtime.dispose();assert.equal(env.frames.size,0);assert.equal(env.listeners(),0);
  });

  for(const stage of ['fine projection','transport schedule','conservative transport','oxygen predictor'])await t.test(stage+' rejection restores accepted chemistry aliases/clock and leaves auxiliary state unchanged',async()=>{
    const env=await prepare('sigil','wood');let boundFramebuffer;const framebuffers=new Set(),originalBind=env.gl.bindFramebuffer,originalDraw=env.gl.drawArrays,originalBuffers=env.gl.drawBuffers;
    env.gl.bindFramebuffer=(target,fbo)=>{boundFramebuffer=fbo;if(fbo)framebuffers.add(fbo);return originalBind(target,fbo);};
    env.gl.drawBuffers=buffers=>{if(boundFramebuffer)boundFramebuffer.selected=Array.from(buffers);return originalBuffers(buffers);};
    env.gl.drawArrays=(...args)=>{for(const attachment of boundFramebuffer?.selected||[]){const texture=boundFramebuffer.attachments?.get(attachment);if(texture)texture.writes=(texture.writes||0)+1;}return originalDraw(...args);};
    const runtime=await env.mountLegacy({initialPreset:'sigil',onFailure:error=>env.failures.push(String(error))});
    const flowProto=window.OriginalFineFlow.prototype,advectionProto=window.MacCormackAdvection.prototype,originalProject=flowProto.project;let acceptedTime=0,failedInputChem,failedInputVF,capturedFlow;
    flowProto.project=function(vf,chem,coarse,dt){capturedFlow=this;failedInputChem=chem;failedInputVF=vf;const result=originalProject.call(this,vf,chem,coarse,dt);acceptedTime+=dt;return result;};
    const start=performance.now()+80;await env.frame(start);const priorTime=acceptedTime,woodSteps=env.calls.woodSteps,mechanics=env.calls.woodMechanicsDraws;
    capturedFlow.warmPressure=capturedFlow.target(capturedFlow.levels[0],env.gl.R32F);capturedFlow.warmValid=true;capturedFlow.materialLedgerState={valid:true};
    const writes=new Map(env.textures.map(texture=>[texture,texture.writes||0]));
    const domain=window.FireDomain,aliases=new Map([...framebuffers].filter(fbo=>fbo.attachments?.size===2&&fbo.attachments.get(env.gl.COLOR_ATTACHMENT0)?.internal===env.gl.RGBA16F&&fbo.attachments.get(env.gl.COLOR_ATTACHMENT0)?.width===domain.nx*8).map(fbo=>[fbo,fbo.attachments.get(env.gl.COLOR_ATTACHMENT1)]));assert.equal(aliases.size,2);
    const method=stage==='fine projection'?'project':stage==='transport schedule'?'prepareTransport':stage==='conservative transport'?'transport':'step',prototype=stage==='oxygen predictor'?advectionProto:flowProto,saved=prototype[method];
    prototype[method]=function(...args){if(method==='project'){failedInputVF=args[0];failedInputChem=args[1];}throw Error('Injected '+stage+' failure');};
    try{
      await env.frame(start+80);const failure=runtime.snapshot().failure;
      assert.equal(failure.stage,stage);assert.equal(failure.acceptedTime,priorTime);assert(failure.attemptedTime>failure.acceptedTime);assert.equal(env.frames.size,0);assert.equal(env.calls.woodSteps,woodSteps);assert.equal(env.calls.woodMechanicsDraws,mechanics);
      assert.equal(capturedFlow.warmValid,false,'Rejected acceleration history is discarded');assert.equal(capturedFlow.materialLedgerState.valid,false,'Rejected material ledger is unavailable');
      assert.equal(failedInputChem.writes||0,writes.get(failedInputChem));assert.equal(failedInputVF.writes||0,writes.get(failedInputVF));
      for(const [fbo,texture]of aliases)assert.equal(fbo.attachments.get(env.gl.COLOR_ATTACHMENT1),texture,'Diffusion alias swaps must roll back both framebuffer attachments');
      assert.equal(env.elements.get('#pause').disabled,true);assert.equal(env.elements.get('#session-status').dataset.state,'error');assert.match(env.elements.get('#message').textContent,/last accepted state is preserved/);
      env.elements.get('#pause').click();assert.equal(env.frames.size,0,'A rejected state cannot be resumed');
    }finally{prototype[method]=saved;flowProto.project=originalProject;await runtime.dispose();}
    assert.equal(env.listeners(),0);
  });
  await t.test('Core half-float filtering survives absence of the optional 32-bit float extension',async()=>{
    const env=await prepare('sigil','wood',{floatLinear:false});
    assert.equal(env.gl.getExtension('OES_texture_float_linear'),null);
    const runtime=await env.mountLegacy({initialPreset:'sigil',onFailure:error=>env.failures.push(String(error))});
    const domain=window.FireDomain;
    const targets=env.textures.filter(texture=>texture.internal===env.gl.RGBA16F&&texture.width===domain.nx*8&&texture.height===domain.ny*domain.depth/8);
    assert.ok(targets.length>=4);
    for(const texture of targets){
      assert.equal(texture.parameters.get(env.gl.TEXTURE_MIN_FILTER),env.gl.LINEAR);
      assert.equal(texture.parameters.get(env.gl.TEXTURE_MAG_FILTER),env.gl.LINEAR);
    }
    const correction=env.shaders.find(shader=>shader.source?.includes('vec3 value=-grad/WORLD'))?.source;
    assert.ok(correction?.includes('outValue=vec4(value,0.0)'),'Half-float pressure correction retains signed precision without the32F extension');
    assert.ok(env.textures.some(texture=>texture.internal===env.gl.RGBA16F&&texture.width!==domain.nx*8&&texture.parameters.get(env.gl.TEXTURE_MIN_FILTER)===env.gl.LINEAR));
    for(const texture of env.textures.filter(texture=>texture.internal===env.gl.R32F))assert.equal(texture.parameters.get(env.gl.TEXTURE_MIN_FILTER),env.gl.NEAREST,'32F pressure solves do not require linear sampling');
    await env.frame(performance.now()+40);await runtime.dispose();
    assert.equal(env.frames.size,0);assert.equal(env.listeners(),0);
  });

  await t.test('Missing float-target renderability is still rejected before GPU allocations',async()=>{
    const env=await prepare('sigil','wood',{floatLinear:false,colorBufferFloat:false});
    await assert.rejects(()=>env.mountLegacy({initialPreset:'sigil'}),/Floating point GPU targets are unavailable/);
    assert.equal(env.textures.length,0);assert.equal(env.programs.length,0);
    assert.equal(env.frames.size,0);assert.equal(env.listeners(),0);assert.equal(env.calls.lost,1);
  });

  await t.test('Previous v5 Original remains available through the actual loader', async () => {
    const candidateAdvection = window.MacCormackAdvection;
    try {
      const env = fixture('sigil', 'wood');
      location.href += '&runtime=v5';
      const { loadRuntime: loadPrevious } = await import(moduleURL('runtime-loader.js') + '?fixture=v5');
      const mountPrevious = await loadPrevious('legacy');
      assert.ok(env.loadedScripts.some(file => file.endsWith('corrected-advection-v5.js')));
      assert.ok(!env.loadedScripts.some(file => file.endsWith('original-fine-flow.js')));
      env.elements.get('#preset').replaceChildren(...LEGACY_PRESETS.map(preset => new Option(preset.name, preset.id.replace(/^legacy:/, ''))));
      window.FireDomain = createFireDomain('sigil');
      window.FireOptics = window.createFireOptics();
      window.createFireRoom();
      const runtime = await mountPrevious({ initialPreset: 'sigil', onFailure: error => env.failures.push(String(error)) });
      assert.deepEqual(env.failures, []);
      await env.frame(performance.now() + 40);
      await runtime.dispose();
      assert.equal(env.frames.size, 0);
      assert.equal(env.listeners(), 0);
    } finally {
      window.MacCormackAdvection = candidateAdvection;
    }
  });

  await t.test('Removing the half-float filtering declaration reproduces the reported ReferenceError', async () => {
    const original = readFileSync(resolve(root, 'fire.js'), 'utf8');
    const declaration = /const\s+halfFloatLinear\s*=\s*true;/;
    assert.match(original, declaration);
    const broken = original.replace(declaration, '').replace(/from\s*(['"])(\.[^'"]+)\1/g, (match, quote, specifier) => 'from ' + quote + new URL(specifier, moduleURL('fire.js')).href + quote);
    const env = await prepare('sigil', 'wood');
    const { mountLegacy: brokenMount } = await import('data:text/javascript;base64,' + Buffer.from(broken).toString('base64'));
    await assert.rejects(() => brokenMount({ initialPreset: 'sigil' }), error => error instanceof ReferenceError && error.message === 'halfFloatLinear is not defined');
    assert.equal(env.frames.size, 0, 'Failed startup schedules no frames');
    assert.equal(env.listeners(), 0, 'Failed startup aborts its listeners');
    assert.equal(env.calls.lost, 1, 'Failed startup releases the context');
  });
});
