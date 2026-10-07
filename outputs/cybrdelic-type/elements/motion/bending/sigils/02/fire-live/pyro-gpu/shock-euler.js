import {pruneShaderFunctions} from '../shader-specialization.js?v=studio-rc-37-repair';
import {solverParamsWGSL} from './solver-params.js?v=studio-rc-37-repair';
import {shockClockLayout,shockClockShaders} from './shock-gpu-clock.js?v=studio-rc-37-repair';
// Short-lived, conservative ideal-gas Euler stage for authored explosion powers.
// State is U=(rho, rho*u, rho*v, rho*w, E); no rendered particles or fake ring
// forces are involved. A dimensionally-split MUSCL/HLLE update keeps the work
// bounded while resolving the shock before momentum is handed to the fire flow.
export const SHOCK_GRID=32;
export const SHOCK_MAX_SUBSTEPS=12;
export const SHOCK_MAX_SIGNAL_SPEED=36;
export const SHOCK_CFL=.36;
export const SHOCK_GAMMA=1.4;
export const SHOCK_FLOW_TRANSFER_SECONDS=.42;

// Transfer the compressible solver's velocity impulse once per rendered
// interval. Applying a shock field as a target every CFL substep over-aligns
// the fire flow and erases the existing roll-up.
export function shockFlowTransferWeight(frameDt,remaining,stepIndex){
 if(!Number.isFinite(frameDt)||frameDt<0||!Number.isFinite(remaining)||remaining<0||!Number.isInteger(stepIndex)||stepIndex<0)throw Error('Invalid shock flow transfer interval');
 return stepIndex===0&&remaining>0?Math.min(frameDt,remaining)/SHOCK_FLOW_TRANSFER_SECONDS:0;
}

export function shockSubsteps(dt,N=SHOCK_GRID,maxSignal=SHOCK_MAX_SIGNAL_SPEED,cfl=SHOCK_CFL){
 if(!Number.isFinite(dt)||dt<0||!Number.isInteger(N)||N<8||!(maxSignal>0)||!(cfl>0&&cfl<1))throw Error('Invalid compressible shock timestep');
 if(dt===0)return 0;
 const required=Math.max(1,Math.ceil(dt*maxSignal/(6/N*cfl)));
 if(required>SHOCK_MAX_SUBSTEPS)throw Error(`Compressible blast CFL requires ${required} substeps; maximum is ${SHOCK_MAX_SUBSTEPS}`);
 return required;
}

export function hlleFlux(left,right,axis=0,gamma=SHOCK_GAMMA){
 if(left.length!==5||right.length!==5||![...left,...right].every(Number.isFinite)||![0,1,2].includes(axis))throw Error('Invalid Euler face state');
 const primitive=u=>{
  const rho=Math.max(u[0],1e-8),m=[u[1],u[2],u[3]],velocity=m.map(v=>v/rho),kinetic=.5*m.reduce((s,v)=>s+v*v,0)/rho;
  const pressure=Math.max((gamma-1)*(u[4]-kinetic),1e-8),sound=Math.sqrt(gamma*pressure/rho);
  return {rho,m,velocity,pressure,sound};
 },L=primitive(left),R=primitive(right),uL=L.velocity[axis],uR=R.velocity[axis];
 const flux=q=>{const p=primitive(q),u=p.velocity[axis],out=[p.rho*u,0,0,0,(q[4]+p.pressure)*u];
  for(let k=0;k<3;k++)out[k+1]=q[k+1]*u+(k===axis?p.pressure:0);return out;};
 const fL=flux(left),fR=flux(right),sL=Math.min(0,uL-L.sound,uR-R.sound),sR=Math.max(0,uL+L.sound,uR+R.sound);
 if(sL>=0)return fL;if(sR<=0)return fR;
 const span=sR-sL;return fL.map((v,i)=>(sR*v-sL*fR[i]+sL*sR*(right[i]-left[i]))/span);
}

// CPU reference used for conservation/positivity tests. The GPU uses the same
// face flux, states and one-dimensional split update (with a conservative floor
// mirror and open extrapolation on the other room bounds).
export function advanceEulerLine(state,dt,dx,axis=0){
 if(!Array.isArray(state)||!state.length||!(dt>=0)||!(dx>0))throw Error('Invalid Euler line');
 const n=state.length,fluxes=Array.from({length:n+1},(_,face)=>{
  const l=state[Math.max(0,face-1)],r=state[Math.min(n-1,face)];return hlleFlux(l,r,axis);
 });
 return state.map((q,i)=>q.map((value,c)=>value-dt/dx*(fluxes[i+1][c]-fluxes[i][c])));
}

