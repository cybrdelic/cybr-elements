import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';
import crypto from 'node:crypto';

const root=new URL('./',import.meta.url);
const out=new URL('./cache-ns-water-prod/',root);
fs.mkdirSync(out,{recursive:true});

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const tauMax=.28,tauMin=.020,duration=8/24;
const h=.045;
const config=makeProductionPreset('vortex');
Object.assign(config,{
  nameKey:'ns-water-prod',
  h,
  nx:64,ny:48,nz:64,
  extent:[64*h,48*h,64*h],
  obstacles:[],
  maxParticles:520000,
  seed:260921,
  gravity:[0,-9.81,0],
  surfaceTension:.072,
  pressureTolerance:1e-5,
  iterations:320,
  flip:.94,
  separation:true,
  advection:'rk2',
  shapeTransport:true,
  surfaceOptions:{
    spacingFactor:.43,
    kernelRadiusFactor:1.48,
    fieldSigma:.68,
    meshSmoothingPasses:8,
    temporalBlend:0,
    shapeHistoryWeight:0
  }
});

const cx=config.extent[0]/2,cz=config.extent[2]/2;
const coreY=.62;

function tauAt(t){
  const a=clamp(t/duration,0,1);
  return tauMax*Math.pow(tauMin/tauMax,a);
}

function similarityVelocity(x,y,z,tau){
  // Leading shrinking-core similarity field centered inside a larger ordinary
  // water body.  The outer liquid is not rescaled or kinematically animated.
  const X=x-cx,Y=y-coreY,Z=z-cz;
  const r=Math.hypot(X,Z);
  const Lr=.82*Math.pow(tau,.5);
  const Lz=.96*Math.pow(tau,.491);
  const R=r/Lr,Q=Y/Lz;
  const env=Math.exp(-.5*(R*R+.72*Q*Q));
  const C=.62,swirl=2.15;
  const ur=-(C/tau)*r*(1-.72*Q*Q)*env;
  const uy=(C/tau)*Y*(2-R*R)*env;
  const ut=swirl*Math.pow(tau,-.509)*R*env*(1+.08*Math.tanh(Q));
  const c=r>1e-10?X/r:1,s=r>1e-10?Z/r:0;
  return [ur*c-ut*s,uy,ur*s+ut*c];
}

function coreWeight(x,y,z,tau){
  const X=x-cx,Y=y-coreY,Z=z-cz;
  const Lr=.82*Math.pow(tau,.5);
  const Lz=.96*Math.pow(tau,.491);
  const R=Math.hypot(X,Z)/Math.max(Lr,1e-6);
  const Q=Y/Math.max(Lz,1e-6);
  // Quartic falloff makes the singular core local: the surrounding water
  // remains normal FLIP water and supplies the large-scale visual reference.
  return Math.exp(-.34*(R**4+.72*Q**4));
}

class BlowupWater extends FlipSolver {
  initialize(){
    // Broad grounded water mound/puddle rather than a floating blob.  This is
    // deliberately similar to the established CYBR water language: a coherent
    // body with a real free surface, thin peripheral sheets and room for spray.
    this.seedVolume((x,y,z)=>{
      const X=(x-cx)/1.19,Z=(z-cz)/1.13;
      const r2=X*X+Z*Z;
      if(r2>=1)return false;
      const top=.16+.82*Math.pow(1-r2,.58);
      return y<top;
    });

    // Seed only the localized core with the similarity field.  Everywhere else
    // starts as ordinary water at rest under gravity.
    const tau=tauAt(0);
    for(let n=0;n<this.count;n++){
      const q=n*3,x=this.p[q],y=this.p[q+1],z=this.p[q+2];
      const w=coreWeight(x,y,z,tau);
      if(w<1e-4)continue;
      const v=similarityVelocity(x,y,z,tau);
      this.v[q]=w*v[0];this.v[q+1]=w*v[1];this.v[q+2]=w*v[2];
    }
  }

