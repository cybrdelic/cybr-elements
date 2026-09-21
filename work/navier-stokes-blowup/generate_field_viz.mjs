#!/usr/bin/env node
/**
 * Field-faithful visualization geometry for the OpenAI Navier–Stokes blowup scaling.
 *
 * This is deliberately NOT a free-surface liquid surrogate.  It builds
 * stream-tube geometry from an explicit smooth axisymmetric divergence-free
 * similarity field whose leading time exponents match the paper:
 *
 *   L_r ~ tau^(1/2)
 *   L_z ~ tau^(1/2-h)
 *   |u_theta|, |u_z| ~ tau^(-1/2-h)
 *   |u_r| ~ tau^(-1/2)
 *   E_core ~ tau^(1/2-3h)
 *
 * The exact OpenAI construction contains additional E/U/Pi pieces, annular
 * pulses and forcing; this script is a visualization of the leading core
 * mechanism, not a reproduction of the full theorem solution.
 */
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const arg = (name, fallback) => {
  const i = argv.indexOf(name);
  return i >= 0 ? argv[i + 1] : fallback;
};
const outDir = path.resolve(arg('--out', 'rendered/navier-stokes-field'));
const frames = Math.max(2, Number(arg('--frames', '10')));
const tauMax = Number(arg('--tau-max', '0.28'));
const tauMin = Number(arg('--tau-min', '0.006'));
const h = Number(arg('--h', '0.009'));
const tubeSides = Math.max(4, Number(arg('--tube-sides', '6')));
const seedRings = Math.max(6, Number(arg('--seed-rings', '12')));

fs.mkdirSync(outDir, { recursive: true });

