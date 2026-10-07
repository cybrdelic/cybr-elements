// Four flags: live state, camera/light support, positive soot and optional
// fine-flow support. Pack them into one word; supported devices reduce each
// subgroup before touching the shared atomic. No wave width is assumed.
export function occupancyReductionWGSL(subgroups=false){
 return `
var<workgroup> combinedFlags:atomic<u32>;
fn reduceOccupancy(flags:u32,lane:u32${subgroups?',subgroupLane:u32':''})->u32{
 if(lane==0u){atomicStore(&combinedFlags,0u);}workgroupBarrier();
 ${subgroups?`let waveFlags=subgroupOr(flags);
 if(subgroupLane==0u&&waveFlags!=0u){atomicOr(&combinedFlags,waveFlags);}`:
 `if(flags!=0u){atomicOr(&combinedFlags,flags);}`}
 workgroupBarrier();return atomicLoad(&combinedFlags);
}`;
}
