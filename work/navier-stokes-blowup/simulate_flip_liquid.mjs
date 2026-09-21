import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import {SurfaceBuilder} from '../flip-lettering/vendor/src/surface.js';
import fs from 'node:fs';
import crypto from 'node:crypto';

const root=new URL('./',import.meta.url);
const out=new URL('./cache-ns-flip-liquid/',root);
fs.mkdirSync(out,{recursive:true});

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const tauMax=.28,tauMin=.012,duration=.36,h=.07;
const config=makeProductionPreset('vortex');
Object.assign(config,{
  nameKey:'ns-blowup-liquid',
  h,
  nx:34,ny:34,nz:34,
  extent:[34*h,34*h,34*h],
  obstacles:[],
  maxParticles:220000,
  seed:260921,
  gravity:[0,0,0],
  surfaceTension:.072,
  pressureTolerance:2e-5,
  iterations:240,
  flip:.91,
  separation:true,
  advection:'rk2',
  shapeTransport:true
});

const cx=config.extent[0]/2,cy=config.extent[1]/2,cz=config.extent[2]/2;

function tauAt(t){
  const a=clamp(t/duration,0,1);
  return tauMax*Math.pow(tauMin/tauMax,a);
}

function targetVelocity(x,y,z,tau){
  // Axisymmetric divergence-free shrinking-core field centered in the liquid.
  const X=x-cx,Y=y-cy,Z=z-cz;
  const r=Math.hypot(X,Z);
  const Lr=Math.pow(tau,.5),Lz=Math.pow(tau,.491);
  const R=r/Lr,Q=Y/Lz;
  const env=Math.exp(-.5*(R*R+.72*Q*Q));
  const C=.62,swirl=2.15;
  const ur=-(C/tau)*r*(1-.72*Q*Q)*env;
  const uy=(C/tau)*Y*(2-R*R)*env;
  const ut=swirl*Math.pow(tau,-.509)*R*env*(1+.08*Math.tanh(Q));
  const c=r>1e-10?X/r:1,s=r>1e-10?Z/r:0;
  return [ur*c-ut*s,uy,ur*s+ut*c];
}

class BlowupLiquid extends FlipSolver {
  initialize(){
    // This is a real CYBR free-surface liquid parcel. The proof itself does
    // not require a free surface; the parcel is a visualization window into
    // the velocity concentration mechanism.
    this.seedVolume((x,y,z)=>{
      const X=(x-cx)/.78,Y=(y-cy)/.67,Z=(z-cz)/.78;
      return X*X+Y*Y+Z*Z<1;
    });
    const tau=tauAt(0);
    for(let n=0;n<this.count;n++){
      const q=n*3,v=targetVelocity(this.p[q],this.p[q+1],this.p[q+2],tau);
      this.v[q]=v[0];this.v[q+1]=v[1];this.v[q+2]=v[2];
    }
  }
  emit(_dt){}
  applyForces(dt){
    // Force the genuine FLIP/APIC liquid toward the prescribed smooth
    // divergence-free similarity velocity. The subsequent pressure solve
    // reprojects it, so every accepted substep remains an incompressible
    // free-surface liquid solve rather than direct particle animation.
    const tau=tauAt(this.time+.5*dt),gain=1-Math.exp(-10*dt),H=this.h;
    const [u,v,w]=this.u,{sx,sy,kind}=this;
    for(let i=1;i<this.nx;i++)for(let j=1;j<this.ny;j++)for(let k=1;k<this.nz;k++){
      const q=this.index(i,j,k);
      if(kind[q]!==1&&kind[q-sx]!==1&&kind[q-sy]!==1&&kind[q-1]!==1)continue;
      const U=targetVelocity(i*H,(j+.5)*H,(k+.5)*H,tau);
      const V=targetVelocity((i+.5)*H,j*H,(k+.5)*H,tau);
      const W=targetVelocity((i+.5)*H,(j+.5)*H,k*H,tau);
      if(this.valid[0][q])u[q]+=gain*(U[0]-u[q]);
      if(this.valid[1][q])v[q]+=gain*(V[1]-v[q]);
      if(this.valid[2][q])w[q]+=gain*(W[2]-w[q]);
    }
  }
}

