import {advanceSmokeDecay} from './smoke-lifecycle.js?v=studio-rc-37-repair';
import {SimulationClock} from './simulation-clock.js?v=studio-rc-37-repair';
import {createOriginalShaders} from './original-shaders.js?v=studio-rc-38-original-motion';
import {runtimeScope} from './runtime-scope.js?v=studio-rc-37-repair';
import {createGLFrameQueue} from './gl-frame-queue.js?v=studio-rc-37-repair';
import {legacyProbe} from './legacy-qa.js?v=studio-rc-37-repair';
import {FIRE_PRESETS} from './pyro-gpu/presets.js?v=studio-rc-37-repair';
import {FIRE_COLORS} from './pyro-gpu/fire-colors.js?v=studio-rc-37-repair';
import {emitterKindFor} from './original-source-profile.js?v=studio-rc-37-repair';
import {FuelBrush,floorHit} from './fuel-ground.js?v=studio-rc-37-repair';
import {createGroundFuelGL} from './ground-fuel-gl.js?v=studio-rc-37-repair';
import {WOOD_THERMO} from './wood-thermo.js?v=studio-rc-37-repair';
import {createWoodStateGL,originalWoodSource} from './wood-state-gl.js?v=studio-rc-37-repair';
import {createWoodStructureGL,createWoodMeshGL} from './wood-structure-gl.js?v=studio-rc-37-repair';
import {POWER_DEFINITIONS,powerDefinition,powerDirection,normalizePowerSettings} from './fire-powers.js?v=studio-rc-37-repair';
import {PowerCastPool} from './fire-abilities.js?v=studio-rc-37-repair';
import {POWER_CAST_CAPACITY} from './fire-power-definitions.js?v=studio-rc-37-repair';

