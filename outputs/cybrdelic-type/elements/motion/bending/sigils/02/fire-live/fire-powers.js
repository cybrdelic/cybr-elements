// Authored supernatural sources feed the existing gas solve. These functions
// never draw a flame, lower resolution or allocate particle/texture resources.
import {shaderFunctionsToGLSL} from './shader-language.js?v=studio-rc-37-audit';
import {POWER_DEFINITIONS} from './fire-power-definitions.js?v=studio-rc-37-audit';
import {abilityMotionWGSL} from './fire-ability-motions.js?v=studio-rc-37-audit';
import {specializePowerSource} from './shader-specialization.js?v=studio-rc-37-audit';
export {POWER_DEFINITIONS};

export function powerDefinition(value) {
  if (typeof value === 'object' && value) value=value.power || value.id;
  if (typeof value === 'string') value=value.replace(/^legacy:/,'');
  return POWER_DEFINITIONS.find(p=>p.id===value||p.kind===value) || null;
}
export function normalizePowerSettings(value={}) {
  const number=(v,d,lo,hi)=>Number.isFinite(Number(v))?Math.max(lo,Math.min(hi,Number(v))):d;
  return {strength:number(value?.strength,1,.25,2),heading:number(value?.heading,0,-180,180),elevation:number(value?.elevation,9,-30,80)};
}
export function powerDirection(settings={}) {
  const {heading,elevation}=normalizePowerSettings(settings),a=heading*Math.PI/180,b=elevation*Math.PI/180;
  return [Math.cos(a)*Math.cos(b),Math.sin(b),Math.sin(a)*Math.cos(b)];
}

