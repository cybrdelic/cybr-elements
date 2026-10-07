import {GAS_CHEMISTRY} from '../reduced-chemistry.js?v=studio-rc-37-audit';
import {WOOD_THERMO} from '../wood-thermo.js?v=studio-rc-37-audit';
export const WOOD_GAS_HEAT_RELEASE=WOOD_THERMO.volatileHeatJkg*WOOD_THERMO.gasSensibleFraction/(WOOD_THERMO.gasHeatCapacityJkgK*WOOD_THERMO.gasHeatScaleK);
// Scalar layout: soot, temperature, fuel, oxygen deficit (zero is fresh air).
// Shared by transport, expansion and emission so they use the same reaction.
// Wood uses a reduced hot-product ignition memory: real advected soot and
// oxygen consumption indicate prior burning. This is not radical/species
// chemistry. Cold products alone cannot burn; fuel, oxygen and heat remain
// required and products cool below480 K into the same extinguished state.
const smooth=(low,high,value)=>{const t=Math.max(0,Math.min(1,(value-low)/(high-low)));return t*t*(3-2*t);};
export function woodCombustionActivation(c){
  if(c.length!==4||!Array.from(c).every(value=>Number.isFinite(value)&&value>=0))
    throw Error('Invalid wood combustion state');
  const ignited=smooth(.005,.05,Math.max(c[0],c[3]));
  return Math.max(smooth(.35,.75,c[1]),ignited*smooth(.15,.35,c[1]));
}
export function woodReactionRate(c){
  return Math.min(c[2],Math.max(1-c[3],0)/.7)*4*woodCombustionActivation(c);
}
export const combustionWGSL=`
fn richSootYield(fuel:f32,oxygen:f32)->f32{
 let richness=.7*max(fuel,0.)/max(oxygen,.02);
 return mix(.35,1.,smoothstep(.3,1.2,richness));
}
fn reactionRate(c:vec4f)->f32{
 let oxygen=max(1.-c.w,0.);
 return min(max(c.z,0.),oxygen/${GAS_CHEMISTRY.oxygenPerFuel})*${GAS_CHEMISTRY.rate}*smoothstep(${GAS_CHEMISTRY.ignitionLow},${GAS_CHEMISTRY.ignitionHigh},c.y);
}
fn flameActivity(c:vec4f)->f32{return min(reactionRate(c)*.5,1.);}
fn woodCombustionActivation(c:vec4f)->f32{
 let products=smoothstep(.005,.05,max(c.x,c.w));
 return max(smoothstep(.35,.75,c.y),products*smoothstep(.15,.35,c.y));
}
fn woodReactionRate(c:vec4f)->f32{
 let oxygen=max(1.-c.w,0.);
 return min(max(c.z,0.),oxygen/.7)*4.*woodCombustionActivation(c);
}
fn woodFlameActivity(c:vec4f)->f32{return min(woodReactionRate(c)*.5,1.);}
`;
// Include this only with objectWGSL. Non-wood source chemistry is unchanged.
export const objectCombustionWGSL=`
fn sceneHeatRelease(ordinary:f32)->f32{
 return select(ordinary,${WOOD_GAS_HEAT_RELEASE.toFixed(8)},abs(object.tint.w)>.5);
}

fn sceneReactionRate(c:vec4f)->f32{
 if(abs(object.tint.w)>.5){return woodReactionRate(c);}return reactionRate(c);
}
fn sceneFlameActivity(c:vec4f)->f32{
 if(abs(object.tint.w)>.5){return woodFlameActivity(c);}return flameActivity(c);
}
// Per-step reduced reaction ledger: fuel mass, oxygen-deficit equivalent,
// sensible heat and soot are accounted together. Gas products stay implicit
// in the all-air pressure solve to avoid another full-resolution species field.
fn sceneReactionLedger(c:vec4f,dt:f32,heatRelease:f32,sootYield:f32)->vec4f{
 if(c.z<=0.||c.w>=1.||c.y<=.15){return vec4f(0);}
 let rate=select(${GAS_CHEMISTRY.rate},4.,abs(object.tint.w)>.5);
 let requested=max(sceneReactionRate(c),0.)*(1.-exp(-rate*max(dt,0.)))/rate;
 let burned=min(min(max(c.z,0.),requested),max(1.-c.w,0.)/.7);
 let oxygenDemand=burned*.7;
 let heat=max(heatRelease,0.)*burned/max(1.+c.z,1.);
 let soot=max(sootYield,0.)*burned*richSootYield(c.z,max(1.-c.w,0.));
 return vec4f(burned,oxygenDemand,heat,soot);
}
`;
