import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';import fs from 'node:fs';import zlib from 'node:zlib';
const out=new URL('water-v2-cache/',import.meta.url);fs.mkdirSync(out,{recursive:true});const c=makeProductionPreset('jets');Object.assign(c,{nameKey:'motion',h:.024,nx:175,ny:100,nz:75,extent:[4.2,2.4,1.8],obstacles:[],maxParticles:220000,seed:6271});
class Flow extends FlipSolver{
 emit(dt){this.carry??=[0,0];
 for(let j=0;j<2;j++){const on=j===0?this.time<.78:this.time<.72;if(!on)continue;const radius=j===0?.14:.125,speed=j===0?3.2:3.0;this.carry[j]+=Math.PI*radius*radius*speed*dt/(this.h*.5)**3;const count=Math.floor(this.carry[j]);this.carry[j]-=count;
 for(let i=0;i<count;i++){const theta=this.random()*Math.PI*2,r=radius*Math.sqrt(this.random());const x=j===0?.8+this.random()*speed*dt:3.0-this.random()*speed*dt,y=(j===0?.85:.90)+r*Math.cos(theta),z=.9+r*Math.sin(theta);const vx=j===0?speed:-speed,vy=j===0?2.1:1.9;if(this.add(x,y,z,vx,vy,.08*Math.sin(this.time*8))){this.spawned++;}}
 }}
}
const sim=new Flow(c),m={config:c,frameDt:1/80,frames:[],playbackFps:24,source:'Two finite continuous jets; original gravity and pressure; collision sheet; emission shuts off then liquid releases'};let start=performance.now();
for(let f=0;f<96;f++){let info=sim.advance(m.frameDt);if(!info.finite||!info.pressure.converged||info.capacityRejected)throw Error(JSON.stringify(info));let n=sim.count,raw=Buffer.concat([Buffer.from(sim.p.buffer,0,n*12),Buffer.from(sim.v.buffer,0,n*12)]);fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(raw,{level:1}));m.frames.push({frame:f,...info});fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(m));if(f%12===0)console.log(JSON.stringify({frame:f,n,elapsed:(performance.now()-start)/1000}));}m.complete=true;fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(m));console.log('COMPLETE');
