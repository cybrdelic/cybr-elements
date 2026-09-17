// Native pressure-projected FLIP/APIC in an authored sigil-shaped guide.
// The guide preserves readable counters during the hold, then releases.
import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';
const variant=process.argv[2]??'01';if(!['01','02'].includes(variant))throw Error('variant');
const base=new URL(`sigil-v1/water-${variant}/`,import.meta.url);fs.mkdirSync(base,{recursive:true});
const out=new URL('particles/',base);fs.mkdirSync(out,{recursive:true});
const bytes=fs.readFileSync(new URL(`sigil-v1/mark-${variant}.bin`,import.meta.url));const data=new Float32Array(bytes.buffer,bytes.byteOffset,bytes.byteLength/4);
const fw=1024,fh=576,plane=fw*fh,scale=.4,h=.016,timeScale=.30,origin=[2.304,.8,.48];
function sample(which,wx,wz){
 const u=(wx/11.4+.5)*(fw-1),v=((wz-2.95)/6.4125+.5)*(fh-1);if(u<0||v<0||u>=fw-1||v>=fh-1)return which===0?-1:0;
 const i=Math.floor(u),j=Math.floor(v),a=u-i,b=v-j,k=which*plane+j*fw+i;
 return (data[k]*(1-a)+data[k+1]*a)*(1-b)+(data[k+fw]*(1-a)+data[k+fw+1]*a)*b;
}
const cfg=makeProductionPreset('jets');Object.assign(cfg,{nameKey:'sigil-guided-water',h,nx:288,ny:220,nz:60,extent:[288*h,220*h,60*h],obstacles:[],maxParticles:330000,seed:8167+Number(variant),gravity:[0,0,0],flip:.88,separation:true,surfaceTension:.072});
const seeds=[];const spacing=h*.5;
for(let x=h*2;x<cfg.extent[0]-h*2;x+=spacing)for(let y=h*2;y<cfg.extent[1]-h*2;y+=spacing){
 const wx=(x-origin[0])/scale,wz=(y-origin[1])/scale,d=sample(0,wx,wz);if(d<.013)continue;
 const half=(.014+.018*(1-Math.exp(-d/.13)))*Math.sqrt(Math.min(1,d/.045));const t=sample(1,wx,wz);
 for(let z=origin[2]-half+spacing*.5;z<origin[2]+half;z+=spacing)seeds.push([t,x,y,z]);
}
seeds.sort((a,b)=>a[0]-b[0]);console.log('SCHEDULE',variant,seeds.length,'particles',flush());function flush(){return '';}
class SigilFlow extends FlipSolver{
 initialize(){}
 insideSolid(x,y,z,margin=0){
  if(super.insideSolid(x,y,z,margin))return true;
  if((this.time??0)/timeScale>=6.2)return false;
  return sample(0,(x-origin[0])/scale,(y-origin[1])/scale)*scale<margin;
 }
 emit(dt){
  const t=this.time/timeScale;this.cursor??=0;
  if(t>=6.2&&!this.released){this.released=true;this.markSolids();}
  while(this.cursor<seeds.length&&seeds[this.cursor][0]<=t+dt/timeScale){
   const q=seeds[this.cursor++],wx=(q[1]-origin[0])/scale,wz=(q[2]-origin[1])/scale;
   const gx=sample(2,wx,wz),gz=sample(3,wx,wz),len=Math.hypot(gx,gz)||1;
   if(this.add(q[1],q[2],q[3],-.10*gz/len,.10*gx/len,.045*Math.sin(wx*9+wz*8)))this.spawned++;
  }
 }
 applyForces(dt){
  const t=this.time/timeScale,r=Math.max(0,Math.min(1,(t-6.2)/.45));this.gravity[1]=-9.81*r*r*(3-2*r);super.applyForces(dt);
  if(t>=6.2)return;
  for(let n=0;n<this.nActive;n++){
   const q=this.active[n],i=Math.floor(q/this.sx),j=Math.floor((q-i*this.sx)/this.sy),k=q%this.sy;
   const wx=((i+.5)*h-origin[0])/scale,wz=((j+.5)*h-origin[1])/scale;
   this.u[2][q]+=.035*Math.sin(wx*13+wz*9-t*3)*dt;
  }
 }
 collide(n){
  super.collide(n);if(this.time/timeScale>=6.2)return;
  const q=n*3,margin=h*.10;
  for(let k=0;k<3;k++){
   const wx=(this.p[q]-origin[0])/scale,wz=(this.p[q+1]-origin[1])/scale,d=sample(0,wx,wz)*scale;if(d>=margin)break;
   const gx=sample(2,wx,wz),gz=sample(3,wx,wz),norm=Math.hypot(gx,gz);if(norm<1e-5)break;
   const nx=gx/norm,ny=gz/norm;this.p[q]+=(margin-d)*nx;this.p[q+1]+=(margin-d)*ny;
   const vn=this.v[q]*nx+this.v[q+1]*ny;if(vn<0){this.v[q]-=vn*nx;this.v[q+1]-=vn*ny;}
  }
 }
}
const sim=new SigilFlow(cfg),manifest={config:cfg,frameDt:timeScale/30,playbackFps:30,timeScale,spaceScale:scale,origin,frames:[],duration:10,source:'Native FLIP/APIC, capillarity and pressure solve; authored glyph side guide during formation/hold, free front/back surface; release to gravity at 6.2s. Not an unforced free-form liquid.'};
const started=performance.now();
for(let f=0;f<300;f++){
 while(fs.readdirSync(out).filter(s=>s.endsWith('.gz')).length>=6)await new Promise(r=>setTimeout(r,300));
 const info=sim.advance(manifest.frameDt);if(!info.finite||!info.pressure.converged||info.capacityRejected||Math.abs(info.sourceVolumeBalance)>1e-8)throw Error(JSON.stringify(info));
 const n=sim.count,raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);
 fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:2}));manifest.frames.push({frame:f,...info});
 const tmp=new URL('manifest.tmp',out);fs.writeFileSync(tmp,JSON.stringify(manifest));fs.renameSync(tmp,new URL('manifest.json',out));
 if(f%15===0)console.log(JSON.stringify({frame:f,particles:n,seconds:Math.round((performance.now()-started)/1000),residual:info.pressure.relativeResidual,mass:info.sourceVolumeBalance}),{flush:true});
}
manifest.complete=true;manifest.elapsedSeconds=(performance.now()-started)/1000;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));console.log('COMPLETE');