  emit(_dt){}

  applyForces(dt){
    // Keep normal water gravity first.
    super.applyForces(dt);

    // Local similarity forcing is applied on the MAC grid, then the normal
    // FLIP pressure solve reprojects the result.  This is not direct particle
    // animation and does not collapse the outer body with the core.
    const tau=tauAt(this.time+.5*dt);
    const response=1-Math.exp(-15*dt);
    const [u,v,w]=this.u,{sx,sy,kind}=this,H=this.h;
    for(let i=1;i<this.nx;i++)for(let j=1;j<this.ny;j++)for(let k=1;k<this.nz;k++){
      const q=this.index(i,j,k);
      if(kind[q]!==1&&kind[q-sx]!==1&&kind[q-sy]!==1&&kind[q-1]!==1)continue;

      const px=i*H,py=(j+.5)*H,pz=(k+.5)*H;
      const wx=coreWeight(px,py,pz,tau);
      if(wx>1e-5&&this.valid[0][q]){
        const target=similarityVelocity(px,py,pz,tau)[0];
        u[q]+=response*wx*(target-u[q]);
      }

      const qx=(i+.5)*H,qy=j*H,qz=(k+.5)*H;
      const wy=coreWeight(qx,qy,qz,tau);
      if(wy>1e-5&&this.valid[1][q]){
        const target=similarityVelocity(qx,qy,qz,tau)[1];
        v[q]+=response*wy*(target-v[q]);
      }

      const rx=(i+.5)*H,ry=(j+.5)*H,rz=k*H;
      const wz=coreWeight(rx,ry,rz,tau);
      if(wz>1e-5&&this.valid[2][q]){
        const target=similarityVelocity(rx,ry,rz,tau)[2];
        w[q]+=response*wz*(target-w[q]);
      }
    }
  }
}

const sim=new BlowupWater(config);
const frameDt=1/24;
const manifest={
  schema:'cybr-flip-cache/3',
  solver:'CYBR FLIP III.1 quadratic APIC/FLIP + Galerkin MG-PCG',
  representation:'large ordinary free-surface water body with localized shrinking-core forcing',
  forcing:'quartic-localized smooth divergence-free similarity field before pressure projection',
  config,frameDt,playbackFps:24,
  tauMax,tauMin,duration,
  frames:[],
  noImageGeneration:true,
  disclosure:'Genuine CYBR FLIP liquid. The localized prescribed field matches the leading shrinking-core exponents but is not the exact full E/U/Pi + annular-pulse + forcing construction from the proof.'
};
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');

for(let frame=0;frame<8;frame++){
  const info=sim.advance(frameDt);
  if(!info.finite||info.capacityRejected||!info.pressure.converged)throw Error(JSON.stringify(info));
  const n=sim.count;
  const primary=Buffer.concat([
    Buffer.from(sim.p.buffer,sim.p.byteOffset,n*12),
    Buffer.from(sim.v.buffer,sim.v.byteOffset,n*12)
  ]);
  const shape=Buffer.from(sim.shape.buffer,sim.shape.byteOffset,n*24);
  fs.writeFileSync(new URL(`${String(frame).padStart(4,'0')}.particles`,out),primary);
  fs.writeFileSync(new URL(`${String(frame).padStart(4,'0')}.shape`,out),shape);
  const tau=tauAt(sim.time);
  const row={frame,tau,...info,primarySha256:sha(primary)};
  manifest.frames.push(row);
  fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest,null,2));
  console.log(JSON.stringify({
    frame,tau,particles:n,maxSpeed:info.maxSpeed,
    kineticEnergy:info.kineticEnergy,divergence:info.divergenceAfter,
    pressureIterations:info.pressure.iterations,substeps:info.substeps
  }));
}
manifest.simulationComplete=true;
fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest,null,2));
console.log('COMPLETE');
