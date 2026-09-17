import {FlipSolver} from './flip.js';
import {makePreset} from './quality-profile.js';
import {encodeCheckpoint,decodeCheckpoint} from './checkpoint.js';
import {SurfaceBuilder,SecondaryParticles} from './surface.js';
let sim,surface,secondary,backend='cpu';
function configuredPreset(m){
 const config=makePreset(m.name,m.quality??'live'),p=m.parameters;
 if(p){
  if(Array.isArray(p.gravity)&&p.gravity.length===3&&p.gravity.every(Number.isFinite))config.gravity=p.gravity.map(x=>Math.max(-100,Math.min(100,x)));
  if(Number.isFinite(p.surfaceTension))config.surfaceTension=Math.max(0,Math.min(2,p.surfaceTension));
  if(Number.isFinite(p.kinematicViscosity))config.kinematicViscosity=Math.max(0,Math.min(1,p.kinematicViscosity));
  if(Number.isFinite(p.pressureTolerance))config.pressureTolerance=Math.max(1e-7,Math.min(.01,p.pressureTolerance));
  if(typeof p.affine==='boolean')config.affine=p.affine;
 }
 if(Number.isFinite(m.flip))config.flip=Math.max(0,Math.min(1,m.flip));
 return config;
}
function sendGeometry(metrics,dt,start){
 surface.density(sim.p,sim.count);
 const savedIso=surface.iso;let white;if(dt===0){white=new Float32Array(secondary.items.length*6);secondary.items.forEach((a,i)=>white.set([a.x,a.y,a.z,a.radius,a.mode,Math.min(1,a.life/.25,(a.life0-a.life)/.12)],i*6));}else white=secondary.advance(sim,surface,dt);const geometry=surface.mesh(sim.p,sim.count,white);if(dt===0)surface.iso=savedIso;
 metrics.surface=surface.lastMeshStats;
 metrics.whitewater={count:white.length/6,births:secondary.births,transitions:secondary.transitions};
 const transfer=Object.values(geometry).map(a=>a.buffer);
 postMessage({geometry,metrics,wallMs:performance.now()-start},transfer);
}
function sendCPUFrame(dt){
 const start=performance.now(),metrics=sim.advance(dt);metrics.flip=sim.flip;
 sendGeometry(metrics,dt,start);
}
function receiveGPUFrame(m){
 if(backend!=='gpu'||!sim)throw Error('Initialize the sparse GPU preview before sending GPU state.');
 if(!(m.positions instanceof Float32Array)||m.positions.length%3||m.positions.length!==m.velocities.length)throw Error('Invalid GPU primary state.');
 const start=performance.now(),count=m.positions.length/3;
 if(count>sim.maxParticles)throw Error('GPU primary state exceeds the preview capacity.');
 // These arrays are readbacks of the GPU solver, NOT a second CPU simulation.
 sim.count=count;sim.p.set(m.positions);sim.v.set(m.velocities);sim.time=m.metrics.time;
 sim.obstacles=structuredClone(m.metrics.colliders??[]);
 for(const u of sim.u)u.fill(0);
 if(m.grid){
  const {values,blocks,atlasSize,atlasColumns}=m.grid,width=atlasSize[0];
  if(values.length!==width*atlasSize[1]*4||blocks.length%4)throw Error('Invalid sparse MAC preview atlas.');
  for(let b=0;b<blocks.length/4;b++){
   const ox=blocks[b*4]*8,oy=blocks[b*4+1]*8,oz=blocks[b*4+2]*8;
   for(let z=0;z<8;z++)for(let y=0;y<8;y++)for(let x=0;x<8;x++){
    const gx=ox+x,gy=oy+y,gz=oz+z;if(gx>sim.nx||gy>sim.ny||gz>sim.nz)continue;
    const texel=((Math.floor(b/atlasColumns)*8+z)*width+(b%atlasColumns)*64+x+8*y)*4,id=gx*sim.sx+gy*sim.sy+gz;
    for(let c=0;c<3;c++)sim.u[c][id]=values[texel+c];
   }
  }
 }
 const metrics={...m.metrics,primaryCPUAdvectionSteps:sim.steps,previewProcessing:'CPU surface reconstruction and one-way diffuse particles'};
 if(sim.steps!==0)throw Error('GPU preview unexpectedly advanced the CPU primary solver.');
 sendGeometry(metrics,m.dt,start);
}
self.onmessage=e=>{
 try{
  const m=e.data;
  if(m.type==='init'||m.type==='initGPU'){
   const config=configuredPreset(m);backend=m.type==='initGPU'?'gpu':'cpu';
   sim=new FlipSolver(config);surface=new SurfaceBuilder(config);secondary=new SecondaryParticles(config.seed+99);
   if(backend==='gpu'){
    const positions=sim.p.slice(0,sim.count*3),velocities=sim.v.slice(0,sim.count*3);
    postMessage({config,gpuSeed:{positions,velocities,randomState:sim.randomState,emitCarry:sim.emitCarry}},[positions.buffer,velocities.buffer]);
   }else{postMessage({config});sendCPUFrame(1/48);}
  }else if(m.type==='saveCheckpoint'){
   if(backend!=='cpu'||!sim)throw Error('CPU checkpoints require the CPU reference backend.');
   const appState={client:m.appState??null,surfaceIso:surface.iso,secondary:{state:secondary.state,items:secondary.items,births:secondary.births,transitions:secondary.transitions,previous:secondary.previous}};
   const buffer=encodeCheckpoint(sim,appState);postMessage({requestId:m.requestId,checkpoint:buffer},[buffer]);
  }else if(m.type==='loadCheckpoint'){
   sim=decodeCheckpoint(m.buffer);backend='cpu';surface=new SurfaceBuilder(sim.config);secondary=new SecondaryParticles(sim.config.seed+99);
   if(sim.appState?.secondary)Object.assign(secondary,sim.appState.secondary);if(sim.appState?.surfaceIso)surface.iso=sim.appState.surfaceIso;
   postMessage({config:sim.config,restored:true,restoredFlip:sim.flip,appState:sim.appState?.client});sendGeometry(sim.inspect(),0,performance.now());
  }else if(m.type==='step'){
   if(!sim||backend!=='cpu')throw Error('CPU FLIP worker is not initialized.');
   if(Number.isFinite(m.flip))sim.flip=Math.max(0,Math.min(1,m.flip));sendCPUFrame(m.dt??1/48);
  }else if(m.type==='gpuFrame')receiveGPUFrame(m);
  else throw Error('Unknown worker message '+m.type);
 }catch(error){postMessage({error:error.stack??String(error)});}
};