// Common analytic support and forces, translated to GLSL for Original. Scale
// affects spatial support; age remains simulation seconds (Pause pauses it).
export const powerSourceWGSL = `
fn powerRecording()->bool{return false;}
fn powerRecordProjectile(index:f32,a:vec3f,b:vec3f,duration:f32,arc:f32,radius:f32,t:f32)->bool{return false;}
fn powerResolvedContact(index:f32)->vec4f{return vec4f(-1,0,1,0);}

// Average a Gaussian release along one step of the carrier trajectory.
// This changes source integration, not gas resolution or rendered detail.
fn abilityErf(x:f32)->f32{
 let a:f32=abs(x);let t:f32=1./(1.+.3275911*a);
 let polynomial:f32=(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-.284496736)*t+.254829592)*t;
 return sign(x)*(1.-polynomial*exp(-a*a));
}
fn abilitySweptGaussian(d:vec3f,travel:vec3f)->f32{
 let distance:f32=length(travel);
 if(distance<.12){return exp(-dot(d,d)*1.2);}
 let along:f32=dot(d,travel)/distance;let perpendicular:f32=max(0.,dot(d,d)-along*along);
 let halfTravel:f32=.5*distance;
 return max(0.,exp(-1.2*perpendicular)*.8090107969*(abilityErf(1.095445115*(along+halfTravel))-abilityErf(1.095445115*(along-halfTravel)))/distance);
}
fn powerHash(p:vec3f)->f32{return fract(sin(dot(p,vec3f(127.1,311.7,74.7)))*43758.5453);}
// Four-corner tetrahedral gradient noise (simplex construction described by
// Gustavson, Simplex noise demystified). One octave, no noise texture or extra
// simulation pass. Applied to released material only, never to final pixels.
fn powerGradient(cell:vec3f)->vec3f{
 let n:f32=powerHash(cell);let g:vec3f=fract(vec3f(17.,59.,113.)*n)*2.-vec3f(1);
 return g/max(length(g),.001);
}
fn powerFold(q:vec3f,t:f32)->f32{
 let p:vec3f=q*2.1+vec3f(.23*t,-.65*t,.17*t);
 let cell:vec3f=floor(p+vec3f(dot(p,vec3f(.3333333333))));
 let a:vec3f=p-cell+vec3f(dot(cell,vec3f(.1666666667)));
 let order:vec3f=step(a.yzx,a.xyz);let opposite:vec3f=vec3f(1)-order;
 let first:vec3f=min(order,opposite.zxy);let second:vec3f=max(order,opposite.zxy);
 let b:vec3f=a-first+vec3f(.1666666667);let c:vec3f=a-second+vec3f(.3333333333);let d:vec3f=a-vec3f(.5);
 let w:vec4f=max(vec4f(.6)-vec4f(dot(a,a),dot(b,b),dot(c,c),dot(d,d)),vec4f(0));
 let squared:vec4f=w*w;let falloff:vec4f=squared*squared;
 let gradients:vec4f=vec4f(dot(powerGradient(cell),a),dot(powerGradient(cell+first),b),dot(powerGradient(cell+second),c),dot(powerGradient(cell+vec3f(1)),d));
 return clamp(dot(falloff,gradients)*64.,-1.,1.);
}
fn powerVortexOffset(height:f32,clock:f32)->vec2f{
 return vec2f(sin(height*1.7-clock*2.1),cos(height*2.3-clock*1.6))*clamp(height,0.,3.)*.075;
}
fn powerTornadoRadius(height:f32)->f32{return .18+.24*clamp(height,0.,3.);}
fn powerRainCenter(cell:vec2f,age:f32)->vec3f{
 let seed:f32=powerHash(vec3f(cell,3.71));
 let period:f32=1.1+.32*seed;let cycle:f32=age/period+seed;let phase:f32=fract(cycle);let batch:f32=floor(cycle);
 let jitter:vec2f=vec2f(powerHash(vec3f(cell,batch+2.)),powerHash(vec3f(cell,batch+7.)))-vec2f(.5);
 let drift:vec2f=vec2f(sin(phase*6.2831853+seed*13.),cos(phase*6.2831853+seed*7.))*.18;
 return vec3f((cell.x-1.)*1.1+jitter.x*.4+drift.x,4.12-4.10*pow(phase,1.35),(cell.y-1.)*1.1+jitter.y*.4+drift.y);
}
fn powerRainPacket(q:vec3f,cell:vec2f,age:f32)->vec4f{
 if(cell.x<0.||cell.x>2.||cell.y<0.||cell.y>2.){return vec4f(0);}
 let center:vec3f=powerRainCenter(cell,age);let delta:vec3f=q-center;
 if(abs(delta.x)>.65||abs(delta.z)>.65){return vec4f(0);}
 if((delta.y<-.65-12.*powerTimeStep()||delta.y>.8+12.*powerTimeStep())&&q.y>.4){return vec4f(0);}
 let seed:f32=powerHash(vec3f(cell,3.71));let period:f32=1.1+.32*seed;
 let cycle:f32=age/period+seed;let phase:f32=fract(cycle);
 let speed:f32=5.535*pow(max(phase,.04),.35)/period;
 let lateralSpeed:vec2f=vec2f(cos(phase*6.2831853+seed*13.),-sin(phase*6.2831853+seed*7.))*(1.1309734/period);
 let radius:vec3f=vec3f(.145,.23,.145);let carrier:vec3f=vec3f(lateralSpeed.x,-speed,lateralSpeed.y);
 let head:f32=abilitySweptGaussian(delta/radius*1.118033989,carrier*powerTimeStep()/radius*1.118033989);
 let wake:f32=exp(-dot(delta.xz,delta.xz)/.012)*smoothstep(0.,.13,delta.y)*(1.-smoothstep(.38,.75,delta.y))*.24;
 let impact:f32=smoothstep(.85,.97,phase);
 let disk:f32=exp(-dot(delta.xz,delta.xz)/.06)*exp(-pow((q.y+.08)/.12,2.))*impact*.55;
 if(head+wake+disk<.001){return vec4f(0);}
 let lateral:vec2f=delta.xz/max(length(delta.xz),.04);
 let velocity:vec3f=mix(vec3f(lateralSpeed.x,-speed,lateralSpeed.y),vec3f(lateral.x*2.8,1.4,lateral.y*2.8),impact*exp(-pow((q.y+.08)/.2,2.)));
 let weight:f32=(head+wake+disk)*(.65+.35*powerFold(delta,age+seed*5.))*1.4;
 return vec4f(velocity*weight,weight);
}
fn powerSupport(kind:f32,x:vec3f,origin:vec3f,scale:f32,age:f32,padding:f32)->bool{
 if(age<0.||scale<=0.){return false;}
 let q:vec3f=(x-origin)/max(scale,.05);
 let pad:f32=max(padding,0.)/max(scale,.05);
 if(kind<1.5){return age<=.45&&q.y>-.3-pad&&q.y<1.05+pad&&length(q.xz)<2.65+pad;}
 if(kind<2.5){return age<=1.15&&all(abs(q)<vec3f(4.15+pad));}
 if(kind<3.5){return abs(q.x)<2.35+pad&&abs(q.z)<2.35+pad&&q.y>-.5-pad&&q.y<4.95+pad;}
 if(kind<4.5){return length(q.xz)<2.25+pad&&q.y>-.22-pad&&q.y<4.25+pad;}
 if(kind<5.5){return false;}
 return age<=1.55&&all(abs(q)<vec3f(2.05+pad));
}
fn powerSource(kind:f32,x:vec3f,origin:vec3f,scale:f32,age:f32,clock:f32,direction:vec3f,strength:f32)->vec4f{
 if(!powerSupport(kind,x,origin,scale,age,0.)){return vec4f(0);}
 let q:vec3f=(x-origin)/max(scale,.05);
 let drive:f32=clamp(strength,.25,2.);
 if(kind<1.5){
  let r:f32=length(q.xz);let theta:f32=atan2(q.z,q.x);let ring:f32=.12+4.5*age;
  let lobes:f32=.09*sin(theta*9.+1.4*sin(theta*3.)+.8)+.045*sin(theta*17.-age*9.);
  let height:f32=.10+.075*sin(theta*7.+.8*cos(theta*3.)-age*11.)+.04*sin(theta*13.+age*7.);
  let v:f32=pow((r-ring-lobes)/.16,2.)+pow((q.y-height)/.17,2.);
  if(v>12.){return vec4f(0);}
  let axis:vec2f=q.xz/max(r,.02);
  let envelope:f32=1.-smoothstep(.20,.45,age);
  let pockets:f32=.2+.8*pow(.5+.5*sin(theta*11.+1.8*sin(theta*3.)+age*5.),2.);
  // Opposite velocity above/below the crest makes a rolling wake rather
  // than translating a perfectly smooth hot torus.
  let roll:f32=clamp((q.y-height)/.17,-1.,1.);
  let lift:f32=1.0+2.5*clamp((r-ring)/.16,-1.,1.);
  let spin:f32=.7*sin(theta*7.);
  return vec4f(vec3f(axis.x*(5.2+roll*2.)-axis.y*spin,lift,axis.y*(5.2+roll*2.)+axis.x*spin),1.35*exp(-v)*envelope*pockets*drive);
 }
 // Fireball uses abilityProjectile in powerCastSource; no second trajectory.
 if(kind<3.5){
  // The four adjacent lanes cover overlaps across cell boundaries. Every
  // packet rejects empty support before evaluating its fuel folds; no full
  // particle scan or new GPU resource is needed.
  let cell:vec2f=floor((q.xz+vec2f(1.1))/1.1);
  let a:vec4f=powerRainPacket(q,cell,age);let b:vec4f=powerRainPacket(q,cell+vec2f(1,0),age);
  let c:vec4f=powerRainPacket(q,cell+vec2f(0,1),age);let d:vec4f=powerRainPacket(q,cell+vec2f(1),age);
  let sum:vec4f=a+b+c+d;
  return vec4f(sum.xyz/max(sum.w,.00001),sum.w*drive);
 }
 if(kind<4.5){
  // A gathering foot feeds two rotating, widening fuel strands. These sheets
  // enter the same helical momentum field and break up through gas transport.
  let sway:vec2f=powerVortexOffset(q.y,clock);
  let radial:vec2f=q.xz-sway;let r:f32=length(radial);let theta:f32=atan2(radial.y,radial.x);
  let height:f32=max(q.y,0.);let width:f32=.17+.02*height;
  let radius:f32=powerTornadoRadius(height)+.035*sin(theta*5.-clock*3.);
  let v:f32=pow((r-radius)/width,2.);let foot:f32=exp(-r*r/.09)*exp(-q.y*q.y/.14);
  if(v>12.&&foot<.00001){return vec4f(0);}
  let tangent:vec3f=vec3f(-radial.y,0,radial.x)/max(r,.06);
  let feed:f32=.3+.7*smoothstep(-.4,.4,powerFold(vec3f(radial.x,q.y,radial.y)*1.4,clock));
  let ceiling:f32=.18+3.22*smoothstep(.02,.8,age);
  let ends:f32=smoothstep(-.22,-.10,q.y)*(1.-smoothstep(ceiling-.2,ceiling+.2,q.y))*(1.-smoothstep(2.9,3.4,q.y));
  let lift:f32=.8+1.3*smoothstep(0.,1.2,q.y);
  let taper:f32=.10+1.15*exp(-height*height/.55);
  let pockets:f32=.65+.35*powerFold(vec3f(radial.x,q.y,radial.y),clock);
  var shell:f32=0.;if(v<=12.){shell=exp(-v);}
  let fuel:f32=(.85*shell*feed+.45*foot)*ends*taper*pockets;
  return vec4f((tangent*(3.+.8*height)+vec3f(0,lift,0)),fuel*drive);
 }
 if(kind<5.5){return vec4f(0);}
 if(age<1.2){
  let orbit:vec3f=vec3f(cos(age*18.),.13*sin(age*11.),sin(age*18.))*.18;
  let delta:vec3f=q-orbit;let r:f32=length(delta);if(r>.45){return vec4f(0);}
  let gathering:f32=.5+.5*smoothstep(.3,1.2,age);
  return vec4f(-q.x*3.,.45,-q.z*3.,.7*exp(-pow(r/.16,2.))*gathering*drive);
 }
 let t:f32=age-1.2;let r:f32=length(q);
 let fold:f32=powerFold(q,t*2.);
 let radius:f32=.42+3.6*t+.16*fold;
 let pockets:f32=.45+.55*pow(.5+.5*fold,2.);
 let body:f32=(1.-smoothstep(radius-.22,radius+.06,r))*(1.-smoothstep(.10,.29,t))*pockets;
 if(body<=.001){return vec4f(0);}
 let axis:vec3f=q/max(r,.04);
 let swirl:vec3f=cross(vec3f(.3,.8,.5),q)*3.5;
 return vec4f((axis*(5.5+fold*1.5)+swirl+vec3f(0,1.8,0)),1.6*body*drive);
}
fn powerAcceleration(kind:f32,x:vec3f,origin:vec3f,scale:f32,age:f32,clock:f32,direction:vec3f,strength:f32)->vec3f{
 if(kind<3.5||kind>4.5||age<0.){return vec3f(0);}
 let q:vec3f=(x-origin)/max(scale,.05);let radial:vec2f=q.xz-powerVortexOffset(q.y,clock);let r:f32=length(radial);
 if(q.y<-.22||q.y>4.||r>1.6){return vec3f(0);}
 let core:f32=powerTornadoRadius(q.y);
 let band:f32=exp(-pow((r-core)/(.28+.025*max(q.y,0.)),2.));
 let ends:f32=smoothstep(-.22,-.10,q.y)*(1.-smoothstep(3.3,4.,q.y));
 let tangent:vec3f=vec3f(-radial.y,0,radial.x)/max(r,.1);
 let inward:vec3f=vec3f(-radial.x,0,-radial.y)/max(r,.1);
 let wobble:f32=1.+.12*sin(q.y*5.-clock*2.7);
 return (tangent*(7.*wobble)+inward*1.8+vec3f(0,1.7,0))*band*ends*clamp(strength,.25,2.);
}
${abilityMotionWGSL}
`;

const sourceCache=new Map();
export function powerSourceFor(kind,language='wgsl',additionalRoots=[]){
 if(language!=='wgsl'&&language!=='glsl')throw Error('Unknown shader language '+language);
 const key=String(kind)+':'+language+':'+[...additionalRoots].sort().join(',');
 if(!sourceCache.has(key)){
  const source=kind==null?powerSourceWGSL:specializePowerSource(powerSourceWGSL,kind,additionalRoots);
  sourceCache.set(key,language==='glsl'?shaderFunctionsToGLSL(source):source);
 }
 return sourceCache.get(key);
}