const vadd = (a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]];
const vsub = (a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]];
const vmul = (a,s)=>[a[0]*s,a[1]*s,a[2]*s];
const vdot = (a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
const vcross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
const vlen = a => Math.sqrt(vdot(a,a));
const vnorm = a => { const n=vlen(a); return n>1e-14?vmul(a,1/n):[0,0,0]; };

function scales(tau) {
  const A = 0.5 + h;
  const D = 0.5 - h;
  return {
    tau, A, D,
    radial: Math.pow(tau, 0.5),
    axial: Math.pow(tau, D),
    tangential: Math.pow(tau, -A),
    radialVelocity: Math.pow(tau, -0.5),
    energyScale: Math.pow(tau, 0.5 - 3*h),
  };
}

/**
 * Smooth axisymmetric divergence-free field.
 *
 * Poloidal part is generated from streamfunction
 *   psi = C/tau * r^2 z exp[-(r/Lr)^2-(z/Lz)^2]
 * so div(u_r e_r + u_z e_z)=0 identically.
 * Axisymmetric swirl adds no divergence.
 */
function velocity(p, tau) {
  const s = scales(tau);
  const [x,y,z] = p;
  const r = Math.hypot(x,y);
  const Lr = s.radial, Lz = s.axial;
  const rr = r / Lr, zz = z / Lz;
  const env = Math.exp(-(rr*rr + zz*zz));
  const C = 0.82;
  const Cs = 1.22;
  const ur = -(C/tau) * r * env * (1 - 2*zz*zz);
  const uz =  (2*C/tau) * z * env * (1 - rr*rr);
  const utheta = Cs * Math.pow(tau, -(0.5+h)) * rr * env;
  const c = r > 1e-14 ? x/r : 1;
  const sn = r > 1e-14 ? y/r : 0;
  return [ur*c - utheta*sn, ur*sn + utheta*c, uz];
}

function normalizedRadius(p, s) {
  return Math.hypot(Math.hypot(p[0],p[1])/s.radial, p[2]/s.axial);
}

function integrateLine(seed, tau, sign) {
  const s = scales(tau);
  const step = 0.085 * s.radial;
  const pts = [seed.slice()];
  let p = seed.slice();
  for (let i=0;i<42;i++) {
    const u1 = velocity(p,tau);
    const n1 = vnorm(u1);
    if (vlen(n1) < 1e-12) break;
    const mid = vadd(p, vmul(n1, sign*0.5*step));
    const n2 = vnorm(velocity(mid,tau));
    const q = vadd(p, vmul(n2, sign*step));
    if (!q.every(Number.isFinite) || normalizedRadius(q,s) > 3.1) break;
    pts.push(q);
    p = q;
  }
  return pts;
}

function streamline(seed, tau) {
  const a = integrateLine(seed,tau,-1).reverse();
  const b = integrateLine(seed,tau,+1);
  return a.slice(0,-1).concat(b);
}

function mesh() { return {v:[], f:[]}; }

function addCylinder(m,a,b,r,sides=tubeSides) {
  const axis = vsub(b,a);
  const L = vlen(axis);
  if (!(L>1e-10)) return;
  const w = vmul(axis,1/L);
  const ref = Math.abs(w[2]) < 0.9 ? [0,0,1] : [0,1,0];
  const u = vnorm(vcross(w,ref));
  const v = vcross(w,u);
  const base = m.v.length;
  for (const p of [a,b]) {
    for (let j=0;j<sides;j++) {
      const t = 2*Math.PI*j/sides;
      m.v.push(vadd(p, vadd(vmul(u,r*Math.cos(t)), vmul(v,r*Math.sin(t)))));
    }
  }
  for (let j=0;j<sides;j++) {
    const k=(j+1)%sides;
    const a0=base+j, a1=base+k, b0=base+sides+j, b1=base+sides+k;
    m.f.push([a0,a1,b1],[a0,b1,b0]);
  }
}

function addPolylineBySpeed(lines, tau, bins, tubeRadius, referenceSpeed) {
  let maxSpeed = 0;
  for (const pts of lines) {
    for (let i=0;i+1<pts.length;i++) {
      const a=pts[i], b=pts[i+1];
      const mid=vmul(vadd(a,b),0.5);
      const speed=vlen(velocity(mid,tau));
      maxSpeed=Math.max(maxSpeed,speed);
      const q=speed/referenceSpeed;
      const bi = q < 0.75 ? 0 : q < 1.5 ? 1 : q < 3.0 ? 2 : 3;
      addCylinder(bins[bi],a,b,tubeRadius);
    }
  }
  return maxSpeed;
}

function addCoreCage(m, s) {
  const rTube = 0.0065*s.radial;
  const addLoop = pts => {
    for (let i=0;i<pts.length;i++) addCylinder(m,pts[i],pts[(i+1)%pts.length],rTube,5);
  };
  // Equatorial ellipses.
  for (const zeta of [-0.8,0,0.8]) {
    const z=zeta*s.axial;
    const rr=s.radial*Math.sqrt(Math.max(0,1-zeta*zeta))*1.35;
    const pts=[];
    for (let i=0;i<48;i++) {
      const t=2*Math.PI*i/48;
      pts.push([rr*Math.cos(t),rr*Math.sin(t),z]);
    }
    addLoop(pts);
  }
  // Meridians.
  for (let a=0;a<8;a++) {
    const theta=2*Math.PI*a/8;
    const pts=[];
    for (let i=0;i<64;i++) {
      const t=2*Math.PI*i/64;
      const rr=1.35*s.radial*Math.cos(t);
      const z=1.35*s.axial*Math.sin(t);
      pts.push([rr*Math.cos(theta),rr*Math.sin(theta),z]);
    }
    addLoop(pts);
  }
}

function writeObj(file,m) {
  let s = '# CYBR ELEMENTS field visualization mesh\n';
  for (const p of m.v) s += `v ${p[0].toPrecision(10)} ${p[1].toPrecision(10)} ${p[2].toPrecision(10)}\n`;
  for (const f of m.f) s += `f ${f[0]+1} ${f[1]+1} ${f[2]+1}\n`;
  fs.writeFileSync(file,s);
}

function numericEnergyAndMax(tau) {
  const s=scales(tau);
  const nr=36, nz=72;
  const rMax=4*s.radial, zMax=4*s.axial;
  const dr=rMax/nr, dz=2*zMax/nz;
  let E=0, maxU=0;
  for (let ir=0;ir<nr;ir++) {
    const r=(ir+0.5)*dr;
    for (let iz=0;iz<nz;iz++) {
      const z=-zMax+(iz+0.5)*dz;
      const u=velocity([r,0,z],tau);
      const q=vdot(u,u);
      const dV=2*Math.PI*r*dr*dz;
      E += 0.5*q*dV;
      maxU=Math.max(maxU,Math.sqrt(q));
    }
  }
  return {energy:E,maxSpeed:maxU};
}

const taus = Array.from({length:frames},(_,i)=>{
  const a=i/(frames-1);
  return tauMax*Math.pow(tauMin/tauMax,a);
});

const firstSample = numericEnergyAndMax(taus[0]);
const referenceSpeed = firstSample.maxSpeed;
const rows=[];

for (let fi=0;fi<frames;fi++) {
  const tau=taus[fi];
  const s=scales(tau);
  const lines=[];
  for (const zeta of [-1.05,-0.45,0,0.45,1.05]) {
    for (let a=0;a<seedRings;a++) {
      const theta=2*Math.PI*(a/seedRings + 0.07*zeta);
      const rr=0.72*s.radial*(1+0.08*Math.sin(3*theta+0.4*zeta));
      lines.push(streamline([rr*Math.cos(theta),rr*Math.sin(theta),zeta*s.axial],tau));
    }
  }

  const bins=[mesh(),mesh(),mesh(),mesh()];
  const tubeRadius=0.0105*s.radial;
  const lineMax=addPolylineBySpeed(lines,tau,bins,tubeRadius,referenceSpeed);
  const cage=mesh();
  addCoreCage(cage,s);

  const frameDir=path.join(outDir,'frames',String(fi).padStart(4,'0'));
  fs.mkdirSync(frameDir,{recursive:true});
  const binFiles=[];
  for (let b=0;b<4;b++) {
    const p=path.join(frameDir,`speed_${b}.obj`);
    writeObj(p,bins[b]);
    binFiles.push(path.relative(outDir,p));
  }
  const cagePath=path.join(frameDir,'core_cage.obj');
  writeObj(cagePath,cage);

  const numeric=numericEnergyAndMax(tau);
  const row={
    frame:fi,tau,t:1-tau,
    radialScale:s.radial,
    axialScale:s.axial,
    characteristicSpeed:s.tangential,
    characteristicRadialSpeed:s.radialVelocity,
    expectedEnergyScale:s.energyScale,
    numericEnergy:numeric.energy,
    numericEnergyRelative:numeric.energy/firstSample.energy,
    gridMaxSpeed:numeric.maxSpeed,
    maxSpeedRelative:numeric.maxSpeed/referenceSpeed,
    streamlineMaxSpeed:lineMax,
    speedBins:binFiles,
    cage:path.relative(outDir,cagePath),
    disclosure:'Leading-core divergence-free visualization surrogate; not the full E/U/Pi + annular-pulse + forcing construction.'
  };
  rows.push(row);
  console.log(JSON.stringify(row));
}

const config={
  frames,tauMax,tauMin,h,
  field:'axisymmetric divergence-free streamfunction + swirl',
  streamfunction:'psi=(0.82/tau) r^2 z exp(-(r/Lr)^2-(z/Lz)^2)',
  swirl:'u_theta=1.22 tau^(-1/2-h) (r/Lr) exp(-(r/Lr)^2-(z/Lz)^2)',
  exponents:{
    radialScale:'tau^(1/2)',
    axialScale:'tau^(1/2-h)',
    dominantVelocity:'tau^(-1/2-h)',
    energy:'tau^(1/2-3h)'
  },
  referenceSpeed,
  noImageGeneration:true,
  disclosure:'Visualization of the leading shrinking-core mechanism described by the OpenAI paper. It is not the exact theorem field and does not include the complete E/U/Pi construction, annular pulse correction, or forcing.'
};
fs.writeFileSync(path.join(outDir,'config.json'),JSON.stringify(config,null,2));
fs.writeFileSync(path.join(outDir,'metrics.json'),JSON.stringify(rows,null,2));
