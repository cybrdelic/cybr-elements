import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import crypto from 'node:crypto';
const root=new URL('./',import.meta.url),out=new URL('cache-final/',root),route=JSON.parse(fs.readFileSync(new URL('path.json',root)));const mb=fs.readFileSync(new URL('mask.bin',root)),mask=new Float32Array(mb.buffer,mb.byteOffset,mb.byteLength/4);
const config=makeProductionPreset('jets');Object.assign(config,{nameKey:'directed',h:.03,nx:280,ny:100,nz:40,extent:[8.4,3,1.2],obstacles:[],maxParticles:180000,seed:8107,gravity:[0,0,0]});
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));const smooth=x=>{x=clamp(x,0,1);return x*x*(3-2*x)};
function at(t){let lo=0,hi=route.times.length-1;t=clamp(t,0,.65);while(hi-lo>1){let m=(lo+hi)>>1;if(route.times[m]<t)lo=m;else hi=m;}let a=(t-route.times[lo])/Math.max(1e-9,route.times[hi]-route.times[lo]);let p=route.points[lo].map((x,i)=>x+(route.points[hi][i]-x)*a);return {p:[(p[0]+3.7347561)*.5+.39,(p[1]-.64341463)*.5+1.02,.60+.025*Math.sin(t*11)],on:route.emit[lo]===1};}
function inside(x,y){let ox=(x-.39)*2-3.7347561,oy=(y-1.02)*2+.64341463,ix=Math.round((ox+5.25)/10.5*511),iy=Math.round(oy/5.8*319);return ix>=0&&ix<512&&iy>=0&&iy<320&&mask[iy*512+ix]>.35;}
class Directed extends FlipSolver{
 constructor(c){super(c);this.birth=new Float32Array(this.maxParticles);this.home=new Float32Array(this.maxParticles*3);this.tangent=new Float32Array(this.maxParticles*3);this.occupancy=new Map();}
 target(i,t){let q=i*3,h=this.home,x=h[q],y=h[q+1],z=h[q+2],begin=1.3+clamp((x-.39)/3.9,0,1)*.42,u=smooth((t-begin)/.65);return [x+(7.0+(x-2.34)*.15-x)*u,y+(1.55+(y-1.7)*.3-y)*u+.20*Math.sin(Math.PI*u),z+(.66+(z-.60)*1.5+(x-2.34)*.04-z)*u+.07*Math.sin(Math.PI*u)];}
 emit(dt){
  // Explicit soft guide forces are applied before the original pressure projection.
  for(let i=0;i<this.count;i++){let q=i*3,g=this.target(i,this.time),next=this.target(i,this.time+.002),release=this.time>1.3+clamp((this.home[q]-.39)/3.9,0,1)*.42;
   let young=smooth((this.time-this.birth[i]-.025)/.05),stiffness=35+125*young,damping=3+19*young;for(let c=0;c<3;c++){let flow=release?clamp((next[c]-g[c])/.002,-12,12):this.tangent[q+c]*.08;let wave=c===2&&!release?.008*Math.sin(this.time*9+this.home[q]*3+this.home[q+1]*4):0;let force=stiffness*(g[c]+wave-this.p[q+c])+damping*(flow-this.v[q+c]);this.v[q+c]+=clamp(force,-90,90)*dt;}
  }
  if(this.time>=.65)return;
  let end=Math.min(.65,this.time+dt),a=at(this.time).p,b=at(end).p,dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy),nx=-dy/Math.max(len,1e-8),ny=dx/Math.max(len,1e-8);this.emitCarry+=len*.006/(this.h*.5)**3;let count=Math.floor(this.emitCarry);this.emitCarry-=count;
  for(let j=0;j<count;j++){let t=this.time+(end-this.time)*this.random(),sample=at(t);if(!sample.on)continue;let r=(this.random()-.5)*.12,z=(this.random()-.5)*.070,p=[sample.p[0]+nx*r,sample.p[1]+ny*r,sample.p[2]+z];if(!inside(p[0],p[1]))continue;let key=p.map(x=>Math.floor(x/this.h)).join(',');let used=this.occupancy.get(key)||0;if(used>=8)continue;
   let tangent=[dx/Math.max(len,1e-8),dy/Math.max(len,1e-8),0];let id=this.count;if(this.add(...p,...tangent.map(x=>x*1.1))){this.birth[id]=t;this.home.set(p,id*3);this.tangent.set(tangent,id*3);this.occupancy.set(key,used+1);this.spawned++;}
  }
 }
}
const sim=new Directed(config),manifest={config,frameDt:1/96,frames:[],solver:'CYBR FLIP III.1 with explicit soft guide forcing and single gated emitter',playbackFps:24};let start=performance.now();const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
for(let frame=0;frame<240;frame++){
 let info=sim.advance(1/96),n=sim.count;if(!info.finite||info.capacityRejected||!info.pressure.converged)throw Error(JSON.stringify(info));let raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);fs.writeFileSync(new URL(`${String(frame).padStart(4,'0')}.particles`,out),raw);fs.writeFileSync(new URL(`${String(frame).padStart(4,'0')}.shape`,out),Buffer.from(sim.shape.buffer,0,n*24));
 let error=0;for(let i=0;i<n;i++){let g=sim.target(i,sim.time);error+=Math.hypot(...g.map((x,c)=>x-sim.p[i*3+c]));}manifest.frames.push({frame,...info,guideMeanDistance:error/Math.max(1,n),head:at(sim.time).p,primarySha256:sha(raw)});fs.writeFileSync(new URL('manifest.tmp',out),JSON.stringify(manifest));fs.renameSync(new URL('manifest.tmp',out),new URL('manifest.json',out));if(frame%8===0)console.log(JSON.stringify({frame,n,guideError:error/Math.max(1,n),seconds:(performance.now()-start)/1000}));
}
manifest.simulationComplete=true;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest));console.log('COMPLETE');