// CPU mirror of the GPU's shared-face MUSCL positivity limiter.
export function advanceMusclEulerLine(state,dt,dx,axis=0){
 if(!Array.isArray(state)||!state.length||!(dt>=0)||!(dx>0))throw Error('Invalid Euler line');
 const at=i=>state[Math.max(0,Math.min(state.length-1,i))];
 const admissible=q=>q.every(Number.isFinite)&&q[0]>1e-5&&q[4]-q.slice(1,4).reduce((s,m)=>s+m*m,0)/(2*q[0])>1e-5;
 if(!state.every(admissible))throw Error('Inadmissible Euler input');
 const minmod=(a,b,c)=>a*b>0&&a*c>0?Math.sign(a)*Math.min(Math.abs(a),Math.abs(b),Math.abs(c)):0;
 const slope=(a,b,c)=>b.map((v,k)=>minmod(v-a[k],.5*(c[k]-a[k]),c[k]-v));
 const lambda=2*dt/dx;
 const fluxes=Array.from({length:state.length+1},(_,face)=>{
  const ql=at(face-1),qr=at(face),sl=slope(at(face-2),ql,qr),sr=slope(ql,qr,at(face+1));
  let left=ql.map((v,k)=>v+.5*sl[k]),right=qr.map((v,k)=>v-.5*sr[k]);
  if(!admissible(left))left=ql;if(!admissible(right))right=qr;
  const high=hlleFlux(left,right,axis),valid=f=>admissible(ql.map((v,k)=>v-lambda*f[k]))&&admissible(qr.map((v,k)=>v+lambda*f[k]));
  if(valid(high))return high;
  const low=hlleFlux(ql,qr,axis),useLow=valid(low);let lo=0,hi=1;
  const blend=t=>low.map((v,k)=>useLow?v+t*(high[k]-v):v*t);
  for(let j=0;j<(useLow?10:12);j++){const t=.5*(lo+hi);if(valid(blend(t)))lo=t;else hi=t;}
  return blend(lo);
 });
 return {state:state.map((q,i)=>q.map((v,k)=>v-dt/dx*(fluxes[i+1][k]-fluxes[i][k]))),boundaryFluxes:[fluxes[0],fluxes.at(-1)]};
}

const paramsWGSL=solverParamsWGSL+'@group(0) @binding(0) var<uniform> p:Params;';

export function shockInitWGSL(N=SHOCK_GRID){return `${paramsWGSL}
const N:u32=${N}u;const CELLS:u32=N*N*N;
@group(0) @binding(1) var<storage,read_write> rhoMomentum0:array<vec4f>;
@group(0) @binding(2) var<storage,read_write> totalEnergy0:array<f32>;
@group(0) @binding(3) var<storage,read_write> rhoMomentum1:array<vec4f>;
@group(0) @binding(4) var<storage,read_write> totalEnergy1:array<f32>;
@compute @workgroup_size(128) fn main(@builtin(global_invocation_id) id:vec3u){
 let i=id.x+N*(id.y+N*id.z);if(i>=CELLS){return;}
 rhoMomentum0[i]=vec4f(1.,0.,0.,0.);rhoMomentum1[i]=vec4f(1.,0.,0.,0.);
 totalEnergy0[i]=2.5;totalEnergy1[i]=2.5;
}`;}

