import {conservativeFluxShader} from './conservative-transport.js?v=studio-rc-37-repair';

// Fuse the final z sweep with chemistry. Preserve the half-float intermediate
// exactly; this removes a volume write/read without changing the equations.
export function fusedFluxReactionShader(source,N=128,D=256){
 const flux=conservativeFluxShader(N,D),first=flux.indexOf('struct FluxStep'),last=flux.indexOf('@group(0) @binding(6) var<storage,read> bricks:');
 const begin=flux.indexOf(' fluxOrigin=vec3i(i)-vec3i(local);'),end=flux.indexOf(' textureStore(dst,vec3i(i),fluxRound',begin);
 const marker=' var c=max(textureLoad(old,vec3i(i),0),vec4f(0));';
 if(first<0||last<first||begin<0||end<begin||!source.includes(marker))throw Error('Final flux fusion sites changed');
 const helpers=flux.slice(first,last).replaceAll('fluxStep.axis','2u').replaceAll('fluxStep.seed','1013904242u');
 const computation=flux.slice(begin,end).replaceAll('fluxStep.axis','2u');
 const rounded=`
 let intermediate=fluxRound(max(c,vec4f(0)),i);
 c=vec4f(unpack2x16float(pack2x16float(intermediate.xy)),unpack2x16float(pack2x16float(intermediate.zw)));
`;
 return source.replace('if(any(i>=vec3u(D))){return;}','')
  .replace(marker,computation+rounded)+helpers;
}
