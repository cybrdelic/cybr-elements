import {occupancyReductionWGSL} from './occupancy-reduction.js?v=studio-rc-37-repair';
import {solverParamsWGSL} from './solver-params.js?v=studio-rc-37-repair';
import {gasThermoWGSL,GAS_THERMO,PLUME_THERMAL} from '../gas-thermodynamics.js?v=studio-rc-37-repair';
import {reactionLedgerWGSL} from '../reaction-ledger.js?v=studio-rc-37-repair';
import {pressureSourceProducerWGSL} from '../pressure-source-cache.js?v=studio-rc-37-repair';
import {GAS_DIFFUSIVITY,PRODUCT_DIFFUSIVITY} from '../gas-transport.js?v=studio-rc-37-repair';
import {objectWGSL} from './objects.js?v=studio-rc-37-repair';
import {combustionWGSL,objectCombustionWGSL} from './combustion.js?v=studio-rc-37-repair';
import {floorFuelWGSL} from './floor-fuel.js?v=studio-rc-37-repair';
import {SMOKE_CLEAR_DENSITY} from '../smoke-lifecycle.js?v=studio-rc-37-repair';
import {woodFluxWGSL} from './wood-flux.js?v=studio-rc-37-repair';
import {powerSourceWGSL, powerSourceFor, POWER_DEFINITIONS} from '../fire-powers.js?v=studio-rc-37-repair';
import {GAS_CHEMISTRY,sourceMixingWGSL} from '../reduced-chemistry.js?v=studio-rc-37-repair';
import {pruneShaderFunctions} from '../shader-specialization.js?v=studio-rc-37-repair';
import {shockProjectWGSL} from './shock-euler.js?v=studio-rc-37-repair';
// MAC velocity components live on their own faces in one (N+1)^3 texture.
// Scalars live at cell centers. All distances and velocities use world units.
export function simulationShaders(N=128,D=256,{flowSupport=false,directVorticity=true,hasPowers=true,powerKind=null,woodCadence=false,subgroups=false,prune=true,pressureCache=false}={}){
let common=`
${combustionWGSL}
${objectWGSL}
${objectCombustionWGSL}
${woodFluxWGSL}
const N:u32=${N}u;const D:u32=${D}u;const H:f32=6.0/${N}.0;
const LO=vec3f(-3,0,-3);const EXT=vec3f(6);
${solverParamsWGSL}
var<private> powerActorIndex:u32;

@group(0) @binding(0) var<uniform> p:Params;
@group(0) @binding(1) var smp:sampler;
@group(0) @binding(8) var sigilSource:texture_2d<f32>;
${floorFuelWGSL}
fn hash(a:vec3f)->f32{return fract(sin(dot(a,vec3f(127.1,311.7,74.7)))*43758.5453);}
fn noise(x:vec3f)->f32{let i=floor(x);let a=fract(x);let f=a*a*(3.0-2.0*a);return mix(mix(mix(hash(i),hash(i+vec3f(1,0,0)),f.x),mix(hash(i+vec3f(0,1,0)),hash(i+vec3f(1,1,0)),f.x),f.y),mix(mix(hash(i+vec3f(0,0,1)),hash(i+vec3f(1,0,1)),f.x),mix(hash(i+vec3f(0,1,1)),hash(i+vec3f(1)),f.x),f.y),f.z);}
fn mac(t:texture_3d<f32>,x:vec3f)->vec3f{
 let q=(x-LO)/H;let z=f32(N+1u);
 return vec3f(textureSampleLevel(t,smp,(q+vec3f(.5,0,0))/z,0).x,textureSampleLevel(t,smp,(q+vec3f(0,.5,0))/z,0).y,textureSampleLevel(t,smp,(q+vec3f(0,0,.5))/z,0).z);
}
fn component(t:texture_3d<f32>,x:vec3f,k:u32)->f32{var off=vec3f(0);off[k]=.5;return textureSampleLevel(t,smp,((x-LO)/H+off)/f32(N+1u),0)[k];}
fn scalar(t:texture_3d<f32>,x:vec3f)->vec4f{if(any(x<LO)||any(x>LO+EXT)){return vec4f(0);}return textureSampleLevel(t,smp,(x-LO)/EXT,0);}
fn trace(t:texture_3d<f32>,x:vec3f,dt:f32)->vec3f{return x-dt*mac(t,x-.5*dt*mac(t,x));}
fn face(i:vec3u,k:u32)->vec3f{var v=vec3f(.5);v[k]=0.;return LO+(vec3f(i)+v)*H;}
fn loadV(t:texture_3d<f32>,i:vec3i)->vec4f{return textureLoad(t,clamp(i,vec3i(0),vec3i(i32(N))),0);}
fn segment2(p:vec2f,a:vec2f,b:vec2f)->f32{let d=b-a;return length(p-a-d*clamp(dot(p-a,d)/dot(d,d),0.,1.));}
fn glyphDistance(q:vec2f,kind:f32)->f32{
 var d=1e4;
 if(kind<8.5){
  for(var i=0u;i<3u;i++){let a=1.5707963+f32(i)*2.0943951;let b=a+2.0943951;d=min(d,segment2(q,.73*vec2f(cos(a),sin(a)),.73*vec2f(cos(b),sin(b))));}
  return min(d,abs(length(q)-.92));
 }
 if(kind<9.5){
  for(var i=0u;i<5u;i++){let a=1.5707963+f32(i)*1.2566371;let b=a+2.5132741;d=min(d,segment2(q,.78*vec2f(cos(a),sin(a)),.78*vec2f(cos(b),sin(b))));}
  return min(d,abs(length(q)-.92));
 }
 if(kind<11.5){
  d=segment2(q,vec2f(0,-.8),vec2f(0,.8));
  d=min(d,segment2(q,vec2f(0,.05),vec2f(-.62,.65)));d=min(d,segment2(q,vec2f(0,.05),vec2f(.62,.65)));
  d=min(d,segment2(q,vec2f(0,-.25),vec2f(-.48,-.65)));d=min(d,segment2(q,vec2f(0,-.25),vec2f(.48,-.65)));
  return min(d,abs(abs(q.x)+abs(q.y+.2)-.32)*.7071068);
 }
 return abs(length(q)-.72);
}
fn jetDirection()->vec3f{
 let t=p.step.y;let sweep=select(0.,sin(t*1.8)*.7,p.effect.x>19.5);
 return normalize(vec3f(cos(sweep),.24+.12*sin(t*2.1),sin(sweep)));
}
${sourceMixingWGSL}
${gasThermoWGSL}
fn powerTimeStep()->f32{return p.step.x;}
${powerSourceWGSL}
fn powerKind()->f32{return p.effect.x-21.;}
fn isPower()->bool{return ${POWER_DEFINITIONS.map(definition=>`p.effect.x==${definition.kind+21}.`).join('||')};}
struct PowerInjection{gas:vec4f};
fn powerInjection(x:vec3f)->PowerInjection{
 if(p.source.w<.5){return PowerInjection(vec4f(0));}
 var momentum=vec3f(0);var weight=0.;
 for(var i=0u;i<4u;i++){
  let actor=p.casts[i];powerActorIndex=i;if(actor.kindScale.z<.5){continue;}
  let value=powerCastSource(actor.kindScale.x,x,actor.originAge.xyz,actor.kindScale.y,sourceSampleAge(actor.originAge.w,actor.kindScale.z,p.step.x),sourceClock(p.step.y,actor.kindScale.w,p.step.x),actor.directionStrength.xyz,actor.directionStrength.w,actor.targetCharge.xyz,actor.targetCharge.w);
  momentum+=value.xyz*value.w;weight+=value.w;
 }
 return PowerInjection(vec4f(momentum/max(weight,.00001),weight));
}
fn powerSample(x:vec3f)->vec4f{let sample=powerInjection(x);return sample.gas;}
fn powerForce(x:vec3f)->vec3f{
 if(p.source.w<.5){return vec3f(0);}
 var force=vec3f(0);
 for(var i=0u;i<4u;i++){
  let actor=p.casts[i];powerActorIndex=i;if(actor.kindScale.z<.5){continue;}
  force+=powerCastAcceleration(actor.kindScale.x,x,actor.originAge.xyz,actor.kindScale.y,sourceSampleAge(actor.originAge.w,actor.kindScale.z,p.step.x),sourceClock(p.step.y,actor.kindScale.w,p.step.x),actor.directionStrength.xyz,actor.directionStrength.w,actor.targetCharge.xyz,actor.targetCharge.w);
 }
 return force;
}
fn powerBrickLive(at:vec3f,halfBrick:f32)->bool{
 if(p.source.w<.5){return false;}
 for(var i=0u;i<4u;i++){
  let actor=p.casts[i];powerActorIndex=i;if(actor.kindScale.z<.5){continue;}
  if(powerCastSupport(actor.kindScale.x,at,actor.originAge.xyz,actor.kindScale.y,sourceSampleAge(actor.originAge.w,actor.kindScale.z,p.step.x),halfBrick*1.733+.5*24.*max(actor.kindScale.y,1.)*p.step.x,actor.targetCharge.xyz,actor.directionStrength.xyz,actor.targetCharge.w)){return true;}
 }
 return false;
}
fn charge(x:vec3f)->f32{
 if(abs(object.tint.w)>.5){return 0.;}
 if(isPower()){return powerSample(x).w;}
 if(p.source.w<.5||p.step.z<0.||(p.effect.w<.5&&p.step.z>p.effect.z)){return 0.;}
 let q=(x-p.source.xyz)/p.effect.y;
 if(object.options.x>.5){return surfaceFeed(x);}
 if(p.effect.x>18.5){
  let d=jetDirection();let axial=dot(q,d);let radial=length(q-d*axial);
  let r2=pow(radial/.14,2.)+pow(axial/.20,2.);if(r2>32.){return 0.;}
  let pulse=select(1.,1.-smoothstep(.22,.30,fract(p.step.z/.82)),p.effect.x>20.5);
  let breakup=.35+.9*noise(q*28.+vec3f(p.step.y*7.,p.step.y*-11.,p.step.y*5.));
  return exp(-r2)*pulse*breakup;
 }
 // Continuous effect-zero source is the sooty plume: emit from a broad,
 // shallow footprint instead of the default rounded cloud or hearth jets.
 if(p.effect.x<.5&&p.effect.w>.5){
  let r2=dot(q/vec3f(.62,.20,.44),q/vec3f(.62,.20,.44));
  if(r2>32.){return 0.;}
  // An unsteady fuel bed breaks the startup torus through transported
  // mixture variations; no detail is painted into the volume renderer.
  let n=noise(q*7.+vec3f(p.step.y*.83,2.7,4.1-p.step.y*.61));
  return exp(-1.25*r2)*mix(.55,1.37,smoothstep(.2,.8,n));
 }
 if(p.effect.x>.5){
  if(any(abs(q)>vec3f(1.6))){return 0.;}
  var r2=dot(q/vec3f(.26,.12,.26),q/vec3f(.26,.12,.26));
  if(p.effect.x>1.5&&p.effect.x<2.5){r2=pow((length(q.xz)-.65)/.12,2.)+pow(q.y/.10,2.);}
  if(p.effect.x>2.5&&p.effect.x<3.5){r2=pow(max(abs(q.x)-1.,0.)/.15,2.)+pow(q.y/.12,2.)+pow(q.z/.15,2.);}
  if(p.effect.x>3.5&&p.effect.x<4.5){r2=pow((length(q)-.52)/.12,2.);}
  if(p.effect.x>4.5&&p.effect.x<5.5){r2=pow((max(abs(q.x),max(abs(q.y),abs(q.z)))-.6)/.055,2.);}
  if(p.effect.x>5.5&&p.effect.x<6.5){let a=q.y*7.8539816;let radial=length(q.xz-.5*vec2f(cos(a),sin(a)));r2=pow(radial/.075,2.)+pow(max(abs(q.y)-.8,0.)/.06,2.);}
  if(p.effect.x>6.5&&p.effect.x<7.5){let nearJet=vec3f(abs(q.x)-.48,q.y,q.z)/vec3f(.12,.10,.12);r2=dot(nearJet,nearJet);}
  var support=1.;
  if(p.effect.x>7.5&&p.effect.x<12.5){
   let isCybr=p.effect.x>9.5&&p.effect.x<10.5;
   if(abs(q.z)>select(.3,.65,isCybr)){return 0.;}
   var stroke=0.;
   if(p.effect.x>9.5&&p.effect.x<10.5){
    let uv=vec2f((q.x*4.+7.)/14.,(q.y*4.+2.95)/7.875);
    support=textureSampleLevel(sigilSource,smp,uv,0).r;
   }else{stroke=glyphDistance(q.xy,p.effect.x);}
   r2=pow(stroke/.045,2.)+pow(q.z/select(.055,.14,isCybr),2.);
  }
  // Two inward-facing nozzles; their momentum meets above the source.
  if(p.effect.x>12.5&&p.effect.x<13.5){let nozzle=vec3f(abs(q.x)-.65,q.y,q.z)/vec3f(.10,.12,.12);r2=dot(nozzle,nozzle);}
  // A broad shallow fuel bed tests a large connected smoke sheet.
  if(p.effect.x>13.5&&p.effect.x<14.5){r2=pow(max(abs(q.x)-.7,0.)/.12,2.)+pow(q.y/.08,2.)+pow(max(abs(q.z)-.7,0.)/.12,2.);}
  let feed=noise(q*12.+vec3f(0,p.step.y*2.,0));
  return support*exp(-1.5*r2)*select(.65+.35*feed,.08+1.15*smoothstep(.25,.75,feed),p.effect.w>.5);
 }
 let r=length(q);if(r>.7){return 0.;}
 let n=noise(q*9.+vec3f(p.shape.x,13.7,4.1));
 let radius=.39+(.16*n)+.045*sin(atan2(q.z,q.x)*5.+q.y*11.);
 return (1.-smoothstep(radius-.10,radius+.03,r))*(.6+.4*noise(q*16.+8.));
}
fn sourceVelocity(x:vec3f)->vec3f{
 let q=x-p.source.xyz;let r=length(q);let dir=q/max(r,.03);
 if(isPower()){return powerSample(x).xyz;}
 if(object.options.x>.5){return (objectNormal(x)*.32+vec3f(0,.65,0))*p.dynamics.x;}
 if(p.effect.x<.5&&p.effect.w>.5){
  // Independent transverse shear from a curl field. The old single
  // noise value locked x and z together and sustained one coherent cap.
  let inlet=curlTurbulence(q,8.4,1.7,vec2f(.8,.6))/8.4;
  return (vec3f(0,.92,0)+inlet*vec3f(.70,.22,.70))*p.dynamics.x;
 }
 if(p.effect.x>18.5){let d=jetDirection();let side=normalize(cross(d,vec3f(0,1,0)));let up=cross(side,d);let jitter=vec2f(noise(q*22.+vec3f(p.step.y*9.,4,8)),noise(q*22.+vec3f(3,p.step.y*11.,7)))*2.-1.;return d*p.dynamics.x*5.+(side*jitter.x+up*jitter.y)*1.4;}
 let asym=1.+.35*sin(atan2(q.z,q.x)*3.+q.y*7.);
 if(p.effect.x>12.5&&p.effect.x<13.5){return vec3f(-sign(q.x)*3.4,2.0,0)*p.dynamics.x;}
 if(p.effect.w>.5){return (vec3f(-q.z*2.*p.dynamics.z,3.8,q.x*2.*p.dynamics.z)+select(vec3f(0),dir*2.,p.effect.x>3.5&&p.effect.x<5.5))*p.dynamics.x;}
 return (dir*(3.8*asym)+vec3f(-q.z*2.*p.dynamics.z,1.6,q.x*2.*p.dynamics.z))*p.dynamics.x;
}
fn curlTurbulence(x:vec3f,frequency:f32,phase:f32,rotation:vec2f)->vec3f{
 // Curl of A=(cos(y+1.3)sin(z), cos(z+2.1)sin(x), cos(x+.7)sin(y)).
 // Differentiating each component explicitly keeps this force solenoidal
 // before obstacle masks; the pressure projection handles the masked edge.
 // Rotate both the coordinates and vector potential for an orthogonal field.
 let drift=vec3f(.3,.7,-.2)*p.step.y+vec3f(phase,phase*1.73,-phase*.61);
 let local=vec3f(rotation.x*x.x+rotation.y*x.z,x.y,-rotation.y*x.x+rotation.x*x.z);
 let q=local*frequency+drift;
 let curlLocal=frequency*vec3f(cos(q.x+.7)*cos(q.y)+sin(q.z+2.1)*sin(q.x),
  cos(q.y+1.3)*cos(q.z)+sin(q.x+.7)*sin(q.y),
  cos(q.z+2.1)*cos(q.x)+sin(q.y+1.3)*sin(q.z));
 return vec3f(rotation.x*curlLocal.x-rotation.y*curlLocal.z,curlLocal.y,
  rotation.y*curlLocal.x+rotation.x*curlLocal.z);
}
fn turbulence(x:vec3f)->vec3f{
 // The rotated fine band avoids axis-aligned harmonics while adding smaller
 // shear. Its bounded weight keeps RMS forcing close to the original.
 return curlTurbulence(x,7.7,0.,vec2f(1.,0.))/7.7+
  .32*curlTurbulence(x,15.4,4.7,vec2f(.8,.6))/15.4;
}
`;
// Ordinary scenes cannot cast powers. Omit the registry rather than asking
// the driver to optimize its branches in every flow/chemistry kernel.
if(woodCadence){
 for(const token of ['@group(0) @binding(34) var<storage,read> woodFluxWords:array<u32>;','return mass/(1.*cellVolume*dt);','return woodFluxDensity(world);']){
  if(!common.includes(token))throw Error('Wood packet specialization contract changed: '+token);
 }
 common=common.replace('@group(0) @binding(34) var<storage,read> woodFluxWords:array<u32>;',
   '@group(0) @binding(34) var<storage,read> woodFluxWords:array<u32>;\n@group(0) @binding(44) var<uniform> woodPacket:vec4f;');
 common=common.replace('return mass/(1.*cellVolume*dt);','return woodPacket.x*mass/(1.*cellVolume*dt);')
   .replace('return woodFluxDensity(world);','return woodPacket.x*woodFluxDensity(world);');
}
if(!hasPowers){
 const begin=common.indexOf(powerSourceWGSL),end=common.indexOf('fn charge(x:',begin);
 if(begin<0||end<begin)throw Error('Power shader specialization contract changed');
 common=common.slice(0,begin)+`
 fn powerKind()->f32{return 0.;}
 fn isPower()->bool{return false;}
 struct PowerInjection{gas:vec4f};
 fn powerInjection(x:vec3f)->PowerInjection{return PowerInjection(vec4f(0));}
 fn powerSample(x:vec3f)->vec4f{return vec4f(0);}
 fn powerForce(x:vec3f)->vec3f{return vec3f(0);}
 fn powerBrickLive(at:vec3f,halfBrick:f32)->bool{return false;}
 `+common.slice(end);
}
// Predictor alpha caches a shared limiter donor: exact half-float codes 1..64,
// or 0 for the original tracing path. Corrected alpha remains source expansion.
// Near-integer coordinates fall back because separate kernels can round a
// trace to opposite sides of a donor boundary.
const advectVelocity=common+`
@group(0) @binding(2) var v:texture_3d<f32>;
@group(0) @binding(3) var dst:texture_storage_3d<rgba16float,write>;
@compute @workgroup_size(8,4,4) fn main(@builtin(global_invocation_id) i:vec3u){
 if(any(i>vec3u(N))){return;}var out=vec3f(0);
 var donor=vec3i(0);var commonDonor=true;
 for(var k=0u;k<3u;k++){
  let x=face(i,k);let back=trace(v,x,p.step.x);out[k]=component(v,back,k);
  var off=vec3f(.5);off[k]=0.;let q=(back-LO)/H-off;let cell=vec3i(floor(q));
  let fraction=q-vec3f(cell);let margin=min(fraction,vec3f(1.)-fraction);
  let tolerance=8.*1.1920929e-7*max(abs(q),vec3f(1.));
  commonDonor=commonDonor&&all(margin>tolerance);
  if(k==0u){donor=cell;}else{commonDonor=commonDonor&&all(donor==cell);}
 }
 let offset=donor-vec3i(i);var encoded=0u;
 if(commonDonor&&all(offset>=vec3i(-2))&&all(offset<=vec3i(1))){
  let q=vec3u(offset+vec3i(2));encoded=1u+q.x+4u*q.y+16u*q.z;
 }
 if(i.y==0u){out.y=0.;}textureStore(dst,vec3i(i),vec4f(out,f32(encoded)));
}`;
const curl=common+`
@group(0) @binding(2) var v:texture_3d<f32>;
@group(0) @binding(3) var dst:texture_storage_3d<rgba16float,write>;
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) i:vec3u){
 if(any(i>=vec3u(N))){return;}let x=LO+(vec3f(i)+.5)*H;
 let dx=vec3f(H,0,0);let dy=vec3f(0,H,0);let dz=vec3f(0,0,H);
 let w=vec3f(component(v,x+dy,2u)-component(v,x-dy,2u)-component(v,x+dz,1u)+component(v,x-dz,1u),
 component(v,x+dz,0u)-component(v,x-dz,0u)-component(v,x+dx,2u)+component(v,x-dx,2u),
 component(v,x+dx,1u)-component(v,x-dx,1u)-component(v,x+dy,0u)+component(v,x-dy,0u))/(2.*H);
 textureStore(dst,vec3i(i),vec4f(w,length(w)));
}`;
const correctVelocity=common+`${shockProjectWGSL()}
${reactionLedgerWGSL(D,{pressureCache})}
@group(0) @binding(2) var old:texture_3d<f32>;
@group(0) @binding(3) var pred:texture_3d<f32>;
@group(0) @binding(4) var chem:texture_3d<f32>;
@group(0) @binding(5) var vort:texture_3d<f32>;
@group(0) @binding(6) var dst:texture_storage_3d<rgba16float,write>;
// Vorticity samples here land exactly on N-grid cell centers. Use direct
// reads and the same zero-outside-domain boundary as scalar(vort,x).
fn vortexAt(i:vec3i)->vec4f{if(any(i<vec3i(0))||any(i>=vec3i(i32(N)))){return vec4f(0);}return textureLoad(vort,i,0);}
fn limitedCell(cell:vec3i,k:u32,value:f32)->f32{
 var lo=1e20;var hi=-1e20;
 for(var z=0;z<2;z++){for(var y=0;y<2;y++){for(var a=0;a<2;a++){let v=loadV(old,cell+vec3i(a,y,z))[k];lo=min(lo,v);hi=max(hi,v);}}}
 return clamp(value,lo,hi);
}
fn limited(x:vec3f,k:u32,value:f32)->f32{
 var off=vec3f(.5);off[k]=0.;return limitedCell(vec3i(floor((x-LO)/H-off)),k,value);
}
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) i:vec3u){
 if(any(i>vec3u(N))){return;}var out=vec3f(0);
 let predicted=loadV(pred,vec3i(i));let previous=loadV(old,vec3i(i));
 let encoded=predicted.w;let hasDonor=encoded>=1.&&encoded<=64.;
 let packed=u32(max(encoded-1.,0.));
 let donor=vec3i(i)+vec3i(i32(packed&3u)-2,i32((packed>>2u)&3u)-2,i32((packed>>4u)&3u)-2);
 for(var k=0u;k<3u;k++){
  let x=face(i,k);
  out[k]=predicted[k]+.5*(previous[k]-component(pred,trace(old,x,-p.step.x),k));
 }
 if(hasDonor){
  var lo=vec3f(1e20);var hi=vec3f(-1e20);
  for(var z=0;z<2;z++){for(var y=0;y<2;y++){for(var dx=0;dx<2;dx++){
   let value=loadV(old,donor+vec3i(dx,y,z)).xyz;lo=min(lo,value);hi=max(hi,value);
  }}}
  out=clamp(out,lo,hi);
 }else{
  for(var k=0u;k<3u;k++){out[k]=limited(trace(old,face(i,k),p.step.x),k,out[k]);}
 }
 let x=LO+(vec3f(i)+.5)*H;let c=scalar(chem,x);
 let cell=vec3i(i);let w=vortexAt(cell);
 let g=vec3f(vortexAt(cell+vec3i(1,0,0)).w-vortexAt(cell-vec3i(1,0,0)).w,vortexAt(cell+vec3i(0,1,0)).w-vortexAt(cell-vec3i(0,1,0)).w,vortexAt(cell+vec3i(0,0,1)).w-vortexAt(cell-vec3i(0,0,1)).w);
 let confinement=2.0*H*p.dynamics.z*cross(g/max(length(g),.00001),w.xyz);
 // Empty air still receives advection, confinement and pressure. Its
 // exact-zero scalar multiplier makes the analytic turbulence unnecessary.
 var forcing=confinement+vec3f(0,densityBuoyancy(c.y,3.0*p.dynamics.w)-smokeWeight(c.x,c.y),0);
 let support=min(c.x+c.y,1.);if(support>0.){forcing+=turbulence(x)*support*.9*p.chemistry.w;}
 out+=forcing*p.step.x;
 if(isPower()&&p.source.w>.5){out+=powerForce(x)*p.step.x;}
 // Brinkman-style damping inside stationary solids before projection.
 // Scalars are separately excluded; this is not a cut-cell pressure solve.
 if(objectDistance(x)<-.018){out*=exp(-p.step.x*240.);}
 var s=0.;
 if(isPower()){
  // Fuel and momentum are one sample of the same moving packet. Evaluating
  // charge and sourceVelocity separately repeats its folds and rain lanes.
  if(abs(object.tint.w)<=.5&&p.source.w>=.5){
   let injected=powerInjection(x);s=injected.gas.w;
   if(s>0.){let added=s*p.step.x*6.*p.chemistry.y;out=mix(out,injected.gas.xyz,sourceMomentumFraction(c.z,added));}
  }
 }else{s=charge(x);if(s>0.){let added=s*p.step.x*ordinaryFuelRate(p.effect.x,p.effect.w)*p.chemistry.y;out=mix(out,sourceVelocity(x),sourceMomentumFraction(c.z,added));}}
 if(i.y==0u){out.y=0.;}
 // Open sides and top; only incoming boundary velocities are suppressed.
 if(i.x==0u){out.x=min(out.x,0.);}if(i.x==N){out.x=max(out.x,0.);}
 if(i.z==0u){out.z=min(out.z,0.);}if(i.z==N){out.z=max(out.z,0.);}
 if(i.y==N){out.y=max(out.y,0.);}
 // Fine chemistry records the completed injection, combustion and cooling
 // of each parcel. No future reaction or second cooling estimate is applied.
 var expansion=completedVolumeSourceAt(x,N);
 if(p.lifecycle.w>0.){
  let shock=shockMac(i,N,H);out+=shock.xyz*p.lifecycle.w;
  expansion+=shock.w*p.lifecycle.w;
 }
 textureStore(dst,vec3i(i),vec4f(out,expansion));
}`;
const diffuseScalar=common+`
@group(0) @binding(3) var old:texture_3d<f32>;
@group(0) @binding(5) var dst:texture_storage_3d<rgba16float,write>;
@group(0) @binding(6) var<storage,read> bricks:array<vec4u>;
fn donor(i:vec3i)->vec4f{return textureLoad(old,clamp(i,vec3i(0),vec3i(i32(D)-1)),0);}
@compute @workgroup_size(4,4,4) fn main(@builtin(workgroup_id) group:vec3u,@builtin(local_invocation_id) local:vec3u){
 let brick=bricks[group.x].xyz;let i=brick*8u+vec3u(group.y,group.z%2u,group.z/2u)*4u+local;
 let cell=vec3i(i);let c=donor(cell);let h=6./f32(D);let a=p.step.x/(h*h);
 let diffusivity=vec4f(${PRODUCT_DIFFUSIVITY},${PRODUCT_DIFFUSIVITY},${GAS_DIFFUSIVITY},${GAS_DIFFUSIVITY});
 let laplacian=donor(cell+vec3i(1,0,0))+donor(cell-vec3i(1,0,0))
   +donor(cell+vec3i(0,1,0))+donor(cell-vec3i(0,1,0))
   +donor(cell+vec3i(0,0,1))+donor(cell-vec3i(0,0,1))-6.*c;
 textureStore(dst,cell,c+diffusivity*a*laplacian);
}`;
const advectScalar=common+`
@group(0) @binding(2) var v:texture_3d<f32>;
@group(0) @binding(3) var old:texture_3d<f32>;
@group(0) @binding(4) var dst:texture_storage_3d<rgba16float,write>;
@group(0) @binding(6) var<storage,read> bricks:array<vec4u>;
@compute @workgroup_size(4,4,4) fn main(@builtin(workgroup_id) group:vec3u,@builtin(local_invocation_id) local:vec3u){
 let i=bricks[group.x].xyz*8u+vec3u(group.y,group.z%2u,group.z/2u)*4u+local;
 if(any(i>=vec3u(D))){return;}let x=LO+(vec3f(i)+.5)*6./f32(D);
 textureStore(dst,vec3i(i),scalar(old,trace(v,x,p.step.x)));
}`;
const correctScalar=(subgroups?'enable subgroups;\n':'')+common+`
@group(0) @binding(2) var v:texture_3d<f32>;
@group(0) @binding(3) var old:texture_3d<f32>;
@group(0) @binding(4) var pred:texture_3d<f32>;
@group(0) @binding(5) var dst:texture_storage_3d<rgba16float,write>;
fn oldCell(i:vec3i)->vec4f{if(any(i<vec3i(0))||any(i>=vec3i(i32(D)))){return vec4f(0);}return textureLoad(old,i,0);}
@group(0) @binding(6) var<storage,read_write> brickWords:array<u32>;
${reactionLedgerWGSL(D,{write:true})}
@group(0) @binding(7) var<storage,read_write> occupied:array<atomic<u32>>;
@group(0) @binding(10) var<storage,read_write> opticalOccupied:array<atomic<u32>>;
${occupancyReductionWGSL(subgroups)}
${pressureCache?pressureSourceProducerWGSL():''}
@compute @workgroup_size(4,4,4) fn main(@builtin(workgroup_id) group:vec3u,@builtin(local_invocation_id) local:vec3u,@builtin(local_invocation_index) lane:u32${subgroups?',@builtin(subgroup_invocation_id) subgroupLane:u32':''}){
 let brick=brickCoordinate(group.x);let i=brick*8u+vec3u(group.y,group.z%2u,group.z/2u)*4u+local;
 let x=LO+(vec3f(i)+.5)*6./f32(D);let back=trace(v,x,p.step.x);
 let forward=textureLoad(pred,vec3i(i),0);var c=forward+.5*(textureLoad(old,vec3i(i),0)-scalar(pred,trace(v,x,-p.step.x)));
 let correction=c-forward;
 // Uniform ambient/halo parcels have an exact zero correction. Their
 // bounded result is already forward; eight donor reads cannot change it.
 if(any(correction!=vec4f(0))){
  let cell=vec3i(floor((back-LO)/6.*f32(D)-.5));var lo=vec4f(1e20);var hi=vec4f(-1e20);
  for(var z=0;z<2;z++){for(var y=0;y<2;y++){for(var a=0;a<2;a++){let q=oldCell(cell+vec3i(a,y,z));lo=min(lo,q);hi=max(hi,q);}}}
  // Donor bounds prevent new extrema without reducing correction merely
  // because another part of the scene requires additional CFL substeps.
  let capacity=max(select(forward-lo,hi-forward,correction>=vec4f(0)),vec4f(0));
  let resolved=1.; // Donor-limited correction is independent of CFL subdivision.
  c=forward+correction*min(vec4f(resolved),capacity/max(abs(correction),vec4f(.0000001)));
 }else{c=forward;}
 c=max(c,vec4f(0));
 let goal=textureSampleLevel(v,smp,((x-LO)/H+.5)/f32(N+1u),0).w;
 // Soot and fuel are transported mass concentrations. Expansion must dilute
 // both together; diluting only soot lets emissive fuel outrun visible smoke.
 let dilution=exp(-goal*p.step.x);
 c.x*=dilution;c.z*=dilution;
 // Consume mixed fuel and oxygen together. Fuel no longer disappears on a
 // timer, and soot/heat no longer depend on a grid-gradient threshold.
 c.w=min(c.w,1.);
 let fuelBeforeSources=c.z;var externalPilotHeat=0.;
 let s=charge(x);let solidDistance=objectDistance(x);if(abs(object.tint.w)>.5&&solidDistance>=-.02){
  // Conservative finite solid release, integrated once over this substep.
  // No art-direction fuel multiplier, synthetic soot or source velocity.
  let vapor=woodFluxFineDensity(x,brick);c.y=woodMixGas(c.y,c.z,vapor);
  if(p.step.w<.5){c.w=sourceOxygenDeficit(c.w,vapor.x);c.z+=vapor.x;
   // External ignition energy is finite in watts, divided by the actual
   // gas mixture heat capacity. Wood demo time does not multiply this heat.
   c.y+=woodGasPilotHeat(x,p.step.z,p.step.x,p.source.w)/(1.+c.z);
  }
 }else if(s>0.&&object.options.x>.5){
  // Add pyrolysis fuel and sensible heat; never overwrite existing gas state.
  // The surface supplies no soot: soot is produced by the reaction above.
  let heat=surfaceState(x).y;let added=min(s*p.step.x*p.chemistry.y*2.,.2);
  c.y=(c.y+added*heat)/(1.+added)+(heat-c.y)*(1.-exp(-p.step.x*s*10.));
  c.z+=select(added,0.,p.step.w>.5);c.w=1.-(1.-c.w)/(1.+added);
 }else if(s>0.&&isPower()){
  // Powers inject premixed hot gas, integrated once over this substep. Their
  // finite windows are in powerSource; transported gas remains after casting.
  // Soot is created by the same combustion reaction as every other source.
  let added=s*p.step.x*6.*p.chemistry.y;
  if(p.step.w>.5){c.x+=added*.8*p.chemistry.z;c.y+=added*.28;}
  else{
   // Pilot heat is bounded; fuel-rich source interiors do not gain oxygen
   // or accumulate unlimited preheat. Mixing with advected air determines
   // where the same fuel/oxygen reaction actually produces the flame.
   c.w=sourceOxygenDeficit(c.w,added);
   c.y=powerIgnitionHeat(c.y,c.z,added,p.chemistry.x,1.-c.w);c.z+=added;
  }
 }else if(s>0.){
 let n=noise((x-p.source.xyz)*12.+vec3f(p.shape.x,7.,4.));
 let pulse=.72+.28*n;let added=s*p.step.x*ordinaryFuelRate(p.effect.x,p.effect.w)*pulse*p.chemistry.y;
 if(p.step.w>.5){c.x+=added*.8*p.chemistry.z;c.y=sourceSensibleHeat(c.y,c.z,added,.06);}
 else{
  let premixed=p.effect.x>.5&&p.effect.x<1.5&&p.shape.z==0.;
  let incomingOxygen=select(0.,.8,premixed);
  c.w=sourceMixtureDeficit(c.w,added,incomingOxygen);
  if(p.effect.x<.5&&p.effect.w>.5){
   // Warm fuel vapor is separate from the localized pilot. Reheating every
   // arriving parcel to ignition temperature made the entire bed glow.
   c.y=sourceSensibleHeat(c.y,c.z,added,${((PLUME_THERMAL.fuelTemperatureK-GAS_THERMO.ambientK)/GAS_THERMO.temperatureScaleK).toFixed(8)});
   let pilotDose=boundedPilotDose(p.step.z,p.step.x,${PLUME_THERMAL.pilotHeatingRate}.,${PLUME_THERMAL.startupHeatingRate}.,${PLUME_THERMAL.startupDurationS})*max(p.chemistry.x,0.)/${PLUME_THERMAL.referencePilotHeat};
   if(pilotDose>0.){
    let pilotQ=((x-p.source.xyz)/p.effect.y-vec3f(${PLUME_THERMAL.pilotOffset.join(",")}))/vec3f(${PLUME_THERMAL.pilotWidth.join(",")});
    externalPilotHeat=pilotDose*exp(-dot(pilotQ,pilotQ))/(1.+c.z+added);
   }
  }else{
   c.y=sourceSensibleHeat(c.y,c.z,added,(.75+.6*n)*p.chemistry.x);
   c.y=sourceIgnition(c.y,added,p.chemistry.x*.47);
  }
  c.z+=added;
 }
 }
 // Finite floor fuel supplies warmed vapor. Soot and flame are created only
 // by the same gas combustion on the next step, never by a brush stamp.
 let bed=floorFeed(x);let floorAdded=bed.x*p.step.x;
 if(floorAdded>0.&&p.step.w<.5){let gasMass=1.+c.z;c.y=(c.y*gasMass+floorAdded*bed.y)/(gasMass+floorAdded);c.z+=floorAdded;
  c.w=sourceOxygenDeficit(c.w,floorAdded);
 }
 let fuelAfterSources=c.z;
 let temperatureBeforeReaction=c.y;
 c.y+=externalPilotHeat;
 let reaction=select(sceneReactionLedger(c,p.step.x,sceneHeatRelease(${GAS_CHEMISTRY.heatRelease}),mix(.12,1.8,p.shape.z)*p.chemistry.z),vec4f(0),p.step.w>.5);
 c.z=max(c.z-reaction.x,0.);c.w=min(c.w+reaction.y,1.);
 c.y=coolGasTemperature(c.y+reaction.z,c.z,c.x,p.step.x);
 // Accumulated 30 Hz decay survives half-float writes even when pressure
 // needs many tiny substeps. It changes density, never display opacity.
 c.x=(c.x+reaction.w)*exp(-p.lifecycle.x*smokeLossRate(c.y));
 let oxidized=min(c.x*(1.-exp(-1.2*max(1.-c.w,0.)*smoothstep(.7,1.8,c.y)*p.step.x)),max(1.-c.w,0.)/.08);
 c.x=max(c.x-oxidized,0.);c.w=min(c.w+oxidized*.08,1.);c.y+=oxidized*.3;
 if(p.step.w>.5){c.z=0.;c.w=0.;c.y*=exp(-p.step.x*.12);}
 let volumeSource=thermalVolumeChange(temperatureBeforeReaction,c.y,fuelBeforeSources,fuelAfterSources,p.step.x);
 if(solidDistance<-.02){c=vec4f(0);}
 // Quantize only numerical residue below the renderer's visible support.
 // Keeping half-float subnormals alive otherwise expands sparse work forever.
 c=select(c,vec4f(0),c<vec4f(${SMOKE_CLEAR_DENSITY},.00001,.000001,.0001));
 let fluidLive=solidDistance>=-.02&&(any(c.xyz>vec3f(0))||fuelAfterSources>fuelBeforeSources);
 storeCombustion(i,select(0.,reaction.x/max(p.step.x,.000001),fluidLive),select(0.,volumeSource,fluidLive));
 textureStore(dst,vec3i(i),max(c,vec4f(0)));
 var flags=select(0u,1u,any(c>vec4f(0)));
 // Bit 1 covers the existing camera/light support; its margins include
 // half-float writes. A convex filtered sample cannot exceed its texels'
 // soot/heat maxima, so a zero halo proves the fragment's early continue.
 // Bit 2 keeps every positive soot value for exact shadow extinction.
 if(c.x>=.000033||c.y>.3499){flags|=2u;}
 ${flowSupport ? `// Fine flow follows soot, heat and fuel. Cold oxygen deficit alone
 // does not require local refinement. This work is absent from the default.
 if(any(c.xyz>vec3f(0))){flags|=8u;}` : ''}
 if(c.x>0.){flags|=4u;}
 ${pressureCache?'recordPressureRate(select(0.,volumeSource,fluidLive),lane);':''}
 let combined=reduceOccupancy(flags,lane${subgroups?',subgroupLane':''});
 ${pressureCache?'finishPressureRates(i,local);':''}
 if(lane==0u){let B=D/8u;let index=brick.x+B*(brick.y+B*brick.z);
  if((combined&1u)!=0u){atomicStore(&occupied[index],1u);}
  if((combined>>1u)!=0u){atomicOr(&opticalOccupied[index],combined>>1u);}
 }
}`;
const rhs=common+`
@group(0) @binding(2) var v:texture_3d<f32>;
@group(0) @binding(3) var b:texture_storage_3d<r32float,write>;
@group(0) @binding(4) var zero:texture_storage_3d<r32float,write>;
@group(0) @binding(5) var previous:texture_3d<f32>;
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u){
 if(any(id>=vec3u(N))){return;}let i=vec3i(id);let q=loadV(v,i);
 let div=(loadV(v,i+vec3i(1,0,0)).x-q.x+loadV(v,i+vec3i(0,1,0)).y-q.y+loadV(v,i+vec3i(0,0,1)).z-q.z)/H;
 textureStore(b,i,vec4f((q.w-div)*H*H));textureStore(zero,i,vec4f(textureLoad(previous,i,0).x*p.shape.w));
}`;
const project=common+`
@group(0) @binding(2) var v:texture_3d<f32>;
@group(0) @binding(3) var pressure:texture_3d<f32>;
@group(0) @binding(4) var rhs:texture_3d<f32>;
@group(0) @binding(5) var dst:texture_storage_3d<rgba16float,write>;
@group(0) @binding(6) var<storage,read_write> stats:array<vec4f>;
var<workgroup> vmax:array<f32,64>;var<workgroup> pre:array<f32,64>;var<workgroup> post:array<f32,64>;var<workgroup> counts:array<f32,64>;
fn phi(i:vec3i)->f32{
 let signX=select(1.,-1.,i.x<0||i.x>=i32(N));let signY=select(1.,-1.,i.y>=i32(N));let signZ=select(1.,-1.,i.z<0||i.z>=i32(N));
 return signX*signY*signZ*textureLoad(pressure,clamp(i,vec3i(0),vec3i(i32(N)-1)),0).x;
}
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_index) lane:u32,@builtin(workgroup_id) group:vec3u){
 vmax[lane]=0.;pre[lane]=0.;post[lane]=0.;counts[lane]=0.;
 if(all(id<=vec3u(N))){let i=vec3i(id);let q=loadV(v,i);
 var out=q.xyz-vec3f(phi(i)-phi(i-vec3i(1,0,0)),phi(i)-phi(i-vec3i(0,1,0)),phi(i)-phi(i-vec3i(0,0,1)))/H;
 // Shock impulse and its divergence enter before this projection.
 // Packed MAC channels have different valid tangential extents. Extrapolate
 // their projected valid face instead of repeatedly projecting a ghost slot.
 if(id.y==N||id.z==N){
  let j=vec3i(i.x,min(i.y,i32(N)-1),min(i.z,i32(N)-1));
  out.x=loadV(v,j).x-(phi(j)-phi(j-vec3i(1,0,0)))/H;
 }
 if(id.x==N||id.z==N){
  let j=vec3i(min(i.x,i32(N)-1),i.y,min(i.z,i32(N)-1));
  out.y=loadV(v,j).y-(phi(j)-phi(j-vec3i(0,1,0)))/H;
 }
 if(id.x==N||id.y==N){
  let j=vec3i(min(i.x,i32(N)-1),min(i.y,i32(N)-1),i.z);
  out.z=loadV(v,j).z-(phi(j)-phi(j-vec3i(0,0,1)))/H;
 }
 if(id.y==0u){out.y=0.;}textureStore(dst,i,vec4f(out,q.w));
 vmax[lane]=length(out);
 if(all(id<vec3u(N))){
 let b=textureLoad(rhs,i,0).x;
 let A=6.*phi(i)-phi(i+vec3i(1,0,0))-phi(i-vec3i(1,0,0))-phi(i+vec3i(0,1,0))-phi(i-vec3i(0,1,0))-phi(i+vec3i(0,0,1))-phi(i-vec3i(0,0,1));
 pre[lane]=abs(b)/(H*H);post[lane]=abs(b-A)/(H*H);counts[lane]=1.;
 }}workgroupBarrier();
 for(var stride=32u;stride>0u;stride/=2u){if(lane<stride){vmax[lane]=max(vmax[lane],vmax[lane+stride]);pre[lane]+=pre[lane+stride];post[lane]+=post[lane+stride];counts[lane]+=counts[lane+stride];}workgroupBarrier();}
 if(lane==0u){let G=(N+4u)/4u;stats[group.x+G*(group.y+G*group.z)]=vec4f(vmax[0],pre[0],post[0],counts[0]);}
}`;
const buildBricks=common+`
@group(0) @binding(2) var<storage,read> oldMask:array<u32>;
@group(0) @binding(3) var<storage,read> previousMask:array<u32>;
@group(0) @binding(4) var<storage,read_write> bricks:array<vec4u>;
struct Dispatch{x:atomic<u32>,y:u32,z:u32};
@group(0) @binding(5) var<storage,read_write> dispatch:Dispatch;
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u){
 let B=i32(D/8u);if(any(id>=vec3u(u32(B)))){return;}var live=false;
 let radius=1;
 if(!live){for(var z=-radius;z<=radius;z++){for(var y=-radius;y<=radius;y++){for(var x=-radius;x<=radius;x++){
 let cell=vec3i(id)+vec3i(x,y,z);if(all(cell>=vec3i(0))&&all(cell<vec3i(B))){let index=u32(cell.x+B*(cell.y+B*cell.z));live=live||oldMask[index]>0u||previousMask[index]>0u;}
 if(live){break;}}if(live){break;}}if(live){break;}}}
 let at=LO+(vec3f(id)+.5)*6./f32(B);
 // Conservative brick/source intersection. Gaussian tails beyond r2=25
 // are <6e-17, far below a representable injected rgba16float value.
 // Existing state still uses the unchanged one-brick transport halo above.
 let halfBrick=3./f32(B);let nearQ=max(abs(at-p.source.xyz)-vec3f(halfBrick),vec3f(0))/p.effect.y;
 let farQ=(abs(at-p.source.xyz)+vec3f(halfBrick))/p.effect.y;
 var sourceLive=all(nearQ<vec3f(.85));
 if(p.effect.x<.5&&p.effect.w>.5){
  // Match charge's shallow ellipsoid, including representable tails. A
  // fixed cube cropped the broad bed until old smoke activated its halo.
  sourceLive=dot(nearQ/vec3f(.62,.20,.44),nearQ/vec3f(.62,.20,.44))<=25.;
 }
 if(isPower()){
  // The same source-center helpers supply field samples and conservative
  // brick intersections. Existing state retains its transport halo above.
  sourceLive=powerBrickLive(at,halfBrick);
 }else if(p.effect.x>.5){
  var r2=dot(nearQ/vec3f(.26,.12,.26),nearQ/vec3f(.26,.12,.26));
  if(p.effect.x>1.5&&p.effect.x<2.5){let radial=max(max(length(nearQ.xz)-.65,.65-length(farQ.xz)),0.);r2=pow(radial/.12,2.)+pow(nearQ.y/.10,2.);}
  if(p.effect.x>2.5&&p.effect.x<3.5){r2=pow(max(nearQ.x-1.,0.)/.15,2.)+pow(nearQ.y/.12,2.)+pow(nearQ.z/.15,2.);}
  if(p.effect.x>3.5&&p.effect.x<4.5){r2=pow(max(max(length(nearQ)-.52,.52-length(farQ)),0.)/.12,2.);}
  sourceLive=all(nearQ<=vec3f(1.6))&&r2<=25.;
  if(p.effect.x>4.5){
   var extent=vec3f(.90);
   if(p.effect.x>5.5&&p.effect.x<6.5){extent=vec3f(.90,1.12,.90);}
   if(p.effect.x>6.5&&p.effect.x<7.5){extent=vec3f(1.10,.62,.62);}
   if(p.effect.x>7.5&&p.effect.x<12.5){extent=vec3f(1.20,1.20,.30);}
   if(p.effect.x>9.5&&p.effect.x<10.5){extent=vec3f(1.20,.65,.65);}
   if(p.effect.x>12.5&&p.effect.x<13.5){extent=vec3f(1.18,.65,.65);}
   if(p.effect.x>13.5){extent=vec3f(1.35,.45,1.35);}
   if(p.effect.x>14.5&&p.effect.x<18.5){extent=vec3f(1.6);}
   if(p.effect.x>18.5){extent=vec3f(.45);}
   sourceLive=all(nearQ<=extent);
  }
 }
 if(object.options.x>.5){
  let center=clamp(at,object.origin.xyz-vec3f(1.49*object.origin.w),object.origin.xyz+vec3f(1.49*object.origin.w));
  let d=objectDistance(center)+length(at-center);
  // Conservative shell/brick intersection, including interpolation padding.
  let radius=halfBrick*1.733+.05*object.origin.w;
  sourceLive=d<.13*object.origin.w+radius&&d>-.02*object.origin.w-radius;
 }
 let injecting=select(p.source.w>.5&&(p.effect.w>.5||p.step.z<p.effect.z),p.source.w>.5,isPower());
 live=live||(injecting&&sourceLive)||floorWork(at,halfBrick);
 if(abs(object.tint.w)>.5){live=live||woodFluxLive(at,halfBrick)||woodGasPilotLive(at,halfBrick,p.step.z,p.step.x,p.source.w);}
 if(live){let index=atomicAdd(&dispatch.x,1u);bricks[index]=vec4u(id,0u);}
}`;
const reduceStats=`
@group(0) @binding(0) var<storage,read> groups:array<vec4f>;
@group(0) @binding(1) var<storage,read_write> out:array<vec4f>;
var<workgroup> values:array<vec4f,256>;
@compute @workgroup_size(256) fn main(@builtin(local_invocation_index) lane:u32){
 var value=vec4f(0);for(var i=lane;i<${Math.ceil((N+1)/4)**3}u;i+=256u){let q=groups[i];value=vec4f(max(value.x,q.x),value.yzw+q.yzw);}values[lane]=value;workgroupBarrier();
 for(var stride=128u;stride>0u;stride/=2u){if(lane<stride){let a=values[lane];let b=values[lane+stride];values[lane]=vec4f(max(a.x,b.x),a.yzw+b.yzw);}workgroupBarrier();}
 if(lane==0u){let previous=out[0];out[0]=vec4f(max(previous.x,values[0].x),previous.yzw+values[0].yzw);}
}`;
const filteredVelocity=directVorticity?correctVelocity:correctVelocity.replace('let cell=vec3i(i);let w=vortexAt(cell);\n let g=vec3f(vortexAt(cell+vec3i(1,0,0)).w-vortexAt(cell-vec3i(1,0,0)).w,vortexAt(cell+vec3i(0,1,0)).w-vortexAt(cell-vec3i(0,1,0)).w,vortexAt(cell+vec3i(0,0,1)).w-vortexAt(cell-vec3i(0,0,1)).w);','let w=scalar(vort,x);let dx=vec3f(H,0,0);let dy=vec3f(0,H,0);let dz=vec3f(0,0,H);\n let g=vec3f(scalar(vort,x+dx).w-scalar(vort,x-dx).w,scalar(vort,x+dy).w-scalar(vort,x-dy).w,scalar(vort,x+dz).w-scalar(vort,x-dz).w);');
const shaders={diffuseScalar,advectVelocity,curl,correctVelocity:filteredVelocity,advectScalar,correctScalar,rhs,project,buildBricks,reduceStats};
for(const name of Object.keys(shaders)){
 if(hasPowers&&powerKind!==null)shaders[name]=shaders[name].replace(powerSourceWGSL,powerSourceFor(powerKind));
 if(hasPowers)shaders[name]=shaders[name].replace('fn powerResolvedContact(index:f32)->vec4f{return vec4f(-1,0,1,0);}','fn powerResolvedContact(index:f32)->vec4f{return p.contacts[powerActorIndex].hits[u32(index)].hit;}');
 if(prune)shaders[name]=pruneShaderFunctions(shaders[name]);
}return shaders;
}

