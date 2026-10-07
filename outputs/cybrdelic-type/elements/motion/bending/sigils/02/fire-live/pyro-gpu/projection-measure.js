import {pressureStencilWGSL} from './pressure-geometry.js?v=studio-rc-37-repair';
export function projectionMeasureShader(n,{weighted=false}={}){return `
const N:u32=${n}u;const H:f32=6./${n}.;
@group(0) @binding(2) var velocity:texture_3d<f32>;
@group(0) @binding(4) var rhs:texture_3d<f32>;
@group(0) @binding(6) var<storage,read_write> stats:array<vec4f>;
${weighted?pressureStencilWGSL(n):''}
var<workgroup> speeds:array<f32,64>;var<workgroup> before:array<f32,64>;var<workgroup> after:array<f32,64>;var<workgroup> counts:array<f32,64>;
fn load(i:vec3i)->vec4f{return textureLoad(velocity,clamp(i,vec3i(0),vec3i(i32(N))),0);}
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u,@builtin(local_invocation_index) lane:u32,@builtin(workgroup_id) group:vec3u){
 speeds[lane]=0.;before[lane]=0.;after[lane]=0.;counts[lane]=0.;
 if(all(id<=vec3u(N))){let i=vec3i(id);let q=load(i);speeds[lane]=length(q.xyz);
  if(all(id<vec3u(N))){
   ${weighted?'let st=pressureStencil(i);let minus=st.minus;let plus=st.plus;':'let minus=vec3f(1);let plus=vec3f(1);'}
   let divergence=(plus.x*load(i+vec3i(1,0,0)).x-minus.x*q.x+plus.y*load(i+vec3i(0,1,0)).y-minus.y*q.y+plus.z*load(i+vec3i(0,0,1)).z-minus.z*q.z)/H;
   before[lane]=abs(textureLoad(rhs,i,0).x)/(H*H);after[lane]=abs(divergence-q.w);counts[lane]=1.;
  }
 }
 workgroupBarrier();
 for(var stride=32u;stride>0u;stride/=2u){if(lane<stride){speeds[lane]=max(speeds[lane],speeds[lane+stride]);before[lane]+=before[lane+stride];after[lane]+=after[lane+stride];counts[lane]+=counts[lane+stride];}workgroupBarrier();}
 if(lane==0u){let G=(N+4u)/4u;stats[group.x+G*(group.y+G*group.z)]=vec4f(speeds[0],before[0],after[0],counts[0]);}
}`;}