const blastPowers={
 // Dimensionless energy units are calibrated against the unit ambient state;
 // they create an over-pressure wave rather than a prescribed velocity shell.
 'radial-blast':420,'fireball':220,'combustion-bomb':680,'flame-dash':300,'phoenix-dive':460,
 'solar-lance':190,'meteor-strike':560,'meteor-barrage':360,'eruption-chain':280,
 'combustion-mine':620,'vortex-burst':390,'flame-serpent':240,'cinder-scatter':190,
 'fire-cross':280,'flame-crescent':210,
};
const num=v=>Number.isInteger(v)?`${v}.`:String(v);
export function shockSourceWGSL(definitions){
 const active=definitions.filter(d=>d.blastWindows.length&&blastPowers[d.id]!==undefined);
 const conditions=active.flatMap(d=>d.blastWindows.map(w=>{
  const start=num(w.from),energy=num(blastPowers[d.id]*Math.pow(6/SHOCK_GRID,3));
  return `if(kind>${d.kind-.5}&&kind<${d.kind+.5}&&age<=shockImpact(k,${start}).x&&age+p.step.x>shockImpact(k,${start}).x){let offset=destination-origin;var center=origin;if(length(offset)>scale*.55){center=shockImpact(k,${start}).yzw;}let sigma=max(scale*.22,1.25*DX);let r2=dot((x-center)/sigma,(x-center)/sigma);let total=${energy}*clamp(strength,.25,2.)*pow(scale,3.);let normalization=15.74960995*sigma*sigma*sigma;source+=total/normalization*exp(-.5*r2);}`;
 })).join('\n ');
 return `fn shockImpact(actor:u32,fallback:f32)->vec4f{
 var recorded=false;var time=1e8;var point=p.casts[actor].targetCharge.xyz;
 for(var flight=0u;flight<6u;flight++){let hit=p.contacts[actor].hits[flight];
  if(hit.timing.y<=0.){continue;}recorded=true;
  if(hit.hit.x>=0.&&hit.hit.x<=1.){let at=hit.timing.x+hit.timing.y*hit.hit.x;
   if(at<time){time=at;point=hit.point.xyz+hit.hit.yzw*.04;}}
 }
 if(!recorded){return vec4f(fallback,point);}return vec4f(time,point);
}
fn blastEnergySource(x:vec3f)->f32{if(ctrl.inject==0u){return 0.;}var source=0.;
 for(var k=0u;k<4u;k++){let a=p.casts[k];if(a.kindScale.z<.5){continue;}
 let kind=a.kindScale.x;let age=a.originAge.w;let origin=a.originAge.xyz;let scale=max(a.kindScale.y,.05);let strength=a.directionStrength.w;let destination=a.targetCharge.xyz;
 ${conditions}
 }return source;}`;
}

