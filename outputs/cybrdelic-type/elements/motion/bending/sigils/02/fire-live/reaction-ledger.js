// One packed word per fine cell: consumed fuel/s and completed gas-volume
// source/s. Chemistry owns these records; rendering and pressure only read.
import {pressureSourceReaderWGSL} from './pressure-source-cache.js?v=studio-rc-37-audit';
export function reactionLedgerWGSL(D=256,{write=false,binding=61,pressureCache=false}={}){
 const headerWords=(D/8)**3*4;
 if(write)return `
const REACTION_D:u32=${D}u;const REACTION_OFFSET:u32=${headerWords}u;
fn brickCoordinate(index:u32)->vec3u{return vec3u(brickWords[index*4u],brickWords[index*4u+1u],brickWords[index*4u+2u]);}
fn storeCombustion(i:vec3u,consumed:f32,volumeSource:f32){
 let index=i.x+REACTION_D*(i.y+REACTION_D*i.z);
 brickWords[REACTION_OFFSET+index]=pack2x16float(vec2f(consumed,volumeSource));
}`;
 return `@group(0) @binding(${binding}) var<storage,read> reactionLedger:array<u32>;
const REACTION_D:u32=${D}u;const REACTION_OFFSET:u32=${headerWords}u;
fn reactionCell(i:vec3i)->vec2f{
 if(any(i<vec3i(0))||any(i>=vec3i(i32(REACTION_D)))){return vec2f(0);}
 let index=u32(i.x)+REACTION_D*(u32(i.y)+REACTION_D*u32(i.z));
 return unpack2x16float(reactionLedger[REACTION_OFFSET+index]);
}
fn combustionAt(world:vec3f)->vec2f{
 let q=(world-vec3f(-3,0,-3))/6.*f32(REACTION_D)-.5;
 let i=vec3i(floor(q));let f=fract(q);
 return mix(mix(mix(reactionCell(i),reactionCell(i+vec3i(1,0,0)),f.x),mix(reactionCell(i+vec3i(0,1,0)),reactionCell(i+vec3i(1,1,0)),f.x),f.y),
   mix(mix(reactionCell(i+vec3i(0,0,1)),reactionCell(i+vec3i(1,0,1)),f.x),mix(reactionCell(i+vec3i(0,1,1)),reactionCell(i+vec3i(1,1,1)),f.x),f.y),f.z);
}
fn consumedReactionAt(world:vec3f)->f32{return combustionAt(world).x;}
${pressureCache?pressureSourceReaderWGSL(D):`fn completedVolumeSourceAt(world:vec3f,gridN:u32)->f32{
 let span=max(1u,REACTION_D/gridN);let cell=vec3i(floor((world-vec3f(-3,0,-3))/6.*f32(gridN)));let base=cell*i32(span);var total=0.;
 for(var z=0u;z<span;z++){for(var y=0u;y<span;y++){for(var x=0u;x<span;x++){total+=reactionCell(base+vec3i(vec3u(x,y,z))).y;}}}
 return total/f32(span*span*span);
}`}`;
}
