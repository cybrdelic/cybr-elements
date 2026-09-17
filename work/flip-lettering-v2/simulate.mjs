import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import crypto from 'node:crypto';
const root=new URL('./',import.meta.url),out=new URL('./cache/',root),path=JSON.parse(fs.readFileSync(new URL('path.json',root)));
const config=makeProductionPreset('jets');Object.assign(config,{nameKey:'cybrdelic',h:.03,nx:156,ny:100,nz:36,extent:[4.68,3,1.08],obstacles:[],maxParticles:350000,seed:8107,gravity:[0,0,0]});
function point(t){let u=Math.max(0,Math.min(1,t/.60))*12.8;let lo=0,hi=path.times.length-1;while(hi-lo>1){let m=(lo+hi)>>1;if(path.times[m]<u)lo=m;else hi=m;}let a=(u-path.times[lo])/(path.times[hi]-path.times[lo]);let p=path.points[lo].map((v,i)=>v+(path.points[hi][i]-v)*a);return [(p[0]+3.7347561)*.50+.39,(p[1]-.64341463)*.50+1.02,.54+.035*Math.sin(u)];}
class Lettering extends FlipSolver{
 emit(dt){if(this.time>=.6)return;let end=Math.min(.6,this.time+dt),a=point(this.time),b=point(end),dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy),nx=-dy/Math.max(len,1e-8),ny=dx/Math.max(len,1e-8);let volume=len*.006;this.emitCarry+=volume/(this.h*.5)**3;let count=Math.floor(this.emitCarry);this.emitCarry-=count;
 for(let j=0;j<count;j++){let u=this.random(),t=this.time+(end-this.time)*u,p=point(t),side=j%2?1:-1,r=(this.random()-.5)*.10,z=side*.042+(this.random()-.5)*.022;let vx=dx/Math.max(len,1e-8)*.08,vy=dy/Math.max(len,1e-8)*.08;
 if(this.add(p[0]+nx*r,p[1]+ny*r,p[2]+z,vx,vy,-side*.32))this.spawned++;}
 }
}
const sim=new Lettering(config),manifest={config,frameDt:1/96,frames:[],solver:'Original CYBR FLIP III.1; custom moving paired emitters',playbackFps:24};let start=performance.now();
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
for(let frame=0;frame<192;frame++){
 const release=Math.max(0,Math.min(1,(sim.time-1.25)/.15));sim.gravity[1]=-9.81*release*release*(3-2*release);const info=sim.advance(1/96),n=sim.count;if(!info.finite||info.capacityRejected||!info.pressure.converged)throw Error(JSON.stringify(info));
 let raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);fs.writeFileSync(new URL(`${String(frame).padStart(4,'0')}.particles`,out),raw);fs.writeFileSync(new URL(`${String(frame).padStart(4,'0')}.shape`,out),Buffer.from(sim.shape.buffer,0,n*24));
 manifest.frames.push({frame,...info,primarySha256:sha(raw)});fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));if(frame%4===0)console.log(JSON.stringify({frame,n,seconds:(performance.now()-start)/1000}));
}
manifest.simulationComplete=true;manifest.seconds=(performance.now()-start)/1000;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));console.log('COMPLETE',manifest.seconds);