export function shockAdvanceWGSL(N=SHOCK_GRID,axis=0,definitions=[],{gpuClock=false}={}){
 if(![0,1,2].includes(axis))throw Error('Invalid Euler sweep axis');
 let code=`${paramsWGSL}
struct ShockControl{dt:f32,inject:u32,pad:vec2u};
@group(0) @binding(1) var<uniform> ctrl:ShockControl;
@group(0) @binding(2) var<storage,read> oldRM:array<vec4f>;
@group(0) @binding(3) var<storage,read> oldE:array<f32>;
@group(0) @binding(4) var<storage,read_write> newRM:array<vec4f>;
@group(0) @binding(5) var<storage,read_write> newE:array<f32>;
const N:u32=${N}u;const AXIS:u32=${axis}u;const DX:f32=6.0/${N}.0;const GAMMA:f32=1.4;
struct U{rho:f32,mom:vec3f,energy:f32};
${shockSourceWGSL(definitions)}
fn linear(i:vec3i)->u32{return u32(i.x)+N*(u32(i.y)+N*u32(i.z));}
fn rawU(i:vec3i)->U{
 let q=clamp(i,vec3i(0),vec3i(i32(N)-1));let at=linear(q);var m=oldRM[at].yzw;
 if(i.y<0){m.y=-m.y;}
 var energy=max(oldE[at],1e-5);if(AXIS==0u&&ctrl.inject!=0u){let x=vec3f(-3,0,-3)+(vec3f(q)+.5)*DX;energy+=blastEnergySource(x);}
 return U(max(oldRM[at].x,1e-5),m,energy);
}
fn add(a:U,b:U)->U{return U(a.rho+b.rho,a.mom+b.mom,a.energy+b.energy);}
fn sub(a:U,b:U)->U{return U(a.rho-b.rho,a.mom-b.mom,a.energy-b.energy);}
fn mul(a:U,s:f32)->U{return U(a.rho*s,a.mom*s,a.energy*s);}
fn minmod(a:f32,b:f32,c:f32)->f32{return select(0.,sign(a)*min(min(abs(a),abs(b)),abs(c)),a*b>0.&&a*c>0.);}
fn slope(a:U,b:U,c:U)->U{return U(minmod(b.rho-a.rho,.5*(c.rho-a.rho),c.rho-b.rho),
 vec3f(minmod(b.mom.x-a.mom.x,.5*(c.mom.x-a.mom.x),c.mom.x-b.mom.x),minmod(b.mom.y-a.mom.y,.5*(c.mom.y-a.mom.y),c.mom.y-b.mom.y),minmod(b.mom.z-a.mom.z,.5*(c.mom.z-a.mom.z),c.mom.z-b.mom.z)),
 minmod(b.energy-a.energy,.5*(c.energy-a.energy),c.energy-b.energy));}
fn finite4(q:vec4f)->bool{return all(q==q)&&all(abs(q)<vec4f(1e20));}
fn admissible(q:U)->bool{if(q.rho<=1e-5||!finite4(vec4f(q.rho,q.mom))||!finite4(vec4f(q.energy,0,0,0))){return false;}let kinetic=dot(q.mom,q.mom)/(2.*q.rho);return q.energy-kinetic>1e-5;}
fn safe(q:U)->U{let rho=max(q.rho,1e-5);let mom=select(vec3f(0),q.mom,finite4(vec4f(q.mom,0)));let kinetic=dot(mom,mom)/(2.*rho);let energy=select(kinetic+1e-5,max(q.energy,kinetic+1e-5),finite4(vec4f(q.energy,0,0,0)));return U(rho,mom,energy);}
fn pressure(q:U)->f32{let s=safe(q);return max((GAMMA-1.)*(s.energy-dot(s.mom,s.mom)/(2.*s.rho)),1e-5);}
fn physicalFlux(q0:U)->U{
 let q=safe(q0);let velocity=q.mom/q.rho;let un=velocity[AXIS];let pr=pressure(q);var m=q.mom*un;m[AXIS]+=pr;
 return U(q.rho*un,m,(q.energy+pr)*un);
}
fn hlle(left0:U,right0:U)->U{
 let left=safe(left0);let right=safe(right0);let vl=left.mom/left.rho;let vr=right.mom/right.rho;
 let pl=pressure(left);let pr=pressure(right);let al=sqrt(GAMMA*pl/left.rho);let ar=sqrt(GAMMA*pr/right.rho);
 let sl=min(0.,min(vl[AXIS]-al,vr[AXIS]-ar));let sr=max(0.,max(vl[AXIS]+al,vr[AXIS]+ar));
 let fl=physicalFlux(left);let fr=physicalFlux(right);
 if(sl>=0.){return fl;}if(sr<=0.){return fr;}
 return mul(add(sub(mul(fl,sr),mul(fr,sl)),mul(sub(right,left),sl*sr)),1./max(sr-sl,1e-8));
}
fn validCell(i:vec3i)->bool{return all(i>=vec3i(0))&&all(i<vec3i(i32(N)));}
fn faceFlux(leftCell:vec3i)->U{
 var axis=vec3i(0);axis[AXIS]=1;
 let qll=rawU(leftCell-axis);let ql=rawU(leftCell);let qr=rawU(leftCell+axis);let qrr=rawU(leftCell+2*axis);
 var left=add(ql,mul(slope(qll,ql,qr),.5));var right=sub(qr,mul(slope(ql,qr,qrr),.5));
 if(!admissible(left)){left=ql;}if(!admissible(right)){right=qr;}
 // One shared flux must keep both one-sided states admissible. Their
 // half-sum is the full cell update; never reject individual cells.
 let high=hlle(left,right);let lambda=2.*ctrl.dt/DX;
 if(admissible(sub(ql,mul(high,lambda)))&&admissible(add(qr,mul(high,lambda)))){return high;}
 let low=hlle(ql,qr);
 if(admissible(sub(ql,mul(low,lambda)))&&admissible(add(qr,mul(low,lambda)))){
  var lo=0.;var hi=1.;for(var j=0u;j<10u;j++){let theta=.5*(lo+hi);let f=add(low,mul(sub(high,low),theta));
   if(admissible(sub(ql,mul(f,lambda)))&&admissible(add(qr,mul(f,lambda)))){lo=theta;}else{hi=theta;}}
  return add(low,mul(sub(high,low),lo));
 }
 var lo=0.;var hi=1.;for(var j=0u;j<12u;j++){let theta=.5*(lo+hi);let f=mul(low,theta);
  if(admissible(sub(ql,mul(f,lambda)))&&admissible(add(qr,mul(f,lambda)))){lo=theta;}else{hi=theta;}}
 return mul(low,lo);
}
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u){
 if(any(id>=vec3u(N))){return;}let i=vec3i(id);var axis=vec3i(0);axis[AXIS]=1;
 let q=rawU(i);let fm=faceFlux(i-axis);let fp=faceFlux(i);let factor=ctrl.dt/DX;
 var next=sub(q,mul(sub(fp,fm),factor));
 
 // Shared positive face contributions form an admissible convex update.
 let at=linear(i);newRM[at]=vec4f(next.rho,next.mom);newE[at]=next.energy;
}`;
 if(gpuClock){
  code=code.replace('var energy=max(oldE[at],1e-5);if(AXIS==0u&&ctrl.inject!=0u){let x=vec3f(-3,0,-3)+(vec3f(q)+.5)*DX;energy+=blastEnergySource(x);}', 'let energy=max(oldE[at],1e-5);');
  code=code.replace('const N:u32=',shockClockLayout+'@group(0) @binding(6) var<storage,read_write> clock:EulerClock;\nconst N:u32=');
  code=code.replaceAll('ctrl.dt','clock.dt');
  code=code.replace('let high=hlle(left,right);',`let pl=pressure(left);let pr=pressure(right);
   let speed=max(abs(left.mom[AXIS]/left.rho)+sqrt(GAMMA*pl/left.rho),abs(right.mom[AXIS]/right.rho)+sqrt(GAMMA*pr/right.rho));
   if(speed*clock.dt/DX>${SHOCK_CFL+.00001}){atomicOr(&clock.flags,2u);}
   let high=hlle(left,right);`);
  code=code.replace('let q=rawU(i);let fm=', 'if(clock.hold<=0.){return;}if(clock.dt<=0.){let at=linear(i);newRM[at]=oldRM[at];newE[at]=oldE[at];return;}\n let q=rawU(i);let fm=');
 }
 return code;
}