export function pressureShaders(n,{cache=true}={}){
const common=`const N:i32=${n};
@group(0) @binding(0) var p:texture_3d<f32>;
@group(0) @binding(1) var b:texture_3d<f32>;
@group(0) @binding(2) var dst:texture_storage_3d<r32float,write>;
fn at(i:vec3i)->f32{let sx=select(1.,-1.,i.x<0||i.x>=N);let sy=select(1.,-1.,i.y>=N);let sz=select(1.,-1.,i.z<0||i.z>=N);return sx*sy*sz*textureLoad(p,clamp(i,vec3i(0),vec3i(N-1)),0).x;}
fn sum(i:vec3i)->f32{return at(i+vec3i(1,0,0))+at(i-vec3i(1,0,0))+at(i+vec3i(0,1,0))+at(i-vec3i(0,1,0))+at(i+vec3i(0,0,1))+at(i-vec3i(0,0,1));}
`;
return {
 // The 4^3 coarse grid fits in one workgroup. Keep all 24 Jacobi
 // iterations in shared memory, with the same f32 arithmetic and boundaries.
 ...(n===4?{coarse:common+`
var<workgroup> values:array<f32,64>;
var<workgroup> next:array<f32,64>;
fn localAt(i:vec3i)->f32{
 let sx=select(1.,-1.,i.x<0||i.x>=4);let sy=select(1.,-1.,i.y>=4);let sz=select(1.,-1.,i.z<0||i.z>=4);
 let q=clamp(i,vec3i(0),vec3i(3));return sx*sy*sz*values[u32(q.x+4*(q.y+4*q.z))];
}
@compute @workgroup_size(4,4,4) fn main(@builtin(local_invocation_id) id:vec3u,@builtin(local_invocation_index) lane:u32){
 let i=vec3i(id);let rhs=textureLoad(b,i,0).x;values[lane]=textureLoad(p,i,0).x;workgroupBarrier();
 for(var j=0u;j<24u;j++){
  let neighbors=localAt(i+vec3i(1,0,0))+localAt(i-vec3i(1,0,0))+localAt(i+vec3i(0,1,0))+localAt(i-vec3i(0,1,0))+localAt(i+vec3i(0,0,1))+localAt(i-vec3i(0,0,1));
  next[lane]=mix(values[lane],(neighbors+rhs)/6.,.6666667);workgroupBarrier();
  values[lane]=next[lane];workgroupBarrier();
 }
 textureStore(dst,i,vec4f(values[lane]));
}`}:{}),
 smooth:common+(cache&&n>=8&&n%8===0?`
var<workgroup> pressureTile:array<f32,600>;
fn tileAt(i:vec3i)->f32{return pressureTile[u32(i.x+10*(i.y+10*i.z))];}
@compute @workgroup_size(8,8,4) fn main(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_id) local:vec3u,@builtin(local_invocation_index) lane:u32,@builtin(workgroup_id) group:vec3u){
 let origin=vec3i(group)*vec3i(8,8,4)-vec3i(1);
 for(var q=lane;q<600u;q+=256u){let offset=vec3i(i32(q%10u),i32((q/10u)%10u),i32(q/100u));pressureTile[q]=at(origin+offset);}
 workgroupBarrier();
 let i=vec3i(id);let t=vec3i(local)+vec3i(1);
 let neighbors=tileAt(t+vec3i(1,0,0))+tileAt(t-vec3i(1,0,0))+tileAt(t+vec3i(0,1,0))+tileAt(t-vec3i(0,1,0))+tileAt(t+vec3i(0,0,1))+tileAt(t-vec3i(0,0,1));
 textureStore(dst,i,vec4f(mix(tileAt(t),(neighbors+textureLoad(b,i,0).x)/6.,.6666667)));
}`:`@compute @workgroup_size(8,8,4) fn main(@builtin(global_invocation_id) id:vec3u){if(any(id>=vec3u(u32(N)))){return;}let i=vec3i(id);textureStore(dst,i,vec4f(mix(at(i),(sum(i)+textureLoad(b,i,0).x)/6.,.6666667)));}`),
 restrict:common+`@group(0) @binding(3) var zero:texture_storage_3d<r32float,write>;
 @compute @workgroup_size(8,8,4) fn main(@builtin(global_invocation_id) id:vec3u){if(any(id>=vec3u(u32(N/2)))){return;}var r=0.;for(var z=0;z<2;z++){for(var y=0;y<2;y++){for(var x=0;x<2;x++){let i=vec3i(id)*2+vec3i(x,y,z);r+=textureLoad(b,i,0).x-6.*at(i)+sum(i);}}}textureStore(dst,vec3i(id),vec4f(r*.5));textureStore(zero,vec3i(id),vec4f(0));}`,
 prolong:common+`fn coarse(i:vec3i)->f32{let sx=select(1.,-1.,i.x<0||i.x>=N/2);let sy=select(1.,-1.,i.y>=N/2);let sz=select(1.,-1.,i.z<0||i.z>=N/2);return sx*sy*sz*textureLoad(b,clamp(i,vec3i(0),vec3i(N/2-1)),0).x;}
 @compute @workgroup_size(8,8,4) fn main(@builtin(global_invocation_id) id:vec3u){if(any(id>=vec3u(u32(N)))){return;}let q=(vec3f(id)+.5)*.5-.5;let lo=vec3i(floor(q));let f=fract(q);var c=0.;for(var z=0;z<2;z++){for(var y=0;y<2;y++){for(var x=0;x<2;x++){let o=vec3i(x,y,z);let w=select(vec3f(1)-f,f,vec3<bool>(x==1,y==1,z==1));c+=coarse(lo+o)*w.x*w.y*w.z;}}}textureStore(dst,vec3i(id),vec4f(at(vec3i(id))+c));}`
};
}
