// New primary FLIP/APIC simulation, not a deformation of the earlier mesh cache.
import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';
import zlib from 'node:zlib';
const out=new URL('bending-rebuild-v5/water-particles/',import.meta.url);
fs.mkdirSync(out,{recursive:true});
const trail=JSON.parse(fs.readFileSync(new URL('shared-trail.json',import.meta.url)));
const timeScale=.32,spaceScale=.4,origin=[2.1,.68,.756];
const c=makeProductionPreset('jets');
Object.assign(c,{nameKey:'bending-depth-jet',h:.018,nx:234,ny:157,nz:84,
 extent:[234*.018,157*.018,84*.018],obstacles:[],maxParticles:190000,seed:93157,
 gravity:[0,-1.7,0],flip:.88,separation:true,surfaceTension:.072});
function pose(t){
 const q=Math.max(0,Math.min(trail.frames.length-1,t*trail.sampleRate)),i=Math.floor(q),u=q-i;
 const a=trail.frames[i],b=trail.frames[Math.min(i+1,trail.frames.length-1)];
 return {p:a.p.map((v,k)=>v*(1-u)+b.p[k]*u),d:a.d.map((v,k)=>v*(1-u)+b.d[k]*u),on:a.on*(1-u)+b.on*u,speed:a.speed,turn:a.turn*(1-u)+b.turn*u};
}
function depth(t){return .31*Math.sin((t-.08)*Math.PI*2/1.60+.35);}
function tangent(t,a){
 const dz=.31*Math.PI*2/1.60*Math.cos((t-.08)*Math.PI*2/1.60+.35);
 const v=[a.d[0]*a.speed*spaceScale,a.d[1]*a.speed*spaceScale,dz];
 const n=Math.hypot(...v);return v.map(x=>x/Math.max(n,.001));
}
class RibbonFlow extends FlipSolver{
 emit(dt){
  this.carry??=0;
  const t=this.time/timeScale,a=pose(t);if(a.on<=0)return;
  // A rounded jet. Its moving centre, normal plane and inherited velocities
  // are genuinely three dimensional before the pressure solve.
  const aspect=Math.exp(.27*Math.sin(t*6.2)+.13*Math.sin(t*14.9+.7));
  const width=.060*(1+.06*Math.sin(t*9))*aspect,radius=.058/aspect;
  const T=tangent(t,a),N=[-a.d[1],a.d[0],0];
  const V=[-T[2]*N[1],T[2]*N[0],T[0]*N[1]-T[1]*N[0]];
  const pathSpeed=Math.hypot(a.speed*spaceScale,.31*Math.PI*2/1.6*Math.cos((t-.08)*Math.PI*2/1.6+.35))/timeScale;
  const flow=Math.PI*width*radius*pathSpeed*a.on;
  this.carry+=flow*dt/(this.h*.5)**3;
  const count=Math.floor(this.carry);this.carry-=count;
  const roll=.30*Math.sin(t*7.7)+.14*Math.sin(t*14.3),co=Math.cos(roll),si=Math.sin(roll);
  for(let i=0;i<count;i++){
   const theta=this.random()*2*Math.PI,rad=Math.sqrt(this.random());
   const aa=width*rad*Math.cos(theta),bb=radius*rad*Math.sin(theta);
   const across=aa*co-bb*si,back=aa*si+bb*co;
   const along=(this.random()-.5)*pathSpeed*dt;
   const x=origin[0]+a.p[0]*spaceScale+N[0]*across+V[0]*back+T[0]*along;
   const y=origin[1]+a.p[1]*spaceScale+N[1]*across+V[1]*back+T[1]*along;
   const z=origin[2]+depth(t)+V[2]*back+T[2]*along;
   const speed=(1.90+.25*(1-rad*rad))*(1+.16*Math.sin(t*15.7)+.08*Math.sin(t*31.9+.8)),omega=1.8+.4*Math.sin(t*9);
   const u=T.map((q,k)=>q*speed+omega*(across*V[k]-back*N[k]));
   if(this.add(x,y,z,...u))this.spawned++;
  }
 }
 applyForces(dt){
  const t=this.time/timeScale,release=Math.max(0,Math.min(1,(t-1.72)/.52));
  this.gravity[1]=-1.7-(9.81-1.7)*release*release*(3-2*release);
  super.applyForces(dt);
  const a=pose(t);if(!a.on)return;
  const cx=origin[0]+a.p[0]*spaceScale,cy=origin[1]+a.p[1]*spaceScale;
  // Local, speed-preserving steering during the bending beat. The subsequent
  // pressure solve enforces incompressibility; there is no positional fitting.
  for(let n=0;n<this.nActive;n++){
   const q=this.active[n],i=Math.floor(q/this.sx),j=Math.floor((q-i*this.sx)/this.sy),k=q%this.sy;
   const dx=(i+.5)*this.h-cx,dy=(j+.5)*this.h-cy,dz=(k+.5)*this.h-origin[2]-depth(t);
   const weight=Math.exp(-(dx*dx+dy*dy+dz*dz)/(.27*.27));
   const angle=a.turn/timeScale*.14*weight*dt,co=Math.cos(angle),si=Math.sin(angle),vx=this.u[0][q],vy=this.u[1][q];
   this.u[0][q]=co*vx-si*vy;this.u[1][q]=si*vx+co*vy;
  }
 }
}
const sim=new RibbonFlow(c);
const manifest={config:c,frameDt:timeScale/30,playbackFps:30,timeScale,spaceScale,origin,frames:[],source:'Area-preserving changing nozzle aspect and axial momentum; same 3D centre; native FLIP/APIC pressure and capillary solve; authored depth trajectory, lift and local turning; no mesh warp'};
const started=performance.now();
for(let f=0;f<120;f++){
 const info=sim.advance(manifest.frameDt);
 if(!info.finite||!info.pressure.converged||info.capacityRejected||Math.abs(info.sourceVolumeBalance)>1e-8)throw Error(JSON.stringify(info));
 const n=sim.count,raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);
 fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:2}));
 manifest.frames.push({frame:f,...info});
 const target=new URL('manifest.json',out),temp=new URL('manifest.tmp',out);
 fs.writeFileSync(temp,JSON.stringify(manifest));fs.renameSync(temp,target);
 if(f%10===0)console.log(JSON.stringify({frame:f,n,seconds:Math.round((performance.now()-started)/1000),pressure:info.pressure.relativeResidual,massBalance:info.sourceVolumeBalance}),{flush:true});
 if(f===42&&!process.argv.includes('--ungated')){
  console.log('PREVIEW GATE: primary states 0..42 ready; waiting for continue-water file');
  while(!fs.existsSync(new URL('bending-rebuild-v5/continue-water',import.meta.url)))await new Promise(resolve=>setTimeout(resolve,500));
 }
}
manifest.complete=true;manifest.elapsedSeconds=(performance.now()-started)/1000;
fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));console.log('WATER SIMULATION COMPLETE');