export function shockDepositWGSL(N=SHOCK_GRID,definitions=[]){return `${paramsWGSL}
const DX:f32=6./${N}.;
${shockSourceWGSL(definitions).replace('if(ctrl.inject==0u){return 0.;}','')}
${shockClockLayout}
@group(0) @binding(6) var<storage,read_write> clock:EulerClock;
@group(0) @binding(1) var<storage,read_write> momentum:array<vec4f>;
@group(0) @binding(2) var<storage,read_write> energy:array<f32>;
@group(0) @binding(3) var<storage,read_write> otherMomentum:array<vec4f>;
@group(0) @binding(4) var<storage,read_write> otherEnergy:array<f32>;
@compute @workgroup_size(128) fn main(@builtin(global_invocation_id) id:vec3u){
 if(id.x>=${N**3}u){return;}let i=vec3u(id.x%${N}u,(id.x/${N}u)%${N}u,id.x/${N*N}u);
 if(clock.hold<=0.){momentum[id.x]=vec4f(1,0,0,0);otherMomentum[id.x]=vec4f(1,0,0,0);energy[id.x]=2.5;otherEnergy[id.x]=2.5;}
 let x=vec3f(-3,0,-3)+(vec3f(i)+.5)*DX;let added=blastEnergySource(x);energy[id.x]+=added;
 if(added>0.){atomicStore(&clock.injected,1u);}
}`;}

export function shockSignalWGSL(N=SHOCK_GRID,definitions=[]){
 let code=shockAdvanceWGSL(N,0,[]);
 code=code.replace('var energy=max(oldE[at],1e-5);if(AXIS==0u&&ctrl.inject!=0u){let x=vec3f(-3,0,-3)+(vec3f(q)+.5)*DX;energy+=blastEnergySource(x);}','let energy=max(oldE[at],1e-5);');
 code=code.slice(0,code.indexOf('@compute @workgroup_size(4,4,4) fn main'));
 code=code.replace('@group(0) @binding(4) var<storage,read_write> newRM:array<vec4f>;','@group(0) @binding(4) var<storage,read_write> signal:array<atomic<u32>>;')
   .replace('@group(0) @binding(5) var<storage,read_write> newE:array<f32>;','');
 return code+shockClockLayout+'@group(0) @binding(6) var<storage,read_write> clock:EulerClock;'+`
 @compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u){
  if(any(id>=vec3u(N))||clock.remaining<=.00000001||(clock.hold<=0.&&atomicLoad(&clock.injected)==0u)){return;}let i=vec3i(id);
  var speed=0.;
  for(var axis=0u;axis<3u;axis++){
   var offset=vec3i(0);offset[axis]=1;
   let qll=rawU(i-offset);let ql=rawU(i);let qr=rawU(i+offset);let qrr=rawU(i+2*offset);
   var left=add(ql,mul(slope(qll,ql,qr),.5));var right=sub(qr,mul(slope(ql,qr,qrr),.5));
   if(!admissible(left)){left=ql;}if(!admissible(right)){right=qr;}
   speed=max(speed,max(length(left.mom/left.rho)+sqrt(GAMMA*pressure(left)/left.rho),length(right.mom/right.rho)+sqrt(GAMMA*pressure(right)/right.rho)));
  }
  atomicMax(&signal[0],bitcast<u32>(speed));
 }`;
}

