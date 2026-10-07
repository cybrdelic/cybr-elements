// Non-overlapping GPU intervals. A paused frame writes only light/render.
export function gpuCosts(t,substeps){
 if(!Number.isInteger(substeps)||substeps<0||substeps>12)throw Error('Invalid timing substeps');
 const ms=(a,b)=>{if(t[b]<t[a])throw Error('Invalid GPU timestamp interval');return Number(t[b]-t[a])/1e6;};
 const gpu={source:0,velocity:0,pressure:0,transport:0,auxiliary:0,
  simulation:substeps?ms(96,97):0,lighting:ms(98,99),render:ms(100,101)};
 for(let i=0;i<substeps;i++){const n=i*8;gpu.source+=ms(n,n+1);gpu.velocity+=ms(n+2,n+3);gpu.pressure+=ms(n+4,n+5);gpu.transport+=ms(n+6,n+7);}
 gpu.auxiliary=Math.max(0,gpu.simulation-gpu.source-gpu.velocity-gpu.pressure-gpu.transport);
 return gpu;
}