const MAX_POWER_EMITTER=21+Math.max(...POWER_DEFINITIONS.map(power=>power.kind));
const DIRECTIONAL_GROUND_POWERS=new Set(['flame-dash','eruption-chain','fire-cross']);
export async function mountLegacy({initialPreset='sigil',initialPowers,onRemount,onFailure=()=>{}}={}){
  const scope=runtimeScope(onFailure),on=scope.on;
  const qaParams=new URL(location.href).searchParams,qaCaptureStop=Number(qaParams.get('capture'))||0;
  'use strict';
  // The source texture is static emitter geometry, not footage or baked motion.
  // Every visible frame is generated from the evolving GPU state below.
  const domain=window.FireDomain;
  const initialProfile=FIRE_PRESETS.find(p=>p.id===initialPreset);
  const hasPowers=!!powerDefinition(initialPreset);
  const hasWood=originalWoodSource(initialPreset,initialProfile).kind>0;
  const [WX,WY,WZ]=domain.extent;
  const [MINX,MINY]=domain.minimum;
  const NX=domain.nx, NZ=domain.ny, DEPTH=domain.depth, TILES_X=8, TILES_Y=DEPTH/8;
  const SOURCE_NX = 896, SOURCE_NZ = 504;
  const RW = 896, RH = 504;
  const AW = NX * TILES_X, AH = NZ * TILES_Y;
  const STEP = 1 / 30, DURATION = 9.8;
  let stateRevision=0, roomLightRevision=-1, smokeLightRevision=-1, propLightRevision=-1;
  let lightingRevision=-1;
  let turbulenceTexture;
  let objectTexture,emptyObjectTexture;
  const objectModels=new Map();
  const canvas = document.querySelector('#fire');
  const view = document.querySelector('#view');
  const message = document.querySelector('#message');
  const metrics = document.querySelector('#metrics');
  const help = document.querySelector('#help');
  const restartButton = document.querySelector('#restart');
  const extinguishButton = document.querySelector('#extinguish');
  const roomToggle = document.querySelector('#room');
  const orbitControl = document.querySelector('#orbit');
  const zoomControl = document.querySelector('#zoom');
  const focusButton = document.querySelector('#focus-fire');
  const fullscreenButton = document.querySelector('#fullscreen');
  const smokeControl = document.querySelector('#smoke-only');
  const colorControl = document.querySelector('#flame-color');
  const fireLightControl = document.querySelector('#fire-light');
  const benchmarkButton = document.querySelector('#benchmark');
  const guideControl=document.querySelector('#source-guide'),fuelToolControl=document.querySelector('#fuel-tool'),clearFuelControl=document.querySelector('#clear-fuel');
  let sourceGuide=qaParams.get('guide')!=='0',fuelTool=false,fuelGesture=null,groundFuel,woodState,woodMechanics,woodMesh,manualFuelSession=false;
  const woodSpeedControl=document.querySelector('#wood-speed'),woodSpeedValue=document.querySelector('#wood-speed-value');
  let woodTimeScale=1;
  const setWoodSpeed=value=>{const number=Number(value);woodTimeScale=Number.isFinite(number)?Math.max(1,Math.min(24,number)):1;woodSpeedControl.value=woodTimeScale;woodSpeedValue.value=woodTimeScale+'×';};
  woodSpeedControl.oninput=()=>setWoodSpeed(woodSpeedControl.value);setWoodSpeed(qaParams.get('woodTimeScale')??1);
  const fuelBounds={minX:MINX,maxX:MINX+WX,minZ:domain.minimum[2],maxZ:domain.minimum[2]+WZ};
  const fuelBrush=new FuelBrush(fuelBounds);
  guideControl.checked=sourceGuide;
  guideControl.onchange=()=>{sourceGuide=guideControl.checked;needsDraw=true;};
  let inspectSmoke=false,flameColor='natural',fireLight=24,measurement=null;
  const markAppearance=()=>{roomLightRevision=-1;propLightRevision=-1;needsDraw=true;};
  colorControl.replaceChildren(...FIRE_COLORS.map(c=>new Option(c.name,c.id)));
  colorControl.onchange=()=>{flameColor=colorControl.value;markAppearance();};
  smokeControl.onchange=()=>{inspectSmoke=smokeControl.checked;needsDraw=true;};
  smokeControl.title='Hide visible flame while keeping combustion, smoke and fire illumination running.';
  const setFireLight=value=>{
    fireLight=Math.max(0,Math.min(80,Number(value)||0));
    fireLightControl.value=fireLight;
    document.querySelector('#fire-light-value').value=fireLight.toFixed(0);
    markAppearance();
  };
  fireLightControl.oninput=()=>setFireLight(fireLightControl.value);
  benchmarkButton.onclick=()=>{
    if(paused){document.querySelector('#gpu-status').textContent='Resume the simulation before measuring.';return;}
    measurement={start:performance.now(),last:null,intervals:[],steps:0};
    benchmarkButton.disabled=true;
    document.querySelector('#gpu-status').textContent='Measuring 180 rendered frames…';
  };
  const cancelMeasurement=()=>{
    if(!measurement)return;
    measurement=null;benchmarkButton.disabled=false;
    document.querySelector('#gpu-status').textContent='Measurement stopped while the scene was hidden.';
  };
  on(document,'visibilitychange',()=>{if(document.hidden)cancelMeasurement();});
  let viewZoom=1, panX=0, panY=0, panTool=false, panGesture=null;
  const lensTan=()=>.3443276133/viewZoom;
  let roomEnabled = new URL(location.href).searchParams.get('room') !== '0';
  let viewAngle = Number(new URL(location.href).searchParams.get('angle') ?? 16);
  orbitControl.min=-30;orbitControl.max=30;
  viewAngle = Number.isFinite(viewAngle) ? Math.max(-30,Math.min(30,viewAngle)) : 16;
  roomToggle.checked = roomEnabled; orbitControl.value = viewAngle; orbitControl.disabled = !roomEnabled;
  const sceneLabel=document.querySelector('.stamp strong');
  sceneLabel.textContent=roomEnabled?'Fire-lit room · etched stone':'Fire and smoke · black background';
  function camera() {
    const yaw=viewAngle*Math.PI/180;
    const eye=[panX+Math.sin(yaw)*13,3.5+panY,Math.cos(yaw)*13];
    const normalize=v=>{const length=Math.hypot(...v);return v.map(x=>x/length);};
    const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
    const forward=normalize([panX-eye[0],2.4+panY-eye[1],-eye[2]]);
    const right=normalize(cross(forward,[0,1,0]));
    return {eye,forward,right,up:cross(right,forward)};
  }
  const gl = canvas.getContext('webgl2', { alpha: false, antialias: false, powerPreference: 'high-performance', failIfMajorPerformanceCaveat: true, preserveDrawingBuffer: false });
  if (!gl) { await scope.stop(); throw new Error('WebGL 2 is unavailable in this browser session. Reload or reopen the browser.'); }
  if (!gl.getExtension('EXT_color_buffer_float')) { await scope.stop(); gl.getExtension('WEBGL_lose_context')?.loseContext(); throw new Error('Floating point GPU targets are unavailable in this browser.'); }
  const probe=legacyProbe(gl);
  const rendererInfo=gl.getExtension('WEBGL_debug_renderer_info');
  const renderer=String(gl.getParameter(rendererInfo?rendererInfo.UNMASKED_RENDERER_WEBGL:gl.RENDERER));
  if(/swiftshader|llvmpipe|softpipe|software rasterizer|microsoft basic render/i.test(renderer)){
    await scope.stop();gl.getExtension('WEBGL_lose_context')?.loseContext();
    throw new Error('The browser selected software rendering. Enable hardware acceleration and restart the browser.');
  }
  const frameQueue=createGLFrameQueue(gl);
  document.querySelector('#gpu-status').textContent=renderer;
  // RGBA16F filtering is core WebGL2 (OES_texture_half_float_linear moved
  // into core). OES_texture_float_linear only gates 32-bit float filtering.
  const halfFloatLinear = true;

  const shaders=createOriginalShaders({domain,hasPowers,hasWood,initialPowerKind:powerDefinition(initialPreset)?.kind??null,
    MAX_POWER_EMITTER,renderSize:[RW,RH],emittersGLSL:window.createFireEmitters(MAX_POWER_EMITTER-21,POWER_CAST_CAPACITY),
    propsGLSL:window.FireProps,woodMaterialGLSL:window.WoodMaterialGLSL});
  const {vertex,shared,presentation}=shaders;
  const simulation=(kind)=>shaders.simulation(kind,{pressureGLSL:pressure.samplingGLSL,vorticityGLSL:vorticity.samplingGLSL,advectionGLSL:advection.correctionGLSL});
  const rendering=()=>shaders.rendering(room.surfaceGLSL);
  function shader(type, source) {
    const s = gl.createShader(type); gl.shaderSource(s, source); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {const detail=gl.getShaderInfoLog(s);gl.deleteShader(s);throw new Error(detail || 'Shader compile failed');}
    return s;
  }
  function program(fragment,customVertex=vertex,label='Original shader') {
    const p = gl.createProgram(),shaders=[];
    try{
      shaders.push(shader(gl.VERTEX_SHADER, customVertex));shaders.push(shader(gl.FRAGMENT_SHADER, fragment));
      for(const s of shaders)gl.attachShader(p,s);gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(`${label}: ${gl.getProgramInfoLog(p) || 'Shader link failed'}`);
      return p;
    }catch(error){gl.deleteProgram(p);throw error;}
    finally{for(const s of shaders)gl.deleteShader(s);}
  }
  async function asyncProgram(fragment,label) {
    const parallel=gl.getExtension('KHR_parallel_shader_compile');
    const p=gl.createProgram(),shaders=[];
    for(const [type,source] of [[gl.VERTEX_SHADER,vertex],[gl.FRAGMENT_SHADER,fragment]]){
      const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);gl.attachShader(p,s);shaders.push(s);
    }
    gl.linkProgram(p);
    try {
      // Defer status checks until the driver reports completion; checking
      // COMPILE_STATUS immediately defeats parallel compilation.
      if(parallel){const deadline=performance.now()+60000;
        while(!gl.getProgramParameter(p,parallel.COMPLETION_STATUS_KHR)){
          if(gl.isContextLost())throw new Error(`${label}: GPU context lost during compilation`);
          if(performance.now()>deadline)throw new Error(`${label}: shader compilation timed out`);
          await new Promise(resolve=>setTimeout(resolve,16));
        }
      }
      if(!gl.getProgramParameter(p,gl.LINK_STATUS)){
        const detail=[gl.getProgramInfoLog(p),...shaders.map(s=>gl.getShaderInfoLog(s))].filter(Boolean).join('\n');
        throw new Error(`${label}: ${detail||'Shader link failed (driver returned no diagnostic)'}`);
      }
      return p;
    } catch(error){gl.deleteProgram(p);throw error;}
    finally{for(const s of shaders)gl.deleteShader(s);}
  }
  const namedProgram=label=>(fragment,customVertex=vertex)=>program(fragment,customVertex,`Original ${label}`);
  // Uniform locations are stable for a linked program. Avoid synchronously
  // looking up twenty locations on every simulation step.
  const locations = new WeakMap();
  function uniform(p, name) {
    let cache=locations.get(p);
    if (!cache) { cache=new Map(); locations.set(p,cache); }
    if (!cache.has(name)) cache.set(name,gl.getUniformLocation(p,name));
    return cache.get(name);
  }
  function texture(width, height, data, filter = gl.LINEAR, internal = gl.RGBA8, format = gl.RGBA, type = gl.UNSIGNED_BYTE) {
    const t = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, filter);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, width, height, 0, format, type, data);
    return t;
  }
  function target() {
    const filter = halfFloatLinear ? gl.LINEAR : gl.NEAREST;
    const vf = texture(AW, AH, null, filter, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
    const chem = texture(AW, AH, null, filter, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
    const fbo = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, vf, 0);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT1, gl.TEXTURE_2D, chem, 0);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0, gl.COLOR_ATTACHMENT1]);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Floating point simulation framebuffer incomplete');
    return { vf, chem, fbo };
  }
  function projectionTarget() {
    const color = texture(RW, RH, null, gl.LINEAR, gl.RGBA16F, gl.RGBA, gl.HALF_FLOAT);
    const fbo = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, color, 0);
    gl.drawBuffers([gl.COLOR_ATTACHMENT0]);
    if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error('Volume projection framebuffer incomplete');
    return { color, fbo };
  }
  function bind(tex, unit, location) {
    gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, tex); gl.uniform1i(location, unit);
  }
  function reset() {
    stateRevision++;
    elapsed = 0; accumulator = 0;smokeDecayRemainder=0; physicalClock.reset(performance.now());
    needsDraw = true;
    brush.active = false;
    brush.fromX = brush.x; brush.fromY = brush.y;
    pointer.vx = 0; pointer.vy = 0;
    powerPool.reset();
    fuelBrush.clear();groundFuel?.clear();woodState?.reset();woodMechanics?.reset();fuelGesture=null;manualFuelSession=false;syncFuelControls();
    if (!pressure || !targets) return;
    pressure.reset();
    for (const t of targets) {
      gl.bindFramebuffer(gl.FRAMEBUFFER, t.fbo); gl.viewport(0, 0, AW, AH);
      gl.clearBufferfv(gl.COLOR, 0, new Float32Array([0, 0, 0, 0]));
      gl.clearBufferfv(gl.COLOR, 1, new Float32Array([0, 1, 0, 0]));
    }
    current = 0;
  }
  function runStep(dt=STEP) {
    const from = targets[current], to = targets[1 - current];
    const profile=sharedPresets.get(activePreset);
    configureWood(profile);
    woodState.step(from.chem,sourceTexture,objectTexture,dt,{clock:elapsed,age:elapsed-burstStart,starter:!freeMode||brush.active,timeScale:woodTimeScale,mechanics:woodMechanics});
    if(woodState.enabled)woodMechanics.step(woodState,dt);
    if(profile?.kindling&&brush.active&&elapsed-burstStart>=0&&elapsed-burstStart<WOOD_THERMO.starterDurationS)groundFuel.ignite();
    groundFuel.step(from.chem,dt,fuelBrush.consume(),!profile?.smokeSimulation&&activePreset!=='smoke-burst',{wood:fuelControl.value==='wood',timeScale:woodTimeScale});
    if(!freeMode&&!woodState.enabled)groundFuel.updateGuide(from.chem,sourceTexture,dt);
    vorticity.update(from.vf,from.chem,brush,freeMode && emitterKind<3,freeMode && emitterKind===6);
    // Reuse the inactive chemistry target; no new full-resolution allocation.
    gl.bindFramebuffer(gl.FRAMEBUFFER,to.fbo);gl.drawBuffers([gl.NONE,gl.COLOR_ATTACHMENT1]);
    gl.viewport(0,0,AW,AH);gl.useProgram(diffuseProgram);
    bind(from.chem,1,uniform(diffuseProgram,'chemTex'));gl.uniform1f(uniform(diffuseProgram,'delta'),dt);
    gl.drawArrays(gl.TRIANGLES,0,3);
    [from.chem,to.chem]=[to.chem,from.chem];
    for(const target of [from,to]){gl.bindFramebuffer(gl.FRAMEBUFFER,target.fbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT1,gl.TEXTURE_2D,target.chem,0);gl.drawBuffers([gl.COLOR_ATTACHMENT0,gl.COLOR_ATTACHMENT1]);}
    const predictor = advection.step(from.vf, from.chem, pressure.getCorrection(), dt);
    gl.useProgram(simProgram); gl.bindFramebuffer(gl.FRAMEBUFFER, to.fbo); gl.viewport(0, 0, AW, AH);
    bind(from.vf, 0, uniform(simProgram, 'vfTex'));
    bind(from.chem, 1, uniform(simProgram, 'chemTex'));
    bind(sourceTexture, 2, uniform(simProgram, 'sourceTex'));
    bind(noiseTexture, 3, uniform(simProgram, 'noiseTex'));
    bind(widthTexture, 4, uniform(simProgram, 'widthTex'));
    bind(pressure.getCorrection(), 5, uniform(simProgram, 'pressureCorrectionTex'));
    bind(predictor, 6, uniform(simProgram, 'mcPredictorTex'));
    bind(vorticity.texture, 7, uniform(simProgram, 'vortexTex'));
    groundFuel.bind(simProgram);
    woodState.bind(simProgram);
    woodMechanics.bind(simProgram);
    gl.activeTexture(gl.TEXTURE14);gl.bindTexture(gl.TEXTURE_3D,objectTexture);gl.uniform1i(uniform(simProgram,'objectTex'),14);
    gl.activeTexture(gl.TEXTURE15);gl.bindTexture(gl.TEXTURE_3D,turbulenceTexture);gl.uniform1i(uniform(simProgram,'turbulenceTex'),15);
    gl.uniform3fv(uniform(simProgram, 'vortexOrigin'), vorticity.origin);
    gl.uniform3fv(uniform(simProgram, 'vortexSpan'), vorticity.span);
    gl.uniform1i(uniform(simProgram,'emitterKind'),emitterKind);
    gl.uniform1f(uniform(simProgram,'burstAge'),elapsed-burstStart);
    if(profile?.power){
      powerPool.write(powerPacked);
      for(let slot=0;slot<POWER_CAST_CAPACITY;slot++)for(let field=0;field<4;field++)for(let axis=0;axis<4;axis++)powerUniforms[field][slot*4+axis]=powerPacked[slot*16+field*4+axis];
      gl.uniform4fv(uniform(simProgram,'powerCastOriginAge[0]'),powerUniforms[0]);
      gl.uniform4fv(uniform(simProgram,'powerCastDirectionStrength[0]'),powerUniforms[1]);
      gl.uniform4fv(uniform(simProgram,'powerCastKindScale[0]'),powerUniforms[2]);
      gl.uniform4fv(uniform(simProgram,'powerCastTargetCharge[0]'),powerUniforms[3]);
    }
    const sourceShape=shapeFor(activePreset);
    gl.uniform1i(uniform(simProgram,'sourceEffectKind'),profile?.effect[0]??-1);
    gl.uniform1f(uniform(simProgram,'objectVariation'),profile?.ignition==='all'?1:profile?.moisture==='damp'?2:profile?.ignition==='crown'?3:0);
    gl.uniform1f(uniform(simProgram,'burstDuration'),profile?.effect[2]||.10);
    const fuel=fuelProfiles[fuelControl.value];
    gl.uniform3f(uniform(simProgram,'fuelProfile'),(profile?.power?1:fuel[0]*sourceShape[2])*(profile?.chemistry[1]??1),fuel[1]*(profile?.chemistry[2]||1),fuel[2]);
    gl.uniform1f(uniform(simProgram,'sourceScale'),sourceShape[0]);
    gl.uniform1f(uniform(simProgram,'sourceLift'),sourceShape[1]);
    gl.uniform1f(uniform(simProgram,'presetBuoyancy'),(profile?.dynamics[3]||1)*4.);
    const sourceHeat=profile?.chemistry[0]??1;
    gl.uniform1f(uniform(simProgram,'sourceHeat'),sourceHeat);
    gl.uniform1f(uniform(simProgram,'powerConfinement'),profile?.power?profile.dynamics[2]:1);
    gl.uniform1f(uniform(simProgram,'powerTurbulence'),profile?.power?profile.chemistry[3]:0);
    gl.uniform1f(uniform(simProgram,'smokeOnly'),profile?.smokeSimulation||activePreset==='smoke-burst'?1:0);
    gl.uniform1f(uniform(simProgram, 'clock'), elapsed);
    gl.uniform1f(uniform(simProgram, 'delta'), dt);
    const smoke=advanceSmokeDecay(smokeDecayRemainder,dt);smokeDecayRemainder=smoke.remainder;gl.uniform1f(uniform(simProgram,'smokeDecayDt'),smoke.decayDt);
    gl.uniform2f(uniform(simProgram, 'pointer'), pointer.x, pointer.y);
    const movingSource = !freeMode || pointer.down;
    gl.uniform2f(uniform(simProgram, 'pointerMotion'), movingSource ? pointer.vx : 0, movingSource ? pointer.vy : 0);
    // Holding a source must not continuously push gas radially away from it.
    gl.uniform1f(uniform(simProgram, 'pointerStrength'), !freeMode && pointer.active ? .32 : 0.0);
    gl.uniform2f(uniform(simProgram, 'brushFrom'), brush.fromX, brush.fromY);
    gl.uniform2f(uniform(simProgram, 'brushTo'), brush.x, brush.y);
    gl.uniform1f(uniform(simProgram, 'brushActive'), brush.active ? 1.0 : 0.0);
    gl.uniform1f(uniform(simProgram, 'sourceEnabled'), freeMode ? 0.0 : 1.0);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    brush.fromX = brush.x; brush.fromY = brush.y;
    current = 1 - current;
    gl.activeTexture(gl.TEXTURE5); gl.bindTexture(gl.TEXTURE_2D, null);
    pressure.update(targets[current].vf,0,targets[current].chem);
    if(profile?.power)powerPool.step(dt);
    stateRevision++;
    pointer.vx *= .48; pointer.vy *= .48;
  }
  function draw() {
    if(paused){const packet=fuelBrush.consume();if(packet)groundFuel.step(targets[current].chem,0,packet,true,{wood:fuelControl.value==='wood',timeScale:woodTimeScale});}
    // Camera changes do not change emission or soot. Reuse their illumination
    // while paused so inspecting the volume does not rebuild all shadow maps.
    const activeWoodMesh=woodState.enabled&&woodMesh.ready;
    const hasProps=activeWoodMesh||freeMode&&(emitterKind===1||emitterKind===2||(emitterKind>=16&&emitterKind<=20));
    const litVolume=roomEnabled||window.SceneLights.active;
    if(lightingRevision!==window.SceneLights.revision||(litVolume?roomLightRevision!==stateRevision:hasProps&&propLightRevision!==stateRevision)){
      const color=FIRE_COLORS.find(c=>c.id===flameColor);
      room.update(targets[current].vf,targets[current].chem,fuelControl.value==='gas'?1:0,litVolume,roomEnabled,color?.rgb||[1,1,1],flameColor==='natural'?0:1,fireLight/24);
      propLightRevision=stateRevision;roomLightRevision=litVolume?stateRevision:-1;lightingRevision=window.SceneLights.revision;
    }
    if(!litVolume && smokeLightRevision!==stateRevision){
      smokeLight.update(targets[current].chem);smokeLightRevision=stateRevision;
    }
    configureWood(sharedPresets.get(activePreset));
    const guideSource=!freeMode||sharedPresets.get(activePreset)?.object==='wood-sigil';
    const meshVisible=woodMesh.draw({wood:woodState,mechanics:woodMechanics,room,roomEnabled,sourceVisible:woodState.enabled&&(!guideSource||sourceGuide),camera:camera(),tan:lensTan(),zoom:viewZoom,pan:[panX,panY],lighting:p=>window.SceneLights.bind(gl,name=>uniform(p,name),roomEnabled)});
    gl.useProgram(renderProgram); gl.bindFramebuffer(gl.FRAMEBUFFER, projected.fbo);
    gl.viewport(0, 0, RW, RH);
    bind(targets[current].vf, 0, uniform(renderProgram, 'vfTex'));
    bind(targets[current].chem, 1, uniform(renderProgram, 'chemTex'));
    bind(sourceTexture,2,uniform(renderProgram,'sourceTex'));
    groundFuel.bind(renderProgram,{render:true,guideVisible:sourceGuide&&!freeMode&&!woodMesh.ready,wood:fuelControl.value==='wood'});
    woodState.bind(renderProgram,true);woodMesh.bind(renderProgram,meshVisible);
    gl.activeTexture(gl.TEXTURE14);gl.bindTexture(gl.TEXTURE_3D,objectTexture);gl.uniform1i(uniform(renderProgram,'objectTex'),14);
    bind(smokeLight.texture, 8, uniform(renderProgram, 'smokeLightTex'));
    room.bind(renderProgram,uniform);
    window.SceneLights.bind(gl,name=>uniform(renderProgram,name),roomEnabled);
    gl.uniform1f(uniform(renderProgram,'customLighting'),window.SceneLights.active?1:0);
    gl.uniform1f(uniform(renderProgram,'gasFlame'),fuelControl.value==='gas'?1:0);
    const tint=FIRE_COLORS.find(c=>c.id===flameColor);
    gl.uniform3fv(uniform(renderProgram,'flameTint'),tint?.rgb||[1,1,1]);
    gl.uniform1f(uniform(renderProgram,'tintStrength'),flameColor==='natural'?0:1);
    gl.uniform1f(uniform(renderProgram,'inspectSmoke'),inspectSmoke?1:0);
    gl.uniform1i(uniform(renderProgram,'visibleEmitter'),freeMode&&!activeWoodMesh?emitterKind:0);
    gl.uniform1f(uniform(renderProgram,'inspectionLight'),litVolume?0:1);
    gl.uniform2f(uniform(renderProgram,'sourcePosition'),brush.x,brush.y);
    gl.uniform1f(uniform(renderProgram,'sourceScale'),shapeFor(activePreset)[0]);
    gl.uniform1f(uniform(renderProgram,'roomEnabled'),roomEnabled?1:0);
    gl.uniform1f(uniform(renderProgram,'cameraTan'),lensTan());
    gl.uniform1f(uniform(renderProgram,'viewZoom'),viewZoom);
    gl.uniform2f(uniform(renderProgram,'viewPan'),panX,panY);
    const viewCamera=camera();
    for(const name of ['eye','forward','right','up']) {
      gl.uniform3fv(uniform(renderProgram,'camera'+name[0].toUpperCase()+name.slice(1)),viewCamera[name]);
    }
    gl.uniform1f(uniform(renderProgram, 'clock'), elapsed);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    gl.useProgram(presentProgram); gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, canvas.width, canvas.height);
    bind(projected.color, 0, uniform(presentProgram, 'projection'));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
  const pointer = { x: .5, y: .5, vx: 0, vy: 0, active: false, down: false, id: null, last: 0 };
  const brush = { x: .5, y: .5, fromX: .5, fromY: .5, active: false };
  let freeMode = false, activePreset = initialPreset;
  let emitterKind=0, burstStart=-100,powerOriginZ=0,powerTrailLast=null;
  let powerAimTarget=null,powerAimDirection=null;
  const powerTargetBounds={min:[MINX+.02*WX,.14,domain.minimum[2]+.02*WZ],max:[MINX+.98*WX,MINY+.96*WY,domain.minimum[2]+.98*WZ]};
  const powerPool=new PowerCastPool({bounds:powerTargetBounds}),powerPacked=new Float32Array(POWER_CAST_CAPACITY*16);
  const powerUniforms=Array.from({length:4},()=>new Float32Array(POWER_CAST_CAPACITY*4));
  let powers=normalizePowerSettings(initialPowers??{strength:qaParams.get('powerStrength')??1,heading:qaParams.get('powerHeading')??powerDefinition(initialPreset)?.defaultHeading??0,elevation:qaParams.get('powerElevation')??9});
  const currentPower=()=>powerDefinition(activePreset);
  const powerKind=()=>currentPower()?.kind||0;
  const floorFuelPower=()=>currentPower()?.floorFuel??powerKind()===5;
  const finitePower=()=>!!currentPower()&&!currentPower().continuous;
  const presetControl=document.querySelector('#preset');
  const fuelControl=document.querySelector('#fuel');
  const burstButton=document.querySelector('#burst');
  const fuelProfiles={wood:[1,.708,1],gas:[.85,.12,1.25],oil:[1.15,1.8,.85]};
  const sharedPresets=new Map(FIRE_PRESETS.map(p=>[p.id,p]));
  sharedPresets.set('campfire',{...sharedPresets.get('bonfire'),id:'campfire'});
  // Three distinct wood beds share the same coupled fluid and combustion.
  // Scale the fuel footprint, log receiver and lift together.
  const sourceShapes={free:[1.1,1,1],campfire:[1,1,1],bonfire:[1.48,.82,1.12],hearth:[.68,.64,.78]};
  function configureWood(profile){
    let descriptor=originalWoodSource(activePreset,profile);
    if(descriptor.kind===1&&freeMode)descriptor={kind:0,bark:0};
    const scale=descriptor.kind===1?4:shapeFor(activePreset)[0],centre=descriptor.kind===1?[0,MINY+2.95]:[MINX+brush.x*WX,MINY+brush.y*WY];
    const bounds=descriptor.kind===2?[centre[0]-1.3*scale,centre[1]-.42*scale,centre[0]+1.3*scale,centre[1]+.29*scale]:[centre[0]-1.5*scale,centre[1]-1.5*scale,centre[0]+1.5*scale,centre[1]+1.5*scale];
    woodState.configure({...descriptor,objectId:profile?.object,depthSpacing:WZ/(DEPTH-1),key:activePreset+':'+descriptor.kind,scale,centre,bounds,ignitionBounds:[MINX,MINY,WX,WY],sigma:descriptor.kind===1?.055:scale*(descriptor.kind===2?.26:.36),moisture:profile?.moisture==='damp'?WOOD_THERMO.dampMoistureFraction:WOOD_THERMO.dryMoistureFraction,variation:profile?.ignition==='all'?1:profile?.ignition==='crown'?3:0});
    woodMechanics.configure(centre,scale);
    woodSpeedControl.disabled=!descriptor.kind&&!(groundFuel?.active&&fuelControl.value==='wood');
  }
  async function loadObject(name){
    if(objectModels.has(name))return objectModels.get(name);
    const thermalPath=name==='cybr-tree'?'forest-tree/wood-solid.rgba16.bin':['logs','house','wood-sigil'].includes(name)?name+'/solid.rgba16.bin':name+'.rgba16.bin';
    const response=await fetch('pyro-gpu/objects/'+thermalPath);
    if(!response.ok)throw new Error('Object geometry missing: '+name);
    const bytes=await response.arrayBuffer();
    if(bytes.byteLength!==64*64*64*8)throw new Error('Object geometry has an invalid size: '+name);
    const texture=gl.createTexture();gl.bindTexture(gl.TEXTURE_3D,texture);
    gl.texParameteri(gl.TEXTURE_3D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_3D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
    for(const axis of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T,gl.TEXTURE_WRAP_R])gl.texParameteri(gl.TEXTURE_3D,axis,gl.CLAMP_TO_EDGE);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT,1);
    gl.texImage3D(gl.TEXTURE_3D,0,gl.RGBA16F,64,64,64,0,gl.RGBA,gl.HALF_FLOAT,new Uint16Array(bytes));
    objectModels.set(name,texture);return texture;
  }
  const presets={sigil:0,free:0,campfire:1,bonfire:1,hearth:1,torch:2,ring:3,sphere:4,wall:5,explosion:6};
  const shapeFor=key=>!sharedPresets.get(key)?.object&&sourceShapes[key]||[sharedPresets.get(key)?.effect[1]||1,Math.max(.35,Math.min(2,(sharedPresets.get(key)?.dynamics[0]||.5)/.5)),1];
  function syncFuelControls(){
    const placed=!!groundFuel?.active||fuelBrush.dirty.size>0;
    document.querySelector('#fuel-actions').hidden=!fuelTool&&!placed;
    const smokeSource=!!sharedPresets.get(activePreset)?.smokeSimulation||activePreset==='smoke-burst';
    const ignite=document.querySelector('#ignite-fuel');ignite.disabled=!placed||smokeSource;
    ignite.title=smokeSource?'Choose a fire source to ignite fuel.':!placed?'Drop fuel on the floor first.':'Apply a finite thermal ignition to the deposited fuel.';
    clearFuelControl.disabled=!placed;
    document.querySelector('#sigil-guide-control').hidden=freeMode&&sharedPresets.get(activePreset)?.object!=='wood-sigil';
  }
  function describeSource(){
    syncFuelControls();
    const name=presetControl.selectedOptions[0]?.textContent||sharedPresets.get(activePreset)?.name||(activePreset==='free'?'Free fire':activePreset==='sigil'?'Cybrdelic sigil':activePreset);
    const finiteWood=originalWoodSource(activePreset,sharedPresets.get(activePreset)).kind>0;
    const definition=currentPower(),power=definition?.kind||0;
    extinguishButton.textContent=finiteWood?'Stop ignition':power?'Stop casting':'Stop fuel';
    burstButton.textContent=definition?.action||(power?'Cast power':'Trigger burst');
    message.textContent=power?`${name} · ${definition.hold?'hold to charge, drag to aim':finitePower()?'click to cast again':floorFuelPower()?'drag across the floor':'drag to move the power'}`:emitterKind===6?`${name} · click to burst again`:`${name} · drag to move the source`;
    help.textContent=definition?.hint|| (emitterKind===6
      ? 'Click to detonate at the cursor, or use Trigger burst. Each burst adds to the live smoke. Pause to inspect the expansion.'
      : finiteWood
      ? 'Surface heat dries and chars finite wood. Stop ignition ends the starter; hot wood keeps burning until its fuel is spent. Original shares its material state through depth.'
      : 'Click or drag to place the source. Release to keep burning. Stop fuel lets the flame die while its smoke drifts.');
    canvas.setAttribute('aria-label',`${name}. ${help.textContent}`);
  }
  function ignite(){
    brush.active=true;burstStart=elapsed;
    focusButton.disabled=false;extinguishButton.disabled=false;
    paused=false;captureAt=qaCaptureStop;lastFrame=performance.now();
    document.querySelector('#pause').textContent='Pause';
    describeSource();
  }
  function castPower({held=false,target}={}){
    const definition=currentPower();if(!definition)return false;
    const cast=powerPool.cast(definition,{origin:[MINX+brush.x*WX,MINY+brush.y*WY,powerOriginZ],direction:powerAimDirection||powerDirection(powers),target:target||powerAimTarget,strength:powers.strength,scale:shapeFor(activePreset)[0],held});
    if(!cast)return false;
    if(floorFuelPower()){
      depositPowerTrail([MINX+brush.x*WX,powerOriginZ]);
      groundFuel.ignite();manualFuelSession=true;
    }
    ignite();return true;
  }
  function depositPowerTrail(at,from=null){
    const radius=fuelBrush.radius,amount=fuelBrush.amount;
    fuelBrush.radius=Math.max(.08,Math.min(.8,.26*shapeFor(activePreset)[0]));fuelBrush.amount=.85*powers.strength;
    const changed=from?fuelBrush.stroke(from,at):fuelBrush.stamp(...at);
    fuelBrush.radius=radius;fuelBrush.amount=amount;return changed;
  }
  async function selectPreset(key,frameSource=true,keepAppearance=false){
    const profile=sharedPresets.get(key);
    if(((profile?.effect[0]===0&&profile?.effect[3]<.5)||!!profile?.power)!==domain.blast||!!profile?.object!==domain.object||!!powerDefinition(key)!==hasPowers||(originalWoodSource(key,profile).kind>0)!==hasWood){onRemount(key);return;}
    if(hasPowers){
      const kind=powerDefinition(key).kind,wasPaused=paused;
      paused=true;
      try{
        let compiled=powerPrograms.get(kind);
        if(!compiled){compiled=await asyncProgram(simulation(kind),'Original '+key);powerPrograms.set(kind,compiled);}
        simProgram=compiled;
      }finally{paused=wasPaused;}
    }
    objectTexture=profile?.object?await loadObject(profile.object):['sigil','sigil-cybr','violet-sigil'].includes(key)?await loadObject('wood-sigil'):emptyObjectTexture;
    activePreset=key;presetControl.value=key;emitterKind=profile?.object?emitterKindFor(profile):presets[key]??emitterKindFor(profile);
    const woodSource=originalWoodSource(key,profile);await woodMechanics.load(woodSource.kind?profile?.object||(woodSource.kind===2?'logs':'wood-sigil'):null);await woodMesh.load(woodMechanics.asset);
    if(!keepAppearance){
    fuelControl.value=profile?.fuel||'wood';
    flameColor=profile?.color||'natural';colorControl.value=flameColor;
    inspectSmoke=!!profile?.smokeSimulation||key==='smoke-burst';smokeControl.checked=inspectSmoke;
    }
    measurement=null;benchmarkButton.disabled=false;
    freeMode=!!profile?.object||!['sigil','sigil-cybr','violet-sigil'].includes(key);
    pointer.down=false;pointer.id=null;pointer.active=false;endPan();setTool(false);
    reset();burstStart=-100;powerOriginZ=profile?.source?.[2]??0;powerTrailLast=null;powerAimTarget=null;powerAimDirection=null;
    extinguishButton.hidden=!freeMode;
    burstButton.hidden=emitterKind!==6&&!powerKind();
    restartButton.textContent=key==='free'?'Clear fire':'Restart';
    focusButton.disabled=true;
    brush.x=brush.fromX=((profile?.source?.[0]??0)-MINX)/WX;
    const height=profile?.source?.[1]??(key==='ring'?1.65:key==='sphere'?1.6:emitterKind===6?.5:key==='torch'?1.1:key==='hearth'?.28:emitterKind===1?.36:.2);
    brush.y=brush.fromY=(height-MINY)/WY;
    paused=false;document.querySelector('#pause').textContent='Pause';lastFrame=performance.now();
    if(floorFuelPower()&&!roomEnabled){roomToggle.checked=true;roomToggle.dispatchEvent(new Event('change'));}
    if(profile?.kindling){const radius=fuelBrush.radius,amount=fuelBrush.amount;fuelBrush.radius=profile.kindling.radius;fuelBrush.amount=profile.kindling.amount;const offset=profile.kindling.offset||[0,0],scale=shapeFor(key)[0];fuelBrush.stamp((profile.source?.[0]||0)+offset[0]*scale,(profile.source?.[2]||0)+offset[1]*scale);fuelBrush.radius=radius;fuelBrush.amount=amount;groundFuel.ignite();}
    if(freeMode && key!=='free'){if(powerKind())castPower();else ignite();}
    else if(freeMode){extinguishButton.disabled=true;describeSource();message.textContent='Free fire · click to ignite';}
    else {
      message.textContent='Live GPU sigil · click to create fire';
      help.textContent='Choose a source above, or click the canvas to create and drag your own fire.';
      canvas.setAttribute('aria-label','Live GPU-simulated volumetric fire forming the Cybrdelic 02 mark. Click to create your own fire.');
    }
    if(frameSource){
      if(freeMode && key!=='free')focusSource();
      else {panX=panY=0;viewZoom=1;updateView();}
    }
    needsDraw=true;
  }
  fuelControl.onchange=()=>{stateRevision++;needsDraw=true;};
  burstButton.onclick=()=>{if(powerKind())castPower();else if(emitterKind===6)ignite();};

  // Rendering and pointer unprojection share the same lens and camera. Keep
  // this unclamped for cursor-anchored zoom and pan; clamp only fuel placement.
  function scenePoint(e) {
    const r = canvas.getBoundingClientRect();
    let x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    let y = Math.max(0, Math.min(1, 1 - (e.clientY - r.top) / r.height));
    if(roomEnabled) {
      const c=camera();
      const ray=c.forward.map((v,i)=>v+(x*2-1)*(16/9)*lensTan()*c.right[i]+(y*2-1)*lensTan()*c.up[i]);
      const distance=-c.eye[2]/ray[2];
      x=(c.eye[0]+ray[0]*distance-MINX)/WX;
      y=(c.eye[1]+ray[1]*distance-MINY)/WY;
    } else {x=((x-.5)*14/viewZoom+panX-MINX)/WX;y=((y-.5)*7.875/viewZoom+2.8875+panY-MINY)/WY;}
    return {x,y};
  }
  function point(e) {
    const at=scenePoint(e);
    const base=Math.max(sharedPresets.get(activePreset)?.minHeight||0,emitterKind===1?.36:emitterKind===2?1.0:emitterKind===3?1.5:emitterKind===4?.85:.08);
    const x=Math.max(.02,Math.min(.98,at.x)),y=Math.max((base-MINY)/WY,Math.min(.96,at.y));
    const now = performance.now();
    const dt = Math.max(.01, (now - pointer.last) / 1000);
    pointer.vx = pointer.last ? Math.max(-2, Math.min(2, (x - pointer.x) / dt)) : 0;
    pointer.vy = pointer.last ? Math.max(-2, Math.min(2, (y - pointer.y) / dt)) : 0;
    pointer.x = x; pointer.y = y; pointer.last = now; pointer.active = true;
  }
  function floorPoint(e){
    if(!roomEnabled)return null;
    const r=canvas.getBoundingClientRect(),x=(e.clientX-r.left)/r.width,y=1-(e.clientY-r.top)/r.height;
    if(![x,y].every(Number.isFinite)||x<0||x>1||y<0||y>1)return null;
    const c=camera(),ray=c.forward.map((v,i)=>v+(x*2-1)*(16/9)*lensTan()*c.right[i]+(y*2-1)*lensTan()*c.up[i]);
    return floorHit(c.eye,ray,fuelBounds);
  }
  function placePower(e,start=false){
    const kind=powerKind();
    if(!kind)return false;
    if(!currentPower().floor){point(e);brush.x=pointer.x;brush.y=pointer.y;powerOriginZ=0;return true;}
    const at=roomEnabled?floorPoint(e):[MINX+Math.max(.02,Math.min(.98,scenePoint(e).x))*WX,0];
    if(!at){if(floorFuelPower())powerTrailLast=null;message.textContent='Choose a floor point inside the simulation to cast this power.';return false;}
    if(DIRECTIONAL_GROUND_POWERS.has(activePreset)){
      powerAimTarget=[at[0],.14,at[1]];powerAimDirection=[at[0]-(MINX+brush.x*WX),0,at[1]-powerOriginZ];
      if(Math.hypot(...powerAimDirection)<.001)powerAimDirection=powerDirection(powers);
      pointer.x=(at[0]-MINX)/WX;pointer.y=brush.y;pointer.active=true;return true;
    }
    if(floorFuelPower()){
      if(start)powerTrailLast=at;
      else if(!powerTrailLast&&brush.active&&depositPowerTrail(at)){groundFuel.ignite();manualFuelSession=true;}
      else if(brush.active&&depositPowerTrail(at,powerTrailLast)){groundFuel.ignite();manualFuelSession=true;}
      powerTrailLast=at;syncFuelControls();
    }
    brush.x=(at[0]-MINX)/WX;brush.y=((sharedPresets.get(activePreset)?.source?.[1]??.18)-MINY)/WY;powerOriginZ=at[1];
    pointer.x=brush.x;pointer.y=brush.y;pointer.active=true;return true;
  }
  function aimHeldPower(e,release=false){
    const cast=powerPool.latest;if(!cast?.active||!cast.held)return false;
    const point=scenePoint(e),floor=roomEnabled&&(currentPower().floor||currentPower().targetMode==='ground'||MINY+point.y*WY<.35)?floorPoint(e):null;
    const target=floor?[floor[0],.14,floor[1]]:[MINX+point.x*WX,Math.max(.14,MINY+point.y*WY),0];
    for(let axis=0;axis<3;axis++)target[axis]=Math.max(powerTargetBounds.min[axis],Math.min(powerTargetBounds.max[axis],target[axis]));
    const direction=target.map((value,axis)=>value-cast.origin[axis]);
    return release?powerPool.release(target,direction):powerPool.aim(target,direction);
  }
  function addFuelPoint(e,start=false){
    const at=floorPoint(e);
    if(!at){if(fuelGesture)fuelGesture.last=null;message.textContent='Place fuel on the floor inside the simulation bounds.';return false;}
    if(start||!fuelGesture?.last)fuelBrush.stamp(...at);else fuelBrush.stroke(fuelGesture.last,at);
    if(fuelGesture)fuelGesture.last=at;
    manualFuelSession=true;syncFuelControls();needsDraw=true;message.textContent='Unlit fuel placed · nearby flame or Ignite fuel starts combustion.';return true;
  }
  on(view,'pointermove', e => {
    if(panGesture){
      if(e.pointerId!==panGesture.id)return;
      const at=scenePoint(e);
      panX+=(panGesture.anchor.x-at.x)*WX;panY+=(panGesture.anchor.y-at.y)*WY;
      updateView();return;
    }
    if(fuelTool){pointer.active=false;if(fuelGesture?.id===e.pointerId)addFuelPoint(e);return;}
    if(panTool||e.shiftKey||e.buttons===2){pointer.active=false;return;}
    if (pointer.down && e.pointerId !== pointer.id) return;
    if(powerKind()){
      if(pointer.down){
        if(powerPool.latest?.held)aimHeldPower(e);
        else if(!finitePower()&&placePower(e))powerPool.move([MINX+brush.x*WX,MINY+brush.y*WY,powerOriginZ],undefined,{direction:powerDirection(powers),strength:powers.strength});
      }
      return;
    }
    point(e);
    if (freeMode && pointer.down && emitterKind!==6) { brush.x = pointer.x; brush.y = pointer.y; }
  });
  on(view,'pointerdown', e => {
    if(pointer.down||panGesture||fuelGesture)return;
    if(panTool||e.shiftKey||e.button===2){
      e.preventDefault();view.focus({preventScroll:true});
      pointer.active=false;pointer.last=0;
      panGesture={id:e.pointerId,anchor:scenePoint(e)};
      view.setPointerCapture(e.pointerId);view.classList.add('is-panning');return;
    }
    if (pointer.down || (e.pointerType === 'mouse' && e.button !== 0)) return;
    e.preventDefault();
    view.focus({preventScroll:true});
    if(fuelTool){
      pointer.active=false;fuelGesture={id:e.pointerId,last:null};
      if(addFuelPoint(e,true))view.setPointerCapture(e.pointerId);else fuelGesture=null;
      return;
    }
    pointer.last=0;
    if(powerKind()){
      const held=!!currentPower().hold;
      if(!held&&!placePower(e,true))return;
      pointer.down=true;pointer.id=e.pointerId;view.setPointerCapture(e.pointerId);
      brush.fromX=brush.x;brush.fromY=brush.y;castPower({held});if(held)aimHeldPower(e);return;
    }
    point(e);
    pointer.down = true; pointer.id = e.pointerId;
    view.setPointerCapture(e.pointerId);
    if (!freeMode) {
      freeMode = true;emitterKind=0;activePreset='free';presetControl.value='free';
      reset();
      extinguishButton.hidden = false;
      restartButton.textContent = 'Clear fire';
    }
    brush.x = brush.fromX = pointer.x;
    brush.y = brush.fromY = pointer.y;
    ignite();
  });
  on(view,'pointerup', e => {
    if(panGesture?.id===e.pointerId){endPan();return;}
    if(fuelGesture?.id===e.pointerId){addFuelPoint(e);fuelGesture=null;return;}
    if (e.pointerId !== pointer.id) return;
    if(powerKind()){
      if(powerPool.latest?.held)aimHeldPower(e,true);
      else if(!finitePower()&&placePower(e))powerPool.move([MINX+brush.x*WX,MINY+brush.y*WY,powerOriginZ],undefined,{direction:powerDirection(powers),strength:powers.strength});
      pointer.down=false;pointer.id=null;powerTrailLast=null;return;
    }
    point(e);
    if (freeMode && emitterKind!==6) { brush.x = pointer.x; brush.y = pointer.y; }
    pointer.down = false; pointer.id = null;
  });
  on(view,'pointercancel', e => {
    if(panGesture?.id===e.pointerId){endPan();return;}
    if(fuelGesture?.id===e.pointerId){fuelGesture=null;return;}
    if (e.pointerId !== pointer.id) return;
    powerPool.cancelHeld();pointer.down = false; pointer.id = null; pointer.active = false;powerTrailLast=null;
  });
  on(view,'lostpointercapture', () => { endPan();fuelGesture=null;powerPool.cancelHeld();pointer.down = false; pointer.id = null;powerTrailLast=null; });
  on(window,'blur', () => { endPan();fuelGesture=null;powerPool.cancelHeld();pointer.down = false; pointer.id = null; pointer.active = false;powerTrailLast=null; });
  on(view,'pointerleave', () => { if (!pointer.down) pointer.active = false; });
  let captureAt = Number(new URL(location.href).searchParams.get('capture')) || 0;
  const physicalClock=new SimulationClock(performance.now());
  let smokeDecayRemainder=0;
  let paused = false, elapsed = 0, accumulator = 0, lastFrame = performance.now();
  let observedSteps = 0, observedDraws = 0, observedStart = lastFrame, needsDraw = true;
  function endPan(){panGesture=null;view.classList.remove('is-panning');pointer.last=0;}
  function updateView(){
    panX=Math.max(-6.5,Math.min(6.5,panX));panY=Math.max(-2.8,Math.min(3.5,panY));
    zoomControl.value=Math.round(viewZoom*100);
    document.querySelector('#zoom-value').textContent=`${Math.round(viewZoom*100)}%`;
    orbitControl.value=viewAngle;document.querySelector('#angle-value').textContent=`${viewAngle}°`;
    document.querySelector('#zoom-out').disabled=viewZoom<=.7;
    document.querySelector('#zoom-in').disabled=viewZoom>=3;
    pointer.active=false;pointer.last=0;needsDraw=true;
  }
  function setZoom(value,anchorEvent){
    if(pointer.down||panGesture||fuelGesture)return;
    const before=anchorEvent?scenePoint(anchorEvent):null;
    viewZoom=Math.max(.7,Math.min(3,Math.round(value*100)/100));
    if(before){const after=scenePoint(anchorEvent);panX+=(before.x-after.x)*WX;panY+=(before.y-after.y)*WY;}
    updateView();
  }
  function setTool(pan,dropFuel=false){
    endPan();fuelGesture=null;powerPool.cancelHeld();pointer.down=false;pointer.id=null;powerTrailLast=null;panTool=pan;fuelTool=dropFuel;pointer.active=false;
    document.querySelector('#fire-tool').setAttribute('aria-pressed',String(!pan&&!dropFuel));
    document.querySelector('#pan-tool').setAttribute('aria-pressed',String(pan));
    fuelToolControl.setAttribute('aria-pressed',String(dropFuel));
    view.dataset.tool=dropFuel?'fuel':pan?'pan':'fire';
    syncFuelControls();
    if(dropFuel){
      if(!roomEnabled){roomToggle.checked=true;roomToggle.dispatchEvent(new Event('change'));}
      help.textContent='Click or drag on the floor to lay unlit fuel. Nearby flames or Ignite fuel ignite it. Fully lit reveals cold patches. Shift/right-drag pans; scroll zooms.';
      message.textContent='Drop fuel · choose a floor point inside the simulation';
    }else describeSource();
  }
  on(view,'contextmenu',e=>e.preventDefault());
  on(view,'wheel',e=>{
    e.preventDefault();
    const delta=e.deltaY*(e.deltaMode===1?16:e.deltaMode===2?view.clientHeight:1);
    setZoom(viewZoom*Math.exp(-Math.max(-250,Math.min(250,delta))*.0015),e);
  },{passive:false});
  document.querySelector('#fire-tool').onclick=()=>setTool(false);
  document.querySelector('#pan-tool').onclick=()=>setTool(true);
  fuelToolControl.onclick=()=>setTool(false,true);
  document.querySelector('#ignite-fuel').onclick=()=>{if(sharedPresets.get(activePreset)?.smokeSimulation||activePreset==='smoke-burst'){message.textContent='Choose a fire source to ignite fuel.';return;}if(!groundFuel?.active&&!fuelBrush.dirty.size){message.textContent='Drop fuel on the floor first.';return;}groundFuel?.ignite();paused=false;captureAt=0;lastFrame=performance.now();document.querySelector('#pause').textContent='Pause';needsDraw=true;message.textContent='Fuel ignited · the finite patches burn down through normal combustion.';};
  clearFuelControl.onclick=()=>{fuelGesture=null;fuelBrush.clear();groundFuel?.clearFuel();syncFuelControls();needsDraw=true;message.textContent='Floor fuel cleared · existing fire and smoke continue.';};
  zoomControl.oninput=()=>setZoom(Number(zoomControl.value)/100);
  document.querySelector('#zoom-in').onclick=()=>setZoom(viewZoom+.25);
  document.querySelector('#zoom-out').onclick=()=>setZoom(viewZoom-.25);
  document.querySelector('#reset-view').onclick=()=>{endPan();viewZoom=1;panX=panY=0;viewAngle=16;updateView();};
  function focusSource(){
    if(!freeMode)return;
    const power=powerKind();
    const lift=power===4?1.45:power===3?-.7:power===1||power===5||power===6?.9:power===2?.4:emitterKind===3?.15:emitterKind===4?0:emitterKind===1||emitterKind===2?.65:emitterKind===6?1.65:1.1;
    panX=MINX+brush.x*WX;panY=MINY+brush.y*WY+lift-2.4;
    viewZoom=power?1.15:emitterKind===4?2.5:emitterKind===3?1.55:emitterKind===5?1.3:emitterKind===6?1.25:activePreset==='bonfire'?1.85:activePreset==='hearth'?2.5:2.25;
    updateView();
  }
  focusButton.onclick=focusSource;
  fullscreenButton.onclick=async()=>{
    try{if(document.fullscreenElement)await document.exitFullscreen();else await document.querySelector('main').requestFullscreen();}
    catch{message.textContent='Fullscreen is unavailable in this browser. Zoom and Move view are still available.';}
  };
  on(document,'fullscreenchange',()=>{fullscreenButton.textContent=document.fullscreenElement?'Exit fullscreen':'Fullscreen';needsDraw=true;});
  updateView();
  const updateLightLabel=()=>{
    sceneLabel.textContent=roomEnabled?(window.SceneLights.active?'Scene lighting · etched stone':'Fire-lit room · etched stone'):'Fire and smoke · black background';
    fireLightControl.disabled=!roomEnabled&&!window.SceneLights.active;
    document.querySelector('.fire-light-control small').textContent=fireLightControl.disabled
      ? 'Enable the room or scene lights to inspect fire illumination. Black view uses smoke inspection fill.'
      : 'Light cast by the flame onto smoke, props and the room.';
  };
  on(window,'scene-light-change',()=>{needsDraw=true;updateLightLabel();});
  updateLightLabel();
  roomToggle.onchange=()=>{
    roomLightRevision=-1;lightingRevision=-1;
    roomEnabled=roomToggle.checked;orbitControl.disabled=!roomEnabled;needsDraw=true;
    updateLightLabel();
  };
  orbitControl.oninput=()=>{viewAngle=Number(orbitControl.value);updateView();};
  document.querySelector('#pause').onclick = () => { paused = !paused;if(!paused){captureAt=0;lastFrame=performance.now();} document.querySelector('#pause').textContent = paused ? 'Resume' : 'Pause'; };
  extinguishButton.onclick = () => {
    brush.active = false;
    powerPool.stop();
    pointer.down = false; pointer.id = null;powerTrailLast=null;
    extinguishButton.disabled = true;
    message.textContent = woodState.enabled?'Ignition stopped · hot wood keeps burning':floorFuelPower()?'Casting stopped · the finite trail keeps burning':powerKind()?'Casting stopped · existing flame and smoke continue':'Fuel stopped · smoke continues to drift';
    paused = false; captureAt = 0;
    document.querySelector('#pause').textContent = 'Pause';
  };
  restartButton.onclick = () => selectPreset(presetControl.value,false,true).catch(onFailure);
  on(window,'keydown', e => {
    if(!scope.visible)return;
    if(e.ctrlKey||e.metaKey||e.altKey||e.repeat)return;
    if(e.target instanceof HTMLElement && (e.target.isContentEditable||e.target.matches('input,select,textarea')))return;
    const key=e.key.toLowerCase();
    if(e.code==='Space' && !(e.target instanceof HTMLElement && e.target.matches('button,a'))){e.preventDefault();document.querySelector('#pause').click();}
    else if(key==='r')restartButton.click();
    else if(key==='0')document.querySelector('#reset-view').click();
    else if(key==='+'||key==='='){e.preventDefault();setZoom(viewZoom+.25);}
    else if(key==='-'||key==='_'){e.preventDefault();setZoom(viewZoom-.25);}
    else if(key==='f')fullscreenButton.click();
    else if(key==='b'&&powerKind()){e.preventDefault();castPower();}
    else if(key==='escape'){setTool(false);pointer.down=false;pointer.id=null;}
  });
  const powerPrograms=new Map();
  let simProgram, renderProgram, presentProgram, diffuseProgram, targets, projected, sourceTexture, widthTexture, noiseTexture, pressure, advection, vorticity, smokeLight, room, current = 0;
  function frame(now) {
    probe.poll(paused);
    physicalClock.tick(now,scope.visible&&!paused);
    if(!scope.visible){lastFrame=now;scope.schedule(frame);return;}
    if(!frameQueue.ready()) {scope.schedule(frame);return;}
    const delta = physicalClock.debt; physicalClock.consume(delta); lastFrame = now;
    let steps = 0,advanced=0;
    const probing=!paused&&accumulator+delta>=(powerKind()?powerPool.temporalStep(STEP):STEP);if(probing)probe.begin();
    if (!paused) {
      accumulator += delta;
      while (steps < 2) {
        const step=powerKind()?powerPool.temporalStep(STEP):STEP;
        if(accumulator+1e-10<step)break;
        elapsed += step;
        if (!freeMode && elapsed > DURATION && !manualFuelSession && !woodState.enabled) { reset(); accumulator = STEP; }
        runStep(step); advanced+=step; accumulator=Math.max(0,accumulator-step); steps++;
        observedSteps++;
        if (captureAt > 0 && elapsed >= captureAt) { paused = true; document.querySelector('#pause').textContent = 'Resume'; break; }
      }
      // Keep bounded unconsumed simulation time across GPU waits.
      physicalClock.debt=Math.min(.25,physicalClock.debt+accumulator); accumulator=0;
    }
    const drawn=steps>0||needsDraw;
    if (drawn) { draw(); observedDraws++; needsDraw = false; }
    if(measurement){
      if(paused){measurement=null;benchmarkButton.disabled=false;document.querySelector('#gpu-status').textContent='Measurement stopped while paused.';}
      else {
        measurement.steps+=steps;measurement.simSeconds=(measurement.simSeconds||0)+advanced;
        if(drawn){
          if(measurement.last!==null)measurement.intervals.push(now-measurement.last);
          measurement.last=now;
          if(measurement.intervals.length===179){
            const duration=(now-measurement.start)/1000,sorted=[...measurement.intervals].sort((a,b)=>a-b);
            document.querySelector('#gpu-status').textContent=`Render submissions ${(179000/measurement.intervals.reduce((sum,v)=>sum+v,0)).toFixed(1)} fps · frame interval p95 ${sorted[Math.ceil(sorted.length*.95)-1].toFixed(1)} ms · ${(measurement.simSeconds/duration).toFixed(2)}× realtime. Browser frame pacing; GPU execution is not measured.`;
            measurement=null;benchmarkButton.disabled=false;
          }
        }
      }
    }
    if(probing)probe.end({time:elapsed,steps,drawn});
    if(drawn)frameQueue.submit();
    if (now - observedStart > 800) {
      const span = (now - observedStart) / 1000;
      const simRate = Math.round(observedSteps / span);
      const renderRate = Math.round(observedDraws / span);
      metrics.dataset.simulationLag=String(physicalClock.debt);
      metrics.dataset.droppedWallTime=String(physicalClock.dropped);
      metrics.textContent = `${paused ? 'paused' : `${simRate} sim steps/s · ${renderRate} rendered fps`} · ${elapsed.toFixed(1)} s · ${NX} × ${NZ} × ${DEPTH} cells`;
      observedSteps = 0; observedDraws = 0; observedStart = now;
    }
    scope.schedule(frame);
  }
  async function start() {
    try {
      if (AW > gl.getParameter(gl.MAX_TEXTURE_SIZE) || AH > gl.getParameter(gl.MAX_TEXTURE_SIZE)) {
        throw new Error('This GPU cannot fit the live fire volume');
      }
      pressure = CoarsePressure.setup(gl, { nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X, tilesY: TILES_Y, worldX:WX,worldZ:WY,worldY:WZ,coarseX:domain.blast?96:128,coarseZ:domain.blast?96:72,coarseDepth:domain.blast?32:8,iterations:domain.blast?24:18 });
      advection = MacCormackAdvection.setup(gl, {
        nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X, tilesY: TILES_Y,
        pressureSamplingGLSL: pressure.samplingGLSL
      });
      vorticity = FireVorticity.setup(gl, {nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X});
      smokeLight = SmokeLight.setup(gl, {nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X});
      room = FireRoom.setup(gl, {nx: NX, nz: NZ, depth: DEPTH, tilesX: TILES_X});
      groundFuel=createGroundFuelGL(gl,{...fuelBounds,shared,program:namedProgram('fuel guide'),uniform,bind,linear:halfFloatLinear});
      if(hasWood){
        woodState=createWoodStateGL(gl,{shared,program:namedProgram('wood state'),uniform,bind});
        woodMechanics=createWoodStructureGL(gl,{shared,program:namedProgram('wood mechanics'),uniform,bind});
        woodMesh=createWoodMeshGL(gl,{shared,lightingGLSL:room.surfaceGLSL,materialGLSL:window.WoodMaterialGLSL,program:namedProgram('wood mesh'),uniform,bind,width:RW,height:RH});
      }else{
        // No material inventory, fracture pipelines, meshes or asset loads
        // for gas-only scenes. Crossing this boundary remounts the runtime.
        const noop=()=>{};
        woodState={enabled:false,configure:noop,reset:noop,step:noop,bind:noop,destroy:noop};
        woodMechanics={ready:false,asset:null,configure:noop,reset:noop,step:noop,bind:noop,load:noop,destroy:noop};
        woodMesh={ready:false,draw:()=>false,load:noop,bind:p=>gl.uniform1f(uniform(p,'woodSurfaceVisible'),0),destroy:noop};
      }
      [simProgram,renderProgram,presentProgram,diffuseProgram]=await Promise.all([
        asyncProgram(simulation(),'Original combustion'),asyncProgram(rendering(),'Original volume render'),asyncProgram(presentation,'Original presentation'),asyncProgram(shaders.diffusion,'Original conservative mixing')
      ]);
      if(hasPowers)powerPrograms.set(powerDefinition(initialPreset).kind,simProgram);
      gl.bindVertexArray(gl.createVertexArray());
      targets = [target(), target()]; projected = projectionTarget();
      // Periodic smooth noise is sampled by the source and velocity fields.
      // It is a static turbulence basis, not prerecorded motion.
      const n = new Uint8Array(256 * 256 * 4);
      function hash(x, y, channel) {
        let v = (x * 374761393 + y * 668265263 + channel * 1442695041) >>> 0;
        v = Math.imul(v ^ (v >>> 13), 1274126177) >>> 0;
        return ((v ^ (v >>> 16)) >>> 0) / 4294967295;
      }
      function valueNoise(x, y, period, channel) {
        const xx = x * period / 256, yy = y * period / 256;
        const ix = Math.floor(xx), iy = Math.floor(yy);
        const fx = xx - ix, fy = yy - iy;
        const sx = fx * fx * (3 - 2 * fx), sy = fy * fy * (3 - 2 * fy);
        const a = hash(ix & (period - 1), iy & (period - 1), channel);
        const b = hash((ix + 1) & (period - 1), iy & (period - 1), channel);
        const c = hash(ix & (period - 1), (iy + 1) & (period - 1), channel);
        const d = hash((ix + 1) & (period - 1), (iy + 1) & (period - 1), channel);
        return (a + (b - a) * sx) * (1 - sy) + (c + (d - c) * sx) * sy;
      }
      for (let y = 0; y < 256; y++) for (let x = 0; x < 256; x++) for (let c = 0; c < 4; c++) {
        const v = .50 * valueNoise(x, y, 8, c) + .28 * valueNoise(x, y, 16, c)
                + .15 * valueNoise(x, y, 32, c) + .07 * valueNoise(x, y, 64, c);
        n[(y * 256 + x) * 4 + c] = Math.max(0, Math.min(255, Math.round(v * 255)));
      }
      noiseTexture = texture(256, 256, n);
      gl.bindTexture(gl.TEXTURE_2D, noiseTexture);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
      turbulenceTexture=gl.createTexture();gl.bindTexture(gl.TEXTURE_3D,turbulenceTexture);
      for(const axis of [gl.TEXTURE_WRAP_S,gl.TEXTURE_WRAP_T,gl.TEXTURE_WRAP_R])gl.texParameteri(gl.TEXTURE_3D,axis,gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_3D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_3D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      const turbulence=new Uint8Array(64*64*64*4);
      for(let z=0;z<64;z++)for(let y=0;y<64;y++)for(let x=0;x<64;x++)for(let c=0;c<4;c++)
        turbulence[((z*64+y)*64+x)*4+c]=Math.round(hash(x+z*71,y+z*37,c)*255);
      gl.texImage3D(gl.TEXTURE_3D,0,gl.RGBA8,64,64,64,0,gl.RGBA,gl.UNSIGNED_BYTE,turbulence);
      emptyObjectTexture=gl.createTexture();gl.bindTexture(gl.TEXTURE_3D,emptyObjectTexture);
      gl.texParameteri(gl.TEXTURE_3D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_3D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
      gl.texImage3D(gl.TEXTURE_3D,0,gl.RGBA16F,1,1,1,0,gl.RGBA,gl.HALF_FLOAT,new Uint16Array([0x4900,0,0,0]));
      objectTexture=emptyObjectTexture;
      if(hasPowers){
        sourceTexture=texture(1,1,new Uint8Array(4));
        widthTexture=texture(1,1,new Uint8Array(1),gl.LINEAR,gl.R8,gl.RED,gl.UNSIGNED_BYTE);
      }else{
      const [sourceBytes, widthBytes] = await Promise.all([
        fetch('source/source-native.rgba8.bin').then(r => { if (!r.ok) throw new Error('Source field missing'); return r.arrayBuffer(); }),
        fetch('source/halfwidth-native.r8.bin').then(r => { if (!r.ok) throw new Error('Source thickness missing'); return r.arrayBuffer(); })
      ]);
      if (sourceBytes.byteLength !== SOURCE_NX * SOURCE_NZ * 4 || widthBytes.byteLength !== SOURCE_NX * SOURCE_NZ) throw new Error('Source field size mismatch');
      const sourcePixels = new Uint8Array(sourceBytes);
      sourceTexture = texture(SOURCE_NX, SOURCE_NZ, sourcePixels);
      widthTexture = texture(SOURCE_NX, SOURCE_NZ, new Uint8Array(widthBytes), gl.LINEAR, gl.R8, gl.RED, gl.UNSIGNED_BYTE);
      }
      // The volume projection is 896x504. A 1920x1080 drawing buffer only
      // upscaled that image while making the presentation pass shade 4.6x as
      // many pixels. Keep the output at the projection's native detail.
      canvas.width = RW; canvas.height = RH;
      const pendingBrush = brush.active;
      reset();
      if (freeMode && pendingBrush) brush.active = true;
      message.textContent = freeMode
        ? pendingBrush ? 'Free fire · drag to move the source' : 'Free fire · click to ignite'
        : 'Live GPU simulation · click to create fire';
      if(freeMode && pendingBrush)describeSource();
      const initialParams=new URL(location.href).searchParams;
      await selectPreset(initialPreset);
      if(initialParams.has('fuel')&&fuelProfiles[initialParams.get('fuel')])fuelControl.value=initialParams.get('fuel');
      setFireLight(fireLight);
      scope.schedule(frame);
    } catch (err) {
      await scope.stop();
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      throw err;
    }
  }
  on(canvas,'webglcontextlost', e => { e.preventDefault(); scope.setVisible(false); onFailure(new Error('The GPU context was lost. Try again to restart the simulation.')); });
  on(canvas,'webglcontextrestored', () => location.reload());
  await start();
  return {
    async dispose(){await scope.stop();frameQueue.dispose();groundFuel.destroy();woodState.destroy();woodMechanics.destroy();woodMesh.destroy();gl.getExtension('WEBGL_lose_context')?.loseContext();},
    setVisible(value){if(!value)cancelMeasurement();scope.setVisible(value);},
    fire:selectPreset,
    castPower,
    abilityState:()=>powerPool.snapshot(),
    inspectState:()=>{if(!paused)throw Error('Pause before reading diagnostic state');return {time:elapsed,woodTimeScale,wood:woodState.inspect?.()};},
    aimPower:(target,direction)=>powerPool.aim(target,direction),
    releasePower:(target,direction)=>powerPool.release(target,direction),
    cancelPower:()=>powerPool.cancelHeld(),
    snapshot:()=>({fire:'legacy:'+activePreset,fuel:fuelControl.value,smoke:inspectSmoke,color:flameColor,fireLight,woodTimeScale,powers:{...powers},ability:powerPool.snapshot(),room:roomEnabled,sourceGuide,tool:fuelTool?'fuel':panTool?'pan':'fire',camera:{zoom:viewZoom,angle:viewAngle,pan:[panX,panY]}}),
    look(item){
      if(item.powers){powers=normalizePowerSettings({...powers,...item.powers});powerPool.updateContinuous({direction:powerDirection(powers),strength:powers.strength});}
      if(typeof item.sourceGuide==='boolean'){sourceGuide=item.sourceGuide;guideControl.checked=sourceGuide;needsDraw=true;}
      if(item.woodTimeScale!==undefined)setWoodSpeed(item.woodTimeScale);
      if(item.tool)setTool(item.tool==='pan',item.tool==='fuel');
      if(item.fuel)fuelControl.value=item.fuel;
      if(FIRE_COLORS.some(c=>c.id===item.color)){flameColor=item.color;colorControl.value=flameColor;markAppearance();}
      if(typeof item.smoke==='boolean'){inspectSmoke=item.smoke;smokeControl.checked=inspectSmoke;needsDraw=true;}
      if(item.fireLight!==undefined)setFireLight(item.fireLight);
      if(typeof item.room==='boolean'){roomToggle.checked=item.room;roomToggle.dispatchEvent(new Event('change'));}
      if(item.camera){viewZoom=item.camera.zoom??viewZoom;viewAngle=Math.max(-30,Math.min(30,item.camera.angle??viewAngle));[panX,panY]=item.camera.pan??[panX,panY];updateView();}
    }
  };
}