export function shockProjectWGSL(N=SHOCK_GRID){return `
@group(0) @binding(60) var<storage,read> shockRM:array<vec4f>;
const SN:u32=${N}u;
fn shockLinear(i:vec3i)->u32{return u32(i.x)+SN*(u32(i.y)+SN*u32(i.z));}
fn shockVelocityAt(i:vec3i)->vec3f{let q=shockRM[shockLinear(clamp(i,vec3i(0),vec3i(i32(SN)-1)))];return q.yzw/max(q.x,1e-5);}
// The fine MAC grid is an integer refinement of the shock grid. Share the
// eight coarse corners between all six faces instead of resampling 48 times.
fn shockCorner(i:vec3i)->vec3f{let v=shockVelocityAt(i);return v*min(1.,24./max(length(v),1e-5));}
fn shockBlend(a:vec3f,b:vec3f,c:vec3f,d:vec3f,e:vec3f,f:vec3f,g:vec3f,h:vec3f,t0:vec3f)->vec3f{
 let t=clamp(t0,vec3f(0),vec3f(1));return mix(mix(mix(a,b,t.x),mix(c,d,t.x),t.y),mix(mix(e,f,t.x),mix(g,h,t.x),t.y),t.z);
}
fn shockMac(i:vec3u,n:u32,h:f32)->vec4f{
 // Shared corners are exact for an even integer refinement. Other test grids
 // use independently sampled faces rather than extrapolating across a brick.
 if(n<2u*SN||n%(2u*SN)!=0u){
  var velocity=vec3f(0);var div=0.;
  for(var k=0u;k<3u;k++){
   var x=vec3f(-3,0,-3)+(vec3f(i)+.5)*h;x[k]-=.5*h;
   let lower=shockVelocity(x)[k];x[k]+=h;let upper=shockVelocity(x)[k];
   velocity[k]=select(lower,0.,k==1u&&i.y==0u);div+=(upper-velocity[k])/h;
  }return vec4f(velocity,div);
 }

 let x=vec3f(-3,0,-3)+(vec3f(min(i,vec3u(n-1u)))+.5)*h;
 let q=(x-vec3f(-3,0,-3))*(f32(SN)/6.)-.5;
 let lo=clamp(vec3i(floor(q)),vec3i(0),vec3i(i32(SN)-2));let t=q-vec3f(lo);let half=h*f32(SN)/12.;
 let a=shockCorner(lo);let b=shockCorner(lo+vec3i(1,0,0));let c=shockCorner(lo+vec3i(0,1,0));let d=shockCorner(lo+vec3i(1,1,0));
 let e=shockCorner(lo+vec3i(0,0,1));let f=shockCorner(lo+vec3i(1,0,1));let g=shockCorner(lo+vec3i(0,1,1));let z=shockCorner(lo+vec3i(1,1,1));
 var velocity=vec3f(0);var div=0.;
 for(var k=0u;k<3u;k++){
  var minus=t;var plus=t;minus[k]-=half;plus[k]+=half;
  let lower=shockBlend(a,b,c,d,e,f,g,z,minus)[k];let upper=shockBlend(a,b,c,d,e,f,g,z,plus)[k];
  velocity[k]=select(lower,upper,i[k]==n);
  div+=(upper-select(lower,0.,k==1u&&i.y==0u))/h;
 }
 if(i.y==0u){velocity.y=0.;}return vec4f(velocity,div);
}
fn shockVelocity(x:vec3f)->vec3f{
 let q=(x-vec3f(-3,0,-3))*(f32(SN)/6.)-vec3f(.5);let lo=clamp(vec3i(floor(q)),vec3i(0),vec3i(i32(SN)-2));let t=clamp(q-vec3f(lo),vec3f(0),vec3f(1));
 let a=mix(shockVelocityAt(lo),shockVelocityAt(lo+vec3i(1,0,0)),t.x);
 let b=mix(shockVelocityAt(lo+vec3i(0,1,0)),shockVelocityAt(lo+vec3i(1,1,0)),t.x);
 let c=mix(shockVelocityAt(lo+vec3i(0,0,1)),shockVelocityAt(lo+vec3i(1,0,1)),t.x);
 let d=mix(shockVelocityAt(lo+vec3i(0,1,1)),shockVelocityAt(lo+vec3i(1,1,1)),t.x);
 let velocity=mix(mix(a,b,t.y),mix(c,d,t.y),t.z);let speed=length(velocity);return velocity*min(1.,24./max(speed,1e-5));
}`;}

