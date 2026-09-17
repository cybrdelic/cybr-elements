import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';
const root=new URL('sigil-02-water-arrival/',import.meta.url),out=new URL('particles/',root);fs.mkdirSync(out,{recursive:true});
const cfg=JSON.parse(fs.readFileSync(new URL('config.json',root))),full=process.argv.includes('--full');
const load=name=>{const b=fs.readFileSync(new URL(name,root));return new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);};
const source=load('source.f32'),forces=[0,1,2].map(c=>load(`guide-${c}.f32`)),count=source.length/7;
const c=makeProductionPreset('jets');Object.assign(c,cfg,{nameKey:'02-water-arriving-surge',obstacles:[],maxParticles:count+100,seed:91351,gravity:[0,0,0],flip:.88,separation:true,surfaceTension:.072});
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
function wave(x,t){
 const birth=.25+(x+4.08)/8.16*1.85+.055*Math.sin(x*2.1),age=Math.max(0,t-birth);
 const a=Math.exp(-age/.65),b=Math.exp(-age/.80),d=Math.exp(-age/.70);
 const ox=-.45*a*Math.cos(3.4*age),oz=-.30*b*Math.cos(4*age),stretch=1-.10*d;
 const vx= .45*a*(Math.cos(3.4*age)/.65+3.4*Math.sin(3.4*age));
 const vz= .30*b*(Math.cos(4*age)/.80+4*Math.sin(4*age));
 return [age,ox,oz,stretch,vx,vz,.10/.70*d];
}
class Flow extends FlipSolver{
 constructor(c){super(c);this.ids=new Uint32Array(this.maxParticles);}
 emit(dt){this.cursor??=0;const t=(this.time+dt)/cfg.timeScale;while(this.cursor<count&&source[this.cursor*7]<=t){const k=this.cursor++*7;if(this.add(...source.subarray(k+1,k+7))){this.ids[this.count-1]=k/7;this.spawned++;}}}
 applyForces(dt){
  const t=this.time/cfg.timeScale,release=smooth((t-5.8)/.85),hold=1-release;
  this.gravity[1]=-9.81*release;super.applyForces(dt);if(!hold)return;
  const h=this.h,sx=this.sx,sy=this.sy;
  for(let axis=0;axis<3;axis++){
   const a=forces[axis],u=this.u[axis],valid=this.valid[axis];
   for(let i=0;i<=this.nx;i++){
    const wx=((i+(axis===0?0:.5))*h-cfg.origin[0])/.35;
    let tx=wx;for(let it=0;it<6;it++){const w=wave(tx,t),derivative=1-w[4]*(1.85/8.16+.055*2.1*Math.cos(tx*2.1));tx-=(tx+w[1]-wx)/Math.max(.3,derivative);}
    const [age,ox,oz,stretch,vx,vz,ds]=wave(tx,t);
    const fx=(tx*.35+cfg.origin[0])/h-(axis===0?0:.5),ix=Math.max(0,Math.min(this.nx-1,Math.floor(fx))),ax=Math.max(0,Math.min(1,fx-ix));
    // Let the leading surge move freely inside a wider guide; tighten only
    // after it has travelled. This is a force, never a position constraint.
    const strength=1.1-.1*smooth(age/1.1),transport=2.5*Math.exp(-age/.85);
    for(let j=0;j<=this.ny;j++){
     const wz=((j+(axis===1?0:.5))*h-cfg.origin[1])/.35,tz=1.9+(wz-1.9-oz)/stretch;
     const fy=(tz*.35+cfg.origin[1])/h-(axis===1?0:.5),iy=Math.max(0,Math.min(this.ny-1,Math.floor(fy))),ay=Math.max(0,Math.min(1,fy-iy));
     for(let k=0;k<=this.nz;k++){
      const q=i*sx+j*sy+k;if(!valid[q])continue;
      const wy=((k+(axis===2?0:.5))*h-cfg.origin[2])/.35,ty=wy*stretch;
      const fz=(ty*.35+cfg.origin[2])/h-(axis===2?0:.5),iz=Math.max(0,Math.min(this.nz-1,Math.floor(fz))),az=Math.max(0,Math.min(1,fz-iz));
      let force=0,damp=0;
      for(let di=0;di<2;di++)for(let dj=0;dj<2;dj++)for(let dk=0;dk<2;dk++){
       const weight=(di?ax:1-ax)*(dj?ay:1-ay)*(dk?az:1-az),n=((ix+di)*sx+(iy+dj)*sy+iz+dk)*2;force+=weight*a[n];damp+=weight*a[n+1];
      }
      const desired=(axis===0?vx:axis===1?vz+(tz-1.9)*ds:-ty*ds/(stretch*stretch))*.35/.4;
      const jac=axis===1?stretch:axis===2?1/stretch:1;
      u[q]+=(force*jac*strength+(damp+transport)*(desired-u[q]))*dt*hold;
     }
    }
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
const sim=new Flow(c),manifest={config:c,origin:cfg.origin,spaceScale:cfg.spaceScale,timeScale:cfg.timeScale,frameDt:cfg.timeScale/30,playbackFps:30,frames:[],source:'Upstream moving inlet and time-dependent bending forces before pressure projection; native FLIP transport. Authored bending guide, not unforced typography.',cacheFormat:'position-u16-velocity-i16-id-u32',cacheVelocityRange:16};
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
