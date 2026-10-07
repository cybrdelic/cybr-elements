import {simulationShaders} from './shaders.js?v=studio-rc-37-repair';

// Conservative finite-volume MUSCL transport. The host bounds each coarse step
// to |velocity * dt / voxelSize| <= 3. Heat and oxygen deficit are intensive;
// soot and fuel are concentrations and retain the conservative flux update.
export function conservativeFluxShader(N=128,D=256,block=[4,4,4]){
 if(![[4,4,4],[8,4,4],[8,8,4]].some(b=>b.every((v,i)=>v===block[i])))throw Error('Unsupported flux workgroup');
 const tileCount=Math.max(...block.map((v,i)=>(v+10)*block[(i+1)%3]*block[(i+2)%3]));
 const lanes=block.reduce((a,b)=>a*b,1);
 if(D%8!==0)throw Error('Flux transport requires complete 8-voxel bricks');
 let template=simulationShaders(N,D).advectScalar.replace('if(any(i>=vec3u(D))){return;}','');
 if(block.some(v=>v!==4))template=template.replace('@workgroup_size(4,4,4)',`@workgroup_size(${block.join(',')})`).replace('vec3u(group.y,group.z%2u,group.z/2u)*4u',`vec3u(group.y*${block[0]}u,(group.z%${8/block[1]}u)*${block[1]}u,(group.z/${8/block[1]}u)*${block[2]}u)`);
 const helpers=`
struct FluxStep{axis:u32,dt:f32,time:f32,seed:u32};
@group(0) @binding(46) var<uniform> fluxStep:FluxStep;
@group(0) @binding(47) var<storage,read_write> fluxDiagnostics:array<atomic<u32>>;
var<workgroup> fluxTile:array<vec4f,${tileCount}>;
var<private> fluxOrigin:vec3i;
fn fluxRawCell(i:vec3i)->vec4f{if(any(i<vec3i(0))||any(i>=vec3i(i32(D)))){return vec4f(0);}return textureLoad(old,i,0);}
fn fluxCell(i:vec3i)->vec4f{
 let d=i-fluxOrigin;let k=fluxStep.axis;let size=vec3i(${block.join(",")});let width=size[k]+10;let height=size[(k+1u)%3u];let depth=size[(k+2u)%3u];let along=d[k]+5;let a=d[(k+1u)%3u];let b=d[(k+2u)%3u];
 // The bounded swept stencil stays inside the five-cell halo; transverse
 // coordinates never leave this workgroup. Domain boundaries were filled
 // by fluxRawCell. Avoid a redundant slow-path texture branch per neighbor.
 return fluxTile[u32(along+width*(a+height*b))];
}
fn fluxSlope(a:vec4f,b:vec4f)->vec4f{return .5*(sign(a)+sign(b))*min(abs(.5*(a+b)),2.*min(abs(a),abs(b)));}
fn faceFlux(faceCell:vec3i,u:f32,axis:vec3i)->vec4f{
 let direction=select(-1,1,u>=0.);let donor=faceCell-select(vec3i(0),axis,u>=0.);
 let nu=u*fluxStep.dt*f32(D)/6.;let travel=min(abs(nu),3.);let whole=u32(floor(travel));let fraction=fract(travel);
 var total=vec4f(0);
 for(var k=0u;k<4u;k++){if(k>=whole){break;}total+=fluxCell(donor-axis*direction*i32(k));}
 let partial=donor-axis*direction*i32(whole);let c=fluxCell(partial);
 let slope=fluxSlope(c-fluxCell(partial-axis),fluxCell(partial+axis)-c);
 return f32(direction)*(total+fraction*(c+.5*f32(direction)*(1.-fraction)*slope));
}
fn fluxHash(v:u32)->u32{var h=v;h^=h>>16u;h*=0x7feb352du;h^=h>>15u;h*=0x846ca68bu;return h^(h>>16u);}
fn fluxHalf(value:f32,seed:u32)->f32{
 if(value<=0.||value>=65504.){return value;}
 let bits=pack2x16float(vec2f(value,0))&65535u;let nearest=unpack2x16float(bits).x;
 let lo=unpack2x16float(bits-select(0u,1u,nearest>value&&bits>0u)).x;
 let hi=unpack2x16float(bits+select(0u,1u,nearest<value&&bits<31743u)).x;
 return select(lo,hi,f32(fluxHash(seed)>>8u)*(1./16777216.)<(value-lo)/max(hi-lo,.000000000001));
}
fn fluxRound(c:vec4f,i:vec3u)->vec4f{
 let seed=(i.x*73856093u)^(i.y*19349663u)^(i.z*83492791u)^bitcast<u32>(fluxStep.time)^fluxStep.seed;
 return vec4f(fluxHalf(c.x,seed),c.y,fluxHalf(c.z,seed^0x85ebca6bu),c.w);
}
`;
 const sample='textureStore(dst,vec3i(i),scalar(old,trace(v,x,p.step.x)));';
 if(!template.includes(sample))throw Error('Production scalar layout changed; review flux integration.');
 return template.replace('@group(0) @binding(6) var<storage,read> bricks:',helpers+'\n@group(0) @binding(6) var<storage,read> bricks:').replace(sample,`
 let lane=local.x+${block[0]}u*(local.y+${block[1]}u*local.z);
 fluxOrigin=vec3i(i)-vec3i(local);
 let size=vec3u(${block.join(",")});let width=size[fluxStep.axis]+10u;let height=size[(fluxStep.axis+1u)%3u];let depth=size[(fluxStep.axis+2u)%3u];
 for(var q=lane;q<width*height*depth;q+=${lanes}u){var at=fluxOrigin;at[fluxStep.axis]+=i32(q%width)-5;
  at[(fluxStep.axis+1u)%3u]+=i32((q/width)%height);at[(fluxStep.axis+2u)%3u]+=i32(q/(width*height));fluxTile[q]=fluxRawCell(at);
 }workgroupBarrier();
 var a=vec3i(0);a[fluxStep.axis]=1;let offset=vec3f(a)*(3./f32(D));
 let left=component(v,x-offset,fluxStep.axis);let right=component(v,x+offset,fluxStep.axis);
 let center=fluxCell(vec3i(i));var c=center+faceFlux(vec3i(i),left,a)-faceFlux(vec3i(i)+a,right,a);
 let divergence=(right-left)*fluxStep.dt*f32(D)/6.;
 c.y+=center.y*divergence;c.w+=center.w*divergence;
 let cfl=max(abs(left),abs(right))*fluxStep.dt*f32(D)/6.;
 if(cfl>3.0001){atomicAdd(&fluxDiagnostics[0],1u);}
 if(any(c.xz<vec2f(-.00001))){atomicAdd(&fluxDiagnostics[1],1u);}
 textureStore(dst,vec3i(i),fluxRound(max(c,vec4f(0)),i));`);
}