const sim=new BlowupLiquid(config);
const surf=new SurfaceBuilder(config);
surf.spacing=h*.55;
surf.radius=h*1.02;

function writeObj(file,mesh){
  const p=mesh.positions,n=mesh.normals;
  let s='# CYBR FLIP III.1 actual free-surface liquid\n';
  for(let i=0;i<p.length;i+=3)s+=`v ${p[i]} ${p[i+1]} ${p[i+2]}\n`;
  for(let i=0;i<n.length;i+=3)s+=`vn ${n[i]} ${n[i+1]} ${n[i+2]}\n`;
  for(let i=0;i<p.length/3;i+=3)s+=`f ${i+1}//${i+1} ${i+2}//${i+2} ${i+3}//${i+3}\n`;
  fs.writeFileSync(file,s);
}

function particleEnergy(){
  const mass=1000*Math.pow(h*.5,3);
  let E=0,max=0;
  for(let n=0;n<sim.count;n++){
    const q=n*3,s2=sim.v[q]**2+sim.v[q+1]**2+sim.v[q+2]**2;
    E+=.5*mass*s2;max=Math.max(max,Math.sqrt(s2));
  }
  return {kineticEnergy:E,maxParticleSpeed:max};
}

const manifest={
  solver:'CYBR FLIP III.1 quadratic APIC/FLIP + Galerkin MG-PCG',
  representation:'actual free-surface liquid particles with reconstructed surface',
  forcing:'relaxation toward smooth divergence-free shrinking-core similarity velocity before pressure projection',
  tauMax,tauMin,duration,frameDt:1/30,frames:[],
  noImageGeneration:true,
  disclosure:'The liquid solver is genuine CYBR FLIP. The prescribed forcing field matches the leading shrinking-core exponents but is not the exact full E/U/Pi + annular-pulse + forcing construction from the proof.'
};

for(let frame=0;frame<12;frame++){
  const info=sim.advance(1/30);
  if(!info.finite||info.capacityRejected||!info.pressure.converged)throw Error(JSON.stringify(info));
  surf.density(sim.p,sim.count);
  const mesh=surf.mesh(sim.p,sim.count,null);
  const stem=String(frame).padStart(4,'0');
  const obj=new URL(`${stem}.obj`,out);
  writeObj(obj,mesh);
  const drops=new URL(`${stem}.drops`,out);
  fs.writeFileSync(drops,Buffer.from(mesh.drops.buffer,mesh.drops.byteOffset,mesh.drops.byteLength));
  const pe=particleEnergy();
  const tau=tauAt(sim.time);
  const row={
    frame,time:sim.time,tau,particles:sim.count,
    surfaceTriangles:mesh.positions.length/9,
    surfaceVolume:surf.lastMeshStats?.volume??null,
    surfaceTargetVolume:surf.lastMeshStats?.target??null,
    surfaceRelativeVolumeError:surf.lastMeshStats?.relativeError??null,
    ...pe,
    divergenceRms:info.divergenceAfter,
    divergenceMax:info.divergenceMax,
    projectionIterations:info.pressure.iterations,
    pressureRelativeResidual:info.pressure.relativeResidual,
    substeps:info.substeps,
    obj:`${stem}.obj`,
    drops:`${stem}.drops`,
    dropletCount:mesh.drops.length/3
  };
  manifest.frames.push(row);
  fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest,null,2));
  console.log(JSON.stringify(row),flush=>{});
}
manifest.simulationComplete=true;
fs.writeFileSync(new URL('manifest.json',out),JSON.stringify(manifest,null,2));
console.log('COMPLETE');
