(function(){
'use strict';
const Q=new URLSearchParams(location.search),capture=Q.has('capture')||window.__CAPTURE__;
if(capture)document.body.classList.add('capture');
const $=id=>document.getElementById(id),names={breach:['BREACH','Dam release · monolith collision · returning bore'],impact:['IMPACT','Liquid drop · shallow pool · radial splash'],jets:['CONFLUENCE','Continuous emitters · colliding jets · breakup'],cascade:['CASCADE','Stepped spillway · falling sheets · plunge pool'],slosh:['IMPULSE','Basin slosh · lateral momentum · wall run-up'],vortex:['VORTEX','Angular flow · free surface · circulation'],paddle:['DISPLACEMENT','Moving solid · relative wall velocity · wake'],capillary:['CAPILLARY','Zero gravity · surface tension · oscillating drop'],viscous:['VISCOUS','Symmetric-strain viscosity · thick stream · solid contact'],hero:['HERO','Dam impact · detailed free surface · two-way free body'],buoy:['BUOYANCY','Pressure force · floating body · momentum exchange']};
let activePreset=null;
const defaultFlip={breach:.93,impact:.93,jets:.93,cascade:.93,slosh:.93,vortex:.93,paddle:.93,capillary:.12,viscous:.1,hero:.93,buoy:.93};
let parameters=null,tracer=null,tracing=false,traceCamera="",mediaRecorder=null,recordedChunks=[],recordTimer=null,recordCanvas=null,recordContext=null;
let gpu=null,resident=null,pendingReject=null;
let renderer,manifest,scene=Q.get('scene')||window.__SCENE__||'breach',execution='live',frame=-1,paused=false,busy=false,worker,ready=false,lastWall=performance.now(),latestMetrics={},liveConfig,pendingStep=null;
const memo=new Map(),workerRequests=new Map();let requestSerial=0;
async function whenIdle(timeout=30000){const start=performance.now();while(busy){if(window.CYBR_ERROR)throw Error(window.CYBR_ERROR);if(performance.now()-start>timeout)throw Error('The current simulation step has not completed.');await new Promise(r=>setTimeout(r,15));}}
async function saveCheckpoint(){paused=true;await whenIdle();if(!worker||execution!=='live')throw Error('Full checkpoints require the CPU reference backend.');return new Promise((resolve,reject)=>{const requestId=++requestSerial;workerRequests.set(requestId,{resolve,reject});worker.postMessage({type:'saveCheckpoint',requestId,appState:{shot:renderer.shot,optics:renderer.opticsMode,orbit:renderer.orbit,mode:renderer.mode,exposure:renderer.renderer.toneMappingExposure,ior:renderer.material.uniforms.uIOR.value,absorption:renderer.material.uniforms.uAbsorption.value.toArray()}});});}
async function loadCheckpoint(buffer){if(!(buffer instanceof ArrayBuffer))throw Error('Checkpoint must be an ArrayBuffer.');paused=true;await whenIdle();if(!worker)throw Error('Initialize the CPU backend first.');resident?.dispose();resident=null;gpu?.dispose();gpu=null;execution='live';busy=true;return new Promise((resolve,reject)=>{pendingStep=resolve;pendingReject=reject;worker.postMessage({type:'loadCheckpoint',buffer},[buffer]);});}

function fail(e){busy=false;paused=true;for(const request of workerRequests.values())request.reject(e);workerRequests.clear();if(pendingReject){pendingReject(e);pendingReject=null;pendingStep=null;}console.error(e);$('loading').textContent=e.message||String(e);window.CYBR_ERROR=e.message||String(e);}
function label(){const n=names[scene];$('title').textContent=n[0];$('subtitle').textContent=n[1];$('sceneSelect').value=scene;$('shotName').textContent=n[1].replaceAll(' · ',' / ').toUpperCase();}
function updateHUD(m){latestMetrics=m;$('particleCount').textContent=(m.particles||0).toLocaleString();$('gridSize').textContent=(m.grid||[0,0,0]).join(' × ');$('simTime').textContent=(m.time||0).toFixed(3);$('projection').textContent=m.divergenceBefore>1e-9?`${(100*(1-m.divergenceAfter/m.divergenceBefore)).toFixed(1)}% ↓`:'—';}
async function unpack(response,config){
 let bytes;if(response instanceof ArrayBuffer)bytes=response;else{if(!response.ok)throw Error(`Geometry fetch failed (${response.status})`);bytes=await response.arrayBuffer();}
 const stream=new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
 const buf=await new Response(stream).arrayBuffer(),dv=new DataView(buf);let offset=24;
 const magic=dv.getUint32(0,true);if(magic!==0x43465231&&magic!==0x43465232&&magic!==0x43465233&&magic!==0x43465234)throw Error('Invalid mesh cache magic');
 const nv=dv.getUint32(4,true),nf=dv.getUint32(8,true),nd=dv.getUint32(12,true),nw=dv.getUint32(16,true),np=dv.getUint32(20,true),extent=config.extent;
 let causticWidth=0,causticHeight=0;if(magic===0x43465233||magic===0x43465234){causticWidth=dv.getUint32(24,true);causticHeight=dv.getUint32(28,true);offset=32;}
 function positions(n){const p=new Float32Array(n*3);for(let i=0;i<n*3;i++)p[i]=dv.getUint16(offset+i*2,true)/65535*extent[i%3];offset+=n*6;return p;}
 const p=positions(nv),normal=new Float32Array(nv*3);for(let i=0;i<nv*3;i++)normal[i]=dv.getInt16(offset+i*2,true)/32767;offset+=nv*6;
 const foam=new Float32Array(nv);if(magic===0x43465232||magic===0x43465233||magic===0x43465234){for(let i=0;i<nv;i++)foam[i]=dv.getUint8(offset+i)/255;offset+=nv;}
 const index=new Uint32Array(nf*3);for(let i=0;i<nf*3;i++)index[i]=dv.getUint32(offset+i*4,true);offset+=nf*12;
 const drops=positions(nd),dropRadii=new Float32Array(nd);if(magic===0x43465234){for(let i=0;i<nd;i++)dropRadii[i]=dv.getFloat32(offset+i*4,true);offset+=nd*4;}else dropRadii.fill(config.h*Math.cbrt(3/(32*Math.PI)));const white=new Float32Array(nw*6);for(let i=0;i<nw*6;i++)white[i]=dv.getFloat32(offset+i*4,true);offset+=nw*24;
 const diagnostic=positions(np);let caustic=null;if(causticWidth){caustic=new Uint8Array(buf.slice(offset,offset+causticWidth*causticHeight*2));offset+=causticWidth*causticHeight*2;}if(offset!==buf.byteLength)throw Error('Mesh cache length mismatch');
 return {positions:p,normals:normal,indices:index,drops,dropRadii,white,diagnostic,foam,caustic,causticWidth,causticHeight};
}
async function selectCache(name){
 stopTrace();resident?.dispose();resident=null;gpu?.dispose();gpu=null;
 worker?.terminate();worker=null;scene=name;label();ready=false;$('loading').classList.remove('hidden');$('loading').textContent='LOADING SIMULATED GEOMETRY…';
 if(window.__LOCAL_MANIFESTS__?.[name])manifest=window.__LOCAL_MANIFESTS__[name];else{const res=await fetch(`cache/${name}/manifest.json`);if(!res.ok)throw Error('High-resolution cache is not included. Select Live CPU FLIP.');manifest=await res.json();}renderer.setup(manifest.config);renderer.setRasterProfile(manifest.config.rasterProfile??'repair');renderer.opticsMode='raster';frame=-1;memo.clear();execution='cache';$('quality').disabled=true;$('flipRatio').disabled=true;$('flipFooter').textContent=`${Math.round(manifest.config.flip*100)}% FLIP`;$('execution').value='cache';await loadFrame(0);ready=true;$('loading').classList.add('hidden');$('playbackLabel').textContent='SIMULATION CACHE / 0.5×';return manifest;
}
async function loadFrame(f){
 if(!manifest)throw Error('No simulation cache is loaded');f=Math.max(0,Math.min(manifest.frames.length-1,Math.floor(f)));
 let data=memo.get(f);if(!data){let input;if(window.__readCache){const b64=await window.__readCache(scene,f);input=Uint8Array.from(atob(b64),c=>c.charCodeAt(0)).buffer;}else input=await fetch(`cache/${scene}/${String(f).padStart(4,'0')}.mesh.gz`);data=await unpack(input,manifest.config);memo.set(f,data);if(memo.size>2)memo.delete(memo.keys().next().value);}
 renderer.setFrame(data);renderer.setMetrics(manifest.frames[f]);frame=f;updateHUD(manifest.frames[f]);if(!window.__DEFER_CAPTURE_RENDER__)renderer.draw(f/manifest.frames.length);return {frame:f,...renderer.info(),metrics:latestMetrics};
}
async function advanceGPUFrame(dt){
 if(!gpu||!worker)throw Error('Sparse GPU solver is unavailable.');
 gpu.config.flip=Number($('flipRatio').value);
 const start=performance.now(),metrics=await gpu.advance(dt);
 if(resident){
  const surface=resident.update(),combined={...metrics,surface,gpuFrameWallMs:performance.now()-start,flip:gpu.config.flip};
  updateHUD(combined);renderer.setMetrics(combined);renderer.draw();frame++;ready=true;busy=false;$('loading').classList.add('hidden');
  $('playbackLabel').textContent='LIVE / GPU SOLVER + GPU SURFACE';$('bottomNote').textContent='GPU AFFINE FLIP / GPU PCG / RESIDENT TETRAHEDRA';
  $('timing').textContent=`GPU pipeline: ${combined.gpuFrameWallMs.toFixed(0)} ms · primary readback ${surface.primaryReadbackBytes} bytes`;
  if(pendingStep){pendingStep(combined);pendingStep=null;pendingReject=null;}return;
 }
 const snapshot=gpu.readState(false,true);
 snapshot.metrics={...snapshot.metrics,substeps:metrics.substeps,gpuFrameWallMs:performance.now()-start,flip:gpu.config.flip};
 const transfer=[snapshot.positions.buffer,snapshot.velocities.buffer];
 if(snapshot.grid)transfer.push(snapshot.grid.values.buffer,snapshot.grid.blocks.buffer);
 worker.postMessage({type:'gpuFrame',positions:snapshot.positions,velocities:snapshot.velocities,grid:snapshot.grid,metrics:snapshot.metrics,dt},transfer);
}
async function selectGPU(name){return selectLive(name,'gpu');}
async function selectLive(name,backend='live'){
 if(!['live','gpu','resident'].includes(backend))throw Error('Unknown live backend.');
 if(backend!=='live'&&['hero','buoy'].includes(name))throw Error('Dynamic-body coupling is currently supported by the CPU reference backend.');
 stopTrace();resident?.dispose();resident=null;gpu?.dispose();gpu=null;window.CYBR_ERROR=null;
 if(activePreset!==name){parameters=null;activePreset=name;$('flipRatio').value=defaultFlip[name];$('flipValue').textContent=defaultFlip[name].toFixed(2);}
 worker?.terminate();frame=-1;scene=name;label();execution=backend;$('quality').disabled=false;$('flipRatio').disabled=false;$('flipFooter').textContent=`${Math.round(Number($('flipRatio').value)*100)}% FLIP`;$('execution').value=backend;ready=false;$('loading').classList.remove('hidden');$('loading').textContent=backend!=='live'?'COMPILING SPARSE GPU FLIP…':'STARTING 3D FLIP SOLVER…';
 if(window.__WORKER_SOURCE__){const url=URL.createObjectURL(new Blob([window.__WORKER_SOURCE__],{type:'text/javascript'}));worker=new Worker(url);URL.revokeObjectURL(url);}
 else worker=new Worker('src/worker.js',{type:'module'});
 worker.onmessage=e=>{
  try{
   const d=e.data;if(d.requestId&&workerRequests.has(d.requestId)){workerRequests.get(d.requestId).resolve(d.checkpoint);workerRequests.delete(d.requestId);return;}if(d.restored){execution='live';$('execution').value='live';scene=d.config.nameKey;activePreset=scene;label();$('flipRatio').value=d.restoredFlip??d.config.flip;$('flipValue').textContent=Number(d.restoredFlip??d.config.flip).toFixed(2);$('flipFooter').textContent=`${Math.round(d.config.flip*100)}% FLIP`;parameters={surfaceTension:d.config.surfaceTension,kinematicViscosity:d.config.kinematicViscosity,pressureTolerance:d.config.pressureTolerance,affine:d.config.affine};frame=-1;}if(d.error){fail(Error(d.error));return;}
   if(d.config){liveConfig=d.config;renderer.setup(d.config);$('surfaceTension').value=d.config.surfaceTension??0;$('viscosity').value=d.config.kinematicViscosity??0;$('tolerance').value=d.config.pressureTolerance??.00002;$('affine').checked=d.config.affine!==false;}
   if(d.restored&&d.appState){renderer.setShot(d.appState.shot??0);renderer.opticsMode=d.appState.optics??'raster';renderer.orbit=d.appState.orbit??null;renderer.renderer.toneMappingExposure=d.appState.exposure??1.04;renderer.material.uniforms.uIOR.value=d.appState.ior??1.333;if(d.appState.absorption)renderer.material.uniforms.uAbsorption.value.set(...d.appState.absorption);renderer.setMode(d.appState.mode??'water');}
   if(d.gpuSeed){gpu=new SparseGPUFLIP(renderer.renderer,liveConfig,d.gpuSeed.positions,d.gpuSeed.velocities,{randomState:d.gpuSeed.randomState,emitCarry:d.gpuSeed.emitCarry});if(execution==='resident')resident=new ResidentSurface(renderer,gpu);advanceGPUFrame(1/48).catch(fail);}
   if(d.geometry){
    renderer.setFrame(d.geometry);renderer.setMetrics(d.metrics);updateHUD(d.metrics);renderer.draw();frame++;ready=true;busy=false;$('loading').classList.add('hidden');
    $('timing').textContent=execution==='gpu'?`Sparse GPU: ${(d.metrics.gpuFrameWallMs??0).toFixed(0)} ms · CPU preview: ${d.wallMs.toFixed(0)} ms · ${d.metrics.activeBricks} bricks`:`Solver + surface: ${d.wallMs.toFixed(0)} ms / step · ${d.metrics.steps} substeps`;
    $('playbackLabel').textContent=execution==='gpu'?'LIVE / SPARSE GPU FLIP':'LIVE / QUADRATIC FLIP + MG-PCG';
    if(pendingStep){pendingStep(d.metrics);pendingStep=null;pendingReject=null;}
   }
  }catch(error){fail(error);}
 };
 worker.onerror=e=>fail(Error(e.message));busy=true;worker.postMessage({type:backend!=='live'?'initGPU':'init',name,quality:$('quality').value,flip:Number($('flipRatio').value),parameters});
}
function selectedLive(name){return selectLive(name,['gpu','resident'].includes(execution)?execution:'live');}
async function tick(){
 try{if(!capture&&ready&&!paused&&!busy){
  if(execution==='cache'){busy=true;await loadFrame((frame+1)%manifest.frames.length);busy=false;}
  else if(worker){busy=true;if(execution==='gpu'||execution==='resident')await advanceGPUFrame(1/48);else worker.postMessage({type:'step',dt:1/48,flip:Number($('flipRatio').value)});}
 }}catch(e){paused=true;busy=false;fail(e);}if(!capture)setTimeout(tick,execution==='cache'?41:12);
}
function download(data,name,type='application/octet-stream'){
 const blob=data instanceof Blob?data:new Blob([data],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);
}
function stopTrace(){tracing=false;tracer?.dispose();tracer=null;if($('traceStatus'))$('traceStatus').textContent='Reference tracing paused.';}
async function startTrace(){
 paused=true;$('pause').textContent='Play';while(busy)await new Promise(r=>setTimeout(r,20));stopTrace();tracer=new ReferencePathTracer(renderer);const stats=tracer.build();tracing=true;traceCamera='';
 function renderSample(){
  if(!tracing)return;
  try{renderer.updateCamera(frame/120);renderer.camera.updateMatrixWorld();const signature=renderer.camera.matrixWorld.elements.join(',')+renderer.camera.fov;if(signature!==traceCamera){tracer.resetCamera();traceCamera=signature;}
   if(tracer.uniforms.uResolution.value.x!==renderer.width||tracer.uniforms.uResolution.value.y!==renderer.height)tracer.resize(renderer.width,renderer.height);
   const info=tracer.sample();$('traceStatus').textContent=`${info.samples} samples / pixel · ${stats.primitiveCount.toLocaleString()} BVH primitives · 10 bounces`;$('playbackLabel').textContent='PROGRESSIVE REFERENCE / '+info.samples+' SPP';
  }catch(e){stopTrace();fail(e);return;}requestAnimationFrame(renderSample);
 }requestAnimationFrame(renderSample);return stats;
}
function exportOBJ(){
 const d=renderer.latest;if(!d?.positions?.length)throw Error('No liquid mesh is loaded.');const out=['# CYBR FLIP III.1 / metres / current reconstructed mesh','o liquid'];
 for(let i=0;i<d.positions.length;i+=3)out.push(`v ${d.positions[i]} ${d.positions[i+1]} ${d.positions[i+2]}`);
 for(let i=0;i<d.normals.length;i+=3)out.push(`vn ${d.normals[i]} ${d.normals[i+1]} ${d.normals[i+2]}`);
 for(let i=0;i<d.indices.length;i+=3){const a=d.indices[i]+1,b=d.indices[i+1]+1,c=d.indices[i+2]+1;out.push(`f ${a}//${a} ${b}//${b} ${c}//${c}`);}download(out.join('\n'),`${scene}_${frame}.obj`,'text/plain');return {vertices:d.positions.length/3,triangles:d.indices.length/3};
}
function exportPLY(){
 const p=renderer.latest.diagnostic,n=p.length/3,out=['ply','format ascii 1.0','comment CYBR FLIP III.1 uniformly subsampled PRIMARY particles; metres',`element vertex ${n}`,'property float x','property float y','property float z','end_header'];
 for(let i=0;i<p.length;i+=3)out.push(`${p[i]} ${p[i+1]} ${p[i+2]}`);download(out.join('\n'),`${scene}_${frame}_sampled_particles.ply`,'text/plain');return {particles:n};
}
function settings(){return {schema:'cybr-flip-settings/2',backend:['gpu','resident'].includes(execution)?execution:'live',scene,quality:$('quality').value,flip:Number($('flipRatio').value),parameters:{surfaceTension:Number($('surfaceTension').value),kinematicViscosity:Number($('viscosity').value),pressureTolerance:Number($('tolerance').value),affine:$('affine').checked},note:'Initial-condition settings; not a simulation checkpoint.'};}
async function restoreSettings(data){
 if(data.schema!=='cybr-flip-settings/2'||!names[data.scene])throw Error('Unsupported project settings.');if(!['live','high','ultra'].includes(data.quality))throw Error('Unsupported quality.');if(!Number.isFinite(data.flip)||data.flip<0||data.flip>1)throw Error('Invalid FLIP fraction.');
 activePreset=data.scene;parameters=data.parameters??{};$('quality').value=data.quality;$('flipRatio').value=data.flip;await selectLive(data.scene,['gpu','resident'].includes(data.backend)?data.backend:'live');
}
async function main(){
 renderer=new LiquidRenderer($('view'));label();
 if(window.__STANDALONE__){const opt=$('execution').querySelector('[value=cache]');opt.disabled=true;opt.textContent='Cache playback requires the complete package';}
 window.CYBR={saveCheckpoint,loadCheckpoint,whenIdle,startTrace,stopTrace,exportOBJ,exportPLY,settings,restoreSettings,get ready(){return ready;},get renderer(){return renderer;},setOptics:mode=>{if(!['raster','bvh'].includes(mode))throw Error('Unknown optics mode');renderer.opticsMode=mode;if(mode==='raster')renderer.setMode(renderer.mode);renderer.draw();},selectCache,selectLive,selectGPU,loadFrame,get gpu(){return gpu;},get resident(){return resident;},
  setShot:n=>{renderer.setShot(n);$('tag').textContent=`0${n+1} / ${n===2?'OVERHEAD STUDY':n===1?'SURFACE STUDY':'VOLUMETRIC STUDY'}`;renderer.draw(frame/(manifest?.frames.length??120));},
  setMode:m=>{renderer.setMode(m);if(resident)resident.update();$('display').value=m;$('bottomNote').textContent=m==='particles'?'ACTUAL LIQUID POSITIONS / UNIFORMLY SUBSAMPLED':m==='normal'?'GEOMETRIC SURFACE NORMALS / NO WAVE DISPLACEMENT':'QUADRATIC APIC → MULTIGRID → DETAIL-PRESERVING SURFACE';renderer.draw(frame/120);},
  resize:(w,h)=>{renderer.resize(w,h);renderer.draw(frame/120);},draw:()=>renderer.draw(frame/120),
  inspect:()=>({...renderer.info(),scene,execution,frame,metrics:latestMetrics,ready}),setPaused:value=>paused=value,stepLive:(dt=1/48)=>new Promise((resolve,reject)=>{if(!worker||busy){reject(Error('Live worker is busy or unavailable'));return;}pendingStep=resolve;pendingReject=reject;busy=true;if(execution==='gpu'||execution==='resident')advanceGPUFrame(dt).catch(fail);else worker.postMessage({type:'step',dt,flip:Number($('flipRatio').value)});}),
  get config(){return execution==='cache'?manifest.config:liveConfig;}
 };
 window.addEventListener('resize',()=>{if(!capture){renderer.resize(innerWidth,innerHeight);renderer.draw();}});
 $('geometryOptics').onclick=()=>{try{paused=true;stopTrace();window.CYBR.setOptics('bvh');$('playbackLabel').textContent='ACTUAL GEOMETRY / BOUNDED BVH OPTICS';}catch(e){fail(e);}};
 $('trace').onclick=()=>startTrace().catch(fail);$('raster').onclick=()=>{stopTrace();window.CYBR.setOptics('raster');renderer.draw(frame/120);$('playbackLabel').textContent=execution==='cache'?'SIMULATION CACHE / 0.5×':execution==='gpu'?'LIVE / SPARSE GPU FLIP':'LIVE / QUADRATIC FLIP + MG-PCG';};
 $('applyPhysics').onclick=()=>{parameters=settings().parameters;selectedLive(scene).catch(fail);};
 $('saveObj').onclick=()=>{try{exportOBJ();}catch(e){fail(e);}};$('savePly').onclick=()=>{try{exportPLY();}catch(e){fail(e);}};
 $('savePng').onclick=()=>$('view').toBlob(b=>download(b,`${scene}_${frame}.png`),'image/png');
 $('saveProject').onclick=()=>download(JSON.stringify(settings(),null,2),'CYBR_FLIP_III_settings.json','application/json');
 $('loadProject').onclick=()=>$('projectInput').click();$('projectInput').onchange=async e=>{try{await restoreSettings(JSON.parse(await e.target.files[0].text()));}catch(error){fail(error);}};
 $('record').onclick=()=>{try{if(mediaRecorder?.state==='recording'){mediaRecorder.stop();$('record').textContent='Record WebM';return;}const type=['video/webm;codecs=vp8','video/webm;codecs=vp9','video/webm'].find(x=>MediaRecorder.isTypeSupported(x));if(!type)throw Error('This browser does not provide a supported WebM encoder.');recordedChunks=[];recordCanvas=document.createElement('canvas');recordCanvas.width=renderer.width;recordCanvas.height=renderer.height;recordContext=recordCanvas.getContext('2d');recordContext.drawImage($('view'),0,0);mediaRecorder=new MediaRecorder(recordCanvas.captureStream(0),{mimeType:type,videoBitsPerSecond:12000000});mediaRecorder.ondataavailable=e=>{if(e.data.size)recordedChunks.push(e.data);};mediaRecorder.onerror=e=>{clearInterval(recordTimer);fail(Error('WebM encoder: '+(e.error?.message??'unknown error')));};mediaRecorder.onstop=()=>{clearInterval(recordTimer);download(new Blob(recordedChunks,{type}),'CYBR_FLIP_III_browser_recording.webm',type);mediaRecorder.stream.getTracks().forEach(t=>t.stop());};mediaRecorder.start(250);const track=mediaRecorder.stream.getVideoTracks()[0];recordTimer=setInterval(()=>{if(!tracing)renderer.draw(frame/120);renderer.renderer.getContext().finish();recordContext.drawImage($('view'),0,0,recordCanvas.width,recordCanvas.height);track.requestFrame?.();},1000/24);$('record').textContent='Stop recording';}catch(e){fail(e);}};
 $('quality').onchange=()=>selectedLive(scene).catch(fail);
 $('sceneSelect').onchange=()=>{(execution==='cache'?selectCache:selectedLive)($('sceneSelect').value).catch(fail);};
 $('execution').onchange=()=>{const mode=$('execution').value;(mode==='cache'?selectCache(scene):selectLive(scene,mode)).catch(fail);};
 $('display').onchange=()=>window.CYBR.setMode($('display').value);
 $('pause').onclick=()=>{if(tracing)stopTrace();$('pause').textContent=(paused=!paused)?'Play':'Pause';};
 $('reset').onclick=()=>{(execution==='cache'?selectCache:selectedLive)(scene).catch(fail);};
 $('camera').onclick=()=>window.CYBR.setShot((renderer.shot+1)%3);
 $('flipRatio').oninput=()=>{const v=Number($('flipRatio').value);$('flipValue').textContent=v.toFixed(2);$('flipFooter').textContent=`${Math.round(v*100)}% FLIP`;};
 if((capture&&!window.__CAPTURE_LIVE__)||Q.get('mode')==='cache')await selectCache(scene);else await selectLive(scene,Q.get('mode')==='resident'||window.__CAPTURE_RESIDENT__?'resident':Q.get('mode')==='gpu'||window.__CAPTURE_GPU__?'gpu':'live');
 if(!capture)tick();
}
main().catch(fail);
})();