export class CompressibleShockStage{
 constructor(device,definitions,{N=SHOCK_GRID}={}){this.device=device;this.definitions=definitions;this.N=N;this.current=0;this.cache=new Map();this.ids=new WeakMap();this.nextId=0;}
 async init(){
  const d=this.device,N=this.N,cells=N**3,storage=GPUBufferUsage.STORAGE|GPUBufferUsage.COPY_DST;
  this.states=Array.from({length:2},(_,index)=>({
   rm:d.createBuffer({label:`shock-rho-momentum-${index}`,size:cells*16,usage:storage}),
   energy:d.createBuffer({label:`shock-total-energy-${index}`,size:cells*4,usage:storage}),
  }));
  this.controls=Array.from({length:3*12},(_,index)=>d.createBuffer({label:`shock-control-${index}`,size:16,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST}));
  this.initPipeline=await this.pipeline(shockInitWGSL(N),'shock-euler-init');
  this.clock=d.createBuffer({label:'compressible-adaptive-clock',size:48,usage:storage|GPUBufferUsage.COPY_SRC});
  this.signal=d.createBuffer({label:'compressible-signal-speed',size:16,usage:storage});
  this.clockPipelines={};for(const [name,code] of Object.entries(shockClockShaders(N)))this.clockPipelines[name]=await this.pipeline(code,'shock-clock-'+name);
  this.signalPipeline=await this.pipeline(shockSignalWGSL(N),'shock-current-signal');
  this.depositPipeline=await this.pipeline(shockDepositWGSL(N,this.definitions),'shock-source-energy');
  this.advancePipelines=[];
  for(let axis=0;axis<3;axis++)this.advancePipelines[axis]=await this.pipeline(shockAdvanceWGSL(N,axis,this.definitions,{gpuClock:true}),'shock-euler-axis-'+axis);
  const initEncoder=d.createCommandEncoder({label:'initialize-conservative-shock-state'});
  const initGroup=d.createBindGroup({layout:this.initPipeline.getBindGroupLayout(0),entries:[
   {binding:1,resource:{buffer:this.states[0].rm}},{binding:2,resource:{buffer:this.states[0].energy}},
   {binding:3,resource:{buffer:this.states[1].rm}},{binding:4,resource:{buffer:this.states[1].energy}},
  ]});const initPass=initEncoder.beginComputePass();initPass.setPipeline(this.initPipeline);initPass.setBindGroup(0,initGroup);initPass.dispatchWorkgroups(Math.ceil(cells/128));initPass.end();d.queue.submit([initEncoder.finish()]);
  return this;
 }
 async pipeline(code,label){
  const module=this.device.createShaderModule({code:pruneShaderFunctions(code),label});const info=await module.getCompilationInfo();const errors=info.messages.filter(m=>m.type==='error');
  if(errors.length)throw Error(label+': '+errors.map(m=>`${m.lineNum}: ${m.message}`).join('\n'));
  return this.device.createComputePipelineAsync({layout:'auto',compute:{module,entryPoint:'main'},label});
 }
 bindGroup(pipeline,entries){const id=buffer=>{if(!this.ids.has(buffer))this.ids.set(buffer,++this.nextId);return this.ids.get(buffer);};
  const key=pipeline.label+':'+entries.map(e=>e.binding+'-'+id(e.resource.buffer)).join('/');
  if(!this.cache.has(key))this.cache.set(key,this.device.createBindGroup({layout:pipeline.getBindGroupLayout(0),entries}));return this.cache.get(key);}
 encode(encoder,paramBuffer,dt,outerIndex,frameSlot=0,reset=false){
  const steps=dt>0?SHOCK_MAX_SUBSTEPS:0;if(!steps)return;
  if(reset){encoder.clearBuffer(this.clock);this.current=0;const initGroup=this.device.createBindGroup({layout:this.initPipeline.getBindGroupLayout(0),entries:[
   {binding:1,resource:{buffer:this.states[0].rm}},{binding:2,resource:{buffer:this.states[0].energy}},
   {binding:3,resource:{buffer:this.states[1].rm}},{binding:4,resource:{buffer:this.states[1].energy}},
  ]});const initPass=encoder.beginComputePass({label:'reset-compressible-shock-state'});initPass.setPipeline(this.initPipeline);initPass.setBindGroup(0,initGroup);initPass.dispatchWorkgroups(Math.ceil(this.N**3/128));initPass.end();}
  const initial=this.controls[(frameSlot%3)*12+(outerIndex%12)];
  this.device.queue.writeBuffer(initial,0,new Float32Array([dt,0,0,0]));
  const clockPass=encoder.beginComputePass();clockPass.setPipeline(this.clockPipelines.begin);
  clockPass.setBindGroup(0,this.bindGroup(this.clockPipelines.begin,[{binding:0,resource:{buffer:initial}},{binding:1,resource:{buffer:this.clock}}]));clockPass.dispatchWorkgroups(1);clockPass.end();
  const deposit=encoder.beginComputePass();deposit.setPipeline(this.depositPipeline);
  deposit.setBindGroup(0,this.bindGroup(this.depositPipeline,[{binding:0,resource:{buffer:paramBuffer}},{binding:1,resource:{buffer:this.states[this.current].rm}},{binding:2,resource:{buffer:this.states[this.current].energy}},{binding:3,resource:{buffer:this.states[1-this.current].rm}},{binding:4,resource:{buffer:this.states[1-this.current].energy}},{binding:6,resource:{buffer:this.clock}}]));deposit.dispatchWorkgroups(Math.ceil(this.N**3/128));deposit.end();
  let slot=this.current;
  for(let iteration=0;iteration<steps;iteration++){
   encoder.clearBuffer(this.signal);
   const src=this.states[slot];const pass=encoder.beginComputePass({label:'compressible-adaptive-step'});
   pass.setPipeline(this.signalPipeline);pass.setBindGroup(0,this.bindGroup(this.signalPipeline,[{binding:2,resource:{buffer:src.rm}},{binding:3,resource:{buffer:src.energy}},{binding:4,resource:{buffer:this.signal}},{binding:6,resource:{buffer:this.clock}}]));
   pass.dispatchWorkgroups(Math.ceil(this.N/4),Math.ceil(this.N/4),Math.ceil(this.N/4));
   pass.setPipeline(this.clockPipelines.choose);pass.setBindGroup(0,this.bindGroup(this.clockPipelines.choose,[{binding:1,resource:{buffer:this.clock}},{binding:2,resource:{buffer:this.signal}}]));pass.dispatchWorkgroups(1);
   for(let axis=0;axis<3;axis++){
    const from=this.states[slot],to=this.states[1-slot],pipeline=this.advancePipelines[axis];
    const group=this.bindGroup(pipeline,[{binding:2,resource:{buffer:from.rm}},{binding:3,resource:{buffer:from.energy}},{binding:4,resource:{buffer:to.rm}},{binding:5,resource:{buffer:to.energy}},{binding:6,resource:{buffer:this.clock}}]);
    pass.setPipeline(pipeline);pass.setBindGroup(0,group);pass.dispatchWorkgroups(Math.ceil(this.N/4),Math.ceil(this.N/4),Math.ceil(this.N/4));slot=1-slot;
   }pass.end();
  }
  const final=encoder.beginComputePass();final.setPipeline(this.clockPipelines.finish);final.setBindGroup(0,this.bindGroup(this.clockPipelines.finish,[{binding:1,resource:{buffer:this.clock}}]));final.dispatchWorkgroups(1);final.end();

  this.current=slot;
 }
 bindings(){return this.states?.[this.current]?.rm||null;}
 destroy(){this.clock?.destroy();this.signal?.destroy();for(const state of this.states||[])for(const buffer of [state.rm,state.energy])buffer.destroy();for(const control of this.controls||[])control.destroy();this.cache.clear();}
}
