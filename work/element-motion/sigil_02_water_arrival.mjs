import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';
const full=process.argv.includes('--full'),root=new URL(`sigil-02-water-arrival/${full?'full/':''}`,import.meta.url),out=new URL('particles/',root);fs.mkdirSync(out,{recursive:true});
const cfg=JSON.parse(fs.readFileSync(new URL('config.json',root)));
const load=name=>{const b=fs.readFileSync(new URL(name,root));return new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);};
const source=load('source.f32'),forces=[0,1,2].map(c=>load(`guide-${c}.f32`)),circulation=[0,1,2].map(c=>load(`circulation-${c}.f32`)),count=source.length/7;
const c=makeProductionPreset('jets');Object.assign(c,cfg,{nameKey:'02-water-arriving-surge',obstacles:[],maxParticles:count+100,seed:91351,gravity:[0,0,0],flip:.88,separation:true,surfaceTension:.072});
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
class Flow extends FlipSolver{
 constructor(c){super(c);this.ids=new Uint32Array(this.maxParticles);}
 emit(dt){this.cursor??=0;const t=(this.time+dt)/cfg.timeScale;while(this.cursor<count&&source[this.cursor*7]<=t){const k=this.cursor++*7;if(this.add(...source.subarray(k+1,k+7))){this.ids[this.count-1]=k/7;this.spawned++;}}}
 applyForces(dt){
  const t=this.time/cfg.timeScale,release=smooth((t-5.8)/.85),hold=1-release;
  this.gravity[1]=-9.81*release;super.applyForces(dt);if(!hold)return;
  for(let axis=0;axis<3;axis++){
   const a=forces[axis],swirl=circulation[axis],u=this.u[axis],valid=this.valid[axis],alive=smooth((t-2.3)/.7),drag=2.6-2.15*alive;
   const first=1.0*Math.cos((t-2.3)*1.27),second=1.0*Math.sin((t-2.3)*1.03);
   for(let q=0;q<this.len;q++)if(valid[q]){
    // Full-volume force contains the curved jet. Source momentum and native
    // pressure carry the fluid around the bends; no moving pose is imposed.
    u[q]+=(a[q*2]-(a[q*2+1]+drag)*u[q]+alive*(first*swirl[q*2]+second*swirl[q*2+1]))*dt*hold;
   }
  }
 }
 step(dt){
  const result=super.step(dt);let kept=0;
  for(let i=0;i<this.count;i++){
   if(this.p[i*3+1]<=.12){this.deleted++;continue;}
   if(kept!==i){for(const [a,stride] of [[this.p,3],[this.v,3],[this.affine,9],[this.shape,6],[this.previousPosition,3]])a.copyWithin(kept*stride,i*stride,(i+1)*stride);this.ids[kept]=this.ids[i];}kept++;
  }this.count=kept;this.shapeInitialized=kept;return result;
 }
}
const sim=new Flow(c),manifest={config:c,origin:cfg.origin,spaceScale:cfg.spaceScale,timeScale:cfg.timeScale,frameDt:cfg.timeScale/30,playbackFps:30,frames:[],source:'Upstream inlets along the curved stroke tangents; native FLIP transport under a static bending potential. Curl forces sustain resolved circulation after 2.3 seconds. No animated guide pose, particle teleport or render morph.',cacheFormat:'position-u16-velocity-i16-id-u32',cacheVelocityRange:16};
const begun=performance.now(),end=full?300:121;
let replay=0;try{replay=JSON.parse(fs.readFileSync(new URL('manifest.json',out))).frames.length;}catch{}
async function saveManifest(){
 fs.writeFileSync(new URL('manifest.tmp',out),JSON.stringify(manifest));
 for(let attempt=0;;attempt++){
  try{fs.renameSync(new URL('manifest.tmp',out),new URL('manifest.json',out));break;}
  catch(error){if(!['EPERM','EBUSY','EACCES'].includes(error.code)||attempt>=40)throw error;await new Promise(r=>setTimeout(r,50));}
 }
}
for(let f=0;f<end;f++){
 while(f>=replay&&fs.readdirSync(out).filter(n=>n.endsWith('.gz')).length>=145)await new Promise(r=>setTimeout(r,300));
 const info=sim.advance(manifest.frameDt);if(!info.finite||!info.pressure.converged||info.capacityRejected||Math.abs(info.sourceVolumeBalance)>1e-8)throw Error(JSON.stringify(info));
 if(f<replay){manifest.frames.push({frame:f,...info});continue;}
 const n=sim.count,packedPosition=new Uint16Array(n*3),packedVelocity=new Int16Array(n*3);
 for(let j=0;j<n*3;j++){if(Math.abs(sim.v[j])>16)throw Error('Cache velocity range exceeded');packedPosition[j]=Math.round(Math.max(0,Math.min(1,sim.p[j]/cfg.extent[j%3]))*65535);packedVelocity[j]=Math.round(sim.v[j]/16*32767);}
 const raw=Buffer.concat([Buffer.from(packedPosition.buffer),Buffer.from(packedVelocity.buffer),Buffer.from(sim.ids.buffer,0,n*4)]);
 fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:4}));manifest.frames.push({frame:f,...info});
 await saveManifest();
 if(f%15===0)console.log(JSON.stringify({frame:f,particles:n,seconds:Math.round((performance.now()-begun)/1000),residual:info.pressure.relativeResidual}));
}
manifest.complete=true;await saveManifest();console.log('SIM COMPLETE');
