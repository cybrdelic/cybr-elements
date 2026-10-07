// Chemistry already visits every live fine voxel and its retiring halo.
// Produce the exact eight-cell restriction there, using the existing occupancy
// barrier, rather than unpacking fine records in every global flow invocation.
export function pressureSourceProducerWGSL(){return `
@group(0) @binding(64) var pressureSourceOut:texture_storage_3d<r32float,write>;
var<workgroup> completedRates:array<f32,64>;
fn recordPressureRate(rate:f32,lane:u32){completedRates[lane]=unpack2x16float(pack2x16float(vec2f(0,rate))).y;}
fn finishPressureRates(i:vec3u,local:vec3u){
 if(any((local&vec3u(1))!=vec3u(0))){return;}
 var total=0.;
 for(var z=0u;z<2u;z++){for(var y=0u;y<2u;y++){for(var x=0u;x<2u;x++){
  let at=local+vec3u(x,y,z);total+=completedRates[at.x+4u*(at.y+4u*at.z)];
 }}}
 textureStore(pressureSourceOut,vec3i(i/2u),vec4f(total*.125));
}
`;}
export function pressureSourceReaderWGSL(D=256){return `
@group(0) @binding(64) var pressureSourceCache:texture_3d<f32>;
const PRESSURE_SOURCE_N:u32=${D/2}u;
fn pressureSourceCell(i:vec3i)->f32{
 if(any(i<vec3i(0))||any(i>=vec3i(i32(PRESSURE_SOURCE_N)))){return 0.;}
 return textureLoad(pressureSourceCache,i,0).x;
}
fn completedVolumeSourceAt(world:vec3f,gridN:u32)->f32{
 let span=max(1u,PRESSURE_SOURCE_N/gridN);
 let cell=vec3i(floor((world-vec3f(-3,0,-3))/6.*f32(gridN)));let base=cell*i32(span);var total=0.;
 for(var z=0u;z<span;z++){for(var y=0u;y<span;y++){for(var x=0u;x<span;x++){total+=pressureSourceCell(base+vec3i(vec3u(x,y,z)));}}}
 return total/f32(span*span*span);
}
`;}
