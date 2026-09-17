import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';
const full=process.argv.includes('--full'),root=new URL(`sigil-02-water-whip/${full?'full':'cpu'}/`,import.meta.url),out=new URL('particles/',root);fs.mkdirSync(out,{recursive:true});
const cfg=JSON.parse(fs.readFileSync(new URL('config.json',root)));
const load=n=>{const b=fs.readFileSync(new URL(n,root));return new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);};
const source=load('parcels.f32'),forces=[0,1,2].map(c=>{const b=fs.readFileSync(`${cfg.forceRoot}/guide-${c}.f32`);return new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);}),count=source.length/9;
const c=makeProductionPreset('jets');Object.assign(c,cfg,{nameKey:'02-ground-bending',obstacles:[{kind:'box',center:[cfg.extent[0]/2,cfg.origin[1]/2,cfg.extent[2]/2],half:[cfg.extent[0],cfg.origin[1]/2,cfg.extent[2]]}],maxParticles:count+10,seed:91351,gravity:[0,0,0],flip:.88,separation:true,surfaceTension:.072});
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
const track=load('whip.f32'),stride=cfg.guideSamples*9;
const guideNow=new Float32Array(stride),guideNext=new Float32Array(stride);
function sampleTime(t,result){
 const ft=Math.max(0,Math.min(cfg.guideTimes-1.001,t/cfg.guideDt)),frame=Math.floor(ft),blend=ft-frame;
 for(let q=0;q<stride;q++)result[q]=track[frame*stride+q]*(1-blend)+track[(frame+1)*stride+q]*blend;
}
function goal(i,t,table,result){
 const k=i*9,u=source[k+6],cz=source[k+7],cy=source[k+8];
 const fq=u*(cfg.guideSamples-1),q=Math.min(cfg.guideSamples-2,Math.floor(fq)),a=fq-q;
 const arrival=smooth((t-2.7-u*.95)/1.65);
 for(let j=0;j<3;j++){
  const r=q*9+j;
  const center=table[r]*(1-a)+table[r+9]*a;
  const n=table[r+3]*(1-a)+table[r+12]*a;
  const b=table[r+6]*(1-a)+table[r+15]*a;
  const moving=(center+n*cz+b*cy)*cfg.spaceScale+cfg.origin[j];
  result[j]=moving*(1-arrival)+source[k+3+j]*arrival;
 }
}
class Flow extends FlipSolver{
 constructor(c){super(c);this.ids=new Uint32Array(this.maxParticles);this.goal0=[0,0,0];this.goal1=[0,0,0];}
 emit(){if(this.count)return;for(let i=0;i<count;i++){const k=i*9;if(!this.add(...source.subarray(k,k+3)))throw Error('Initial mass inside collider');this.ids[i]=i;this.spawned++;}}
 step(dt){
  if(this.count){const t=this.time/cfg.timeScale,guide=1-smooth((t-5.1)/.75);
   if(guide>0){sampleTime(t,guideNow);sampleTime(t+.025,guideNext);}
   if(guide>0)for(let i=0;i<this.count;i++){
    goal(i,t,guideNow,this.goal0);goal(i,t+.025,guideNext,this.goal1);
    for(let j=0;j<3;j++){const q=i*3+j,wanted=(this.goal1[j]-this.goal0[j])/(.025*cfg.timeScale);let acceleration=90*(this.goal0[j]-this.p[q])+14*(wanted-this.v[q]);acceleration=Math.max(-24,Math.min(24,acceleration));this.v[q]+=dt*guide*acceleration;}
   }
  }return super.step(dt);
 }
 applyForces(dt){
  const t=this.time/cfg.timeScale,release=smooth((t-8.1)/.65),hold=1-release,settled=smooth((t-4.8)/.6);
  this.gravity[1]=-9.81*release;super.applyForces(dt);
  // An unresolved wall boundary layer dissipates tangential momentum at
  // contact. Normal contact remains the native solid-boundary projection.
  // This replaces the former perfectly slippery floor, not free-flight drag.
  if(release>0)for(let i=1;i<this.nx;i++)for(let j=1;j<this.ny;j++){
   const height=(j+.5)*this.h-cfg.origin[1];if(height<0||height>.055)continue;
   const retention=Math.exp(-45*Math.exp(-height/.025)*dt);
   for(let k=1;k<this.nz;k++){const q=this.index(i,j,k);this.u[0][q]*=retention;this.u[2][q]*=retention;}
  }
  if(!hold||!settled)return;
  for(let axis=0;axis<3;axis++){
   const a=forces[axis],u=this.u[axis],valid=this.valid[axis];
   for(let q=0;q<this.len;q++)if(valid[q])u[q]+=(a[q*2]-(a[q*2+1]+.65)*u[q])*dt*hold*settled;
  }
  // Bounded, smooth bulk circulation inside the force-confined liquid.
  for(let i=1;i<this.nx;i++)for(let j=1;j<this.ny;j++)for(let k=1;k<this.nz;k++){
   const q=this.index(i,j,k);if(this.kind[q]!==1)continue;
   const x=i*this.h,y=j*this.h,z=k*this.h;
   this.u[0][q]+=.20*Math.sin(y*13+t)*Math.cos(z*9)*dt*hold;
   this.u[1][q]+=.20*Math.sin(z*11-t*.7)*Math.cos(x*8)*dt*hold;
   this.u[2][q]+=.20*Math.sin(x*12+t*.8)*Math.cos(y*9)*dt*hold;
  }
 }
}
const sim=new Flow(c),manifest={config:c,origin:cfg.origin,spaceScale:cfg.spaceScale,timeScale:cfg.timeScale,frameDt:cfg.timeScale/30,playbackFps:30,frames:[],source:'All water exists at frame zero in a rounded ground crescent. A volume-aware 3D hook and accelerating cast guide its lift. Authored external accelerations lift, bend and spread it into the sigil. Native FLIP and a solid floor solve the release. No timed reveal, outflow deletion or particle-position warp.',cacheFormat:'position-u16-velocity-i16-id-u32',cacheVelocityRange:16};
const started=performance.now();
for(let f=0;f<cfg.frames;f++){
 while(full&&fs.readdirSync(out).filter(n=>n.endsWith('.gz')).length>=12)await new Promise(r=>setTimeout(r,400));
 const info=sim.advance(manifest.frameDt);if(!info.finite||!info.pressure.converged||info.capacityRejected||Math.abs(info.sourceVolumeBalance)>1e-8)throw Error(JSON.stringify(info));
 let floorContacts=0,minHeight=Infinity;for(let i=0;i<sim.count;i++){minHeight=Math.min(minHeight,sim.p[i*3+1]);if(sim.p[i*3+1]<cfg.origin[1]+cfg.h*1.5)floorContacts++;}
 manifest.frames.push({frame:f,...info,floorContacts,minHeightWorld:(minHeight-cfg.origin[1])/.35});
 if(full||f%6===0||f===cfg.frames-1){
  const n=sim.count,pp=new Uint16Array(n*3),pv=new Int16Array(n*3);
  for(let j=0;j<n*3;j++){if(Math.abs(sim.v[j])>16)throw Error('Cache range exceeded');pp[j]=Math.round(Math.max(0,Math.min(1,sim.p[j]/cfg.extent[j%3]))*65535);pv[j]=Math.round(sim.v[j]/16*32767);}
  fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(Buffer.concat([Buffer.from(pp.buffer),Buffer.from(pv.buffer),Buffer.from(sim.ids.buffer,0,n*4)]),{level:4}));
 }
 fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));
 if(f%30===0)console.log(JSON.stringify({frame:f,particles:sim.count,contacts:floorContacts,minHeight:manifest.frames.at(-1).minHeightWorld,seconds:Math.round((performance.now()-started)/1000)}));
}
manifest.complete=true;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));console.log('SIM COMPLETE');
