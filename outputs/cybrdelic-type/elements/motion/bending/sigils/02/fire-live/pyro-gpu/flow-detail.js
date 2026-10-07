// Material coordinates travel with the resolved MAC flow. A two-second
// exponential relaxation bounds distortion without periodic reset seams.
// This is advected curl detail, not a wavelet turbulence implementation.
import {reactionRoundingWGSL} from './reaction-precision.js?v=studio-rc-37-audit';
export function flowDetailShader(N=128,M=64){
 if(!Number.isInteger(N)||N<4||!Number.isInteger(M)||M<4)throw Error('Invalid flow detail grid');
 return `
struct Params{step:vec4f};
@group(0) @binding(0) var<uniform> p:Params;
@group(0) @binding(1) var smp:sampler;
@group(0) @binding(2) var velocity:texture_3d<f32>;
@group(0) @binding(3) var old:texture_3d<f32>;
@group(0) @binding(4) var dst:texture_storage_3d<rgba16float,write>;
@group(0) @binding(5) var curl:texture_3d<f32>;
const LO=vec3f(-3,0,-3);const H=6./${N}.;
fn mac(x:vec3f)->vec3f{
 let q=(x-LO)/H;let z=${N+1}.;
 return vec3f(textureSampleLevel(velocity,smp,(q+vec3f(.5,0,0))/z,0).x,
 textureSampleLevel(velocity,smp,(q+vec3f(0,.5,0))/z,0).y,
 textureSampleLevel(velocity,smp,(q+vec3f(0,0,.5))/z,0).z);
}
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) i:vec3u){
 if(any(i>=vec3u(${M}u))){return;}
 let x=LO+(vec3f(i)+.5)*6./${M}.;let delta=p.step.x*mac(x-.5*p.step.x*mac(x));let back=x-delta;
 var prior=vec4f(0);if(all(back>=LO)&&all(back<=LO+6.)){prior=textureSampleLevel(old,smp,(back-LO)/6.,0);}
 let decay=exp(-p.step.x*.5);let phi=select(1.,(1.-decay)/max(p.step.x*.5,.0000001),p.step.x>.000001);
 let omega=textureSampleLevel(curl,smp,(x-LO)/6.,0).xyz;
 let energyGoal=min(.5*H*H*dot(omega,omega),16.);let energyDecay=exp(-p.step.x*5.);
 let result=vec4f(prior.xyz*decay-delta*phi,mix(energyGoal,max(prior.w,0.),energyDecay));
 let rounded=reactionRound(abs(result),i,p.step.y);
 textureStore(dst,vec3i(i),sign(result)*rounded);
}`+reactionRoundingWGSL;
}
export function flowDetailVelocity(source){
 const marker='fn turbulence(x:vec3f)->vec3f{';
 const force='turbulence(x)*support*.9*p.chemistry.w';
 if(!source.includes(marker)||!source.includes(force))throw Error('Flow detail shader sites changed');
 return '@group(0) @binding(50) var materialFlow:texture_3d<f32>;\n'+source
  .replace(marker,marker+'\n let material=textureSampleLevel(materialFlow,smp,(x-LO)/EXT,0);let flowX=x+material.xyz;')
  .replaceAll('curlTurbulence(x,','curlTurbulence(flowX,')
  .replace(force,'turbulence(x)*support*min(2.5*sqrt(max(2.*textureSampleLevel(materialFlow,smp,(x-LO)/EXT,0).w,0.)),.9)*p.chemistry.w');
}
