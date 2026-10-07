// Unbiased half-float writes retain chemical changes smaller than one storage
// ULP. Zero and exactly representable values remain stationary. This changes
// storage rounding, not the reaction model or its stoichiometric constants.
export const reactionRoundingWGSL=`
fn reactionHash(v:u32)->u32{var h=v;h^=h>>16u;h*=0x7feb352du;h^=h>>15u;h*=0x846ca68bu;return h^(h>>16u);}
fn reactionHalf(value:f32,seed:u32)->f32{
 if(value<=0.||value>=65504.){return value;}
 let bits=pack2x16float(vec2f(value,0))&65535u;let nearest=unpack2x16float(bits).x;
 let lo=unpack2x16float(bits-select(0u,1u,nearest>value&&bits>0u)).x;
 let hi=unpack2x16float(bits+select(0u,1u,nearest<value&&bits<31743u)).x;
 return select(lo,hi,f32(reactionHash(seed)>>8u)*(1./16777216.)<(value-lo)/max(hi-lo,.000000000001));
}
fn reactionRoundSeed(c:vec4f,i:vec3u,time:f32,phase:u32)->vec4f{
 let seed=(i.x*73856093u)^(i.y*19349663u)^(i.z*83492791u)^bitcast<u32>(time)^phase;
 return vec4f(reactionHalf(c.x,seed),reactionHalf(c.y,seed^0x85ebca6bu),reactionHalf(c.z,seed^0xc2b2ae35u),reactionHalf(c.w,seed^0x27d4eb2fu));
}
fn reactionRound(c:vec4f,i:vec3u,time:f32)->vec4f{return reactionRoundSeed(c,i,time,0u);}
`;
export function transportPrecisionShader(source){
 const marker='textureStore(dst,vec3i(i),scalar(old,trace(v,x,p.step.x)));';
 if(!source.includes(marker))throw Error('Transport precision write site changed');
 return source.replace(marker,'textureStore(dst,vec3i(i),reactionRoundSeed(scalar(old,trace(v,x,p.step.x)),i,p.step.y,0x9e3779b9u));')+reactionRoundingWGSL;
}
export function reactionPrecisionShader(source){
 const marker='textureStore(dst,vec3i(i),max(c,vec4f(0)));';
 if(!source.includes(marker))throw Error('Reaction precision write site changed');
 return source.replace(marker,'textureStore(dst,vec3i(i),reactionRound(max(c,vec4f(0)),i,p.step.y));')+reactionRoundingWGSL;
}
