import {shaderFunctionsToGLSL} from './shader-language.js?v=studio-rc-37-repair';
// Shared reduced gas units. Finite wood retains its measured material heat
// release and hot-product ignition memory. These are not species chemistry.
export const GAS_CHEMISTRY=Object.freeze({oxygenPerFuel:.7,rate:5.8,heatRelease:5.5,ignitionLow:.35,ignitionHigh:.75,cooling:.9,hotCooling:.7});
export function mixSourceMomentum(oldVelocity,sourceVelocity,oldFuel,added){
 if(![...oldVelocity,...sourceVelocity,oldFuel,added].every(Number.isFinite)||oldFuel<0||added<0)throw Error('Invalid source momentum');
 const fraction=added/(1+oldFuel+added);
 return oldVelocity.map((v,i)=>v+(sourceVelocity[i]-v)*fraction);
}

// Intensive pilot heat and air displacement for a finite released fuel dose.
// Both engines compile these functions from the same source.
export const sourceMixingWGSL=`
fn smokeLossRate(temperature:f32)->f32{return mix(.16,.055,smoothstep(.15,.8,temperature));}
fn smokeWeight(soot:f32,temperature:f32)->f32{
 return min(max(soot,0.),.5)*.035*(1.-smoothstep(.15,.8,temperature));
}
fn sourceSampleAge(age:f32,state:f32,dt:f32)->f32{
 if(state>1.5){return max(age,0.);}return age+.5*dt;
}
fn sourceClock(clock:f32,seed:f32,dt:f32)->f32{return clock+.5*dt+seed*11.37;}
fn sourceIgnition(heat:f32,added:f32,preheat:f32)->f32{
 return heat+max(1.8*preheat-heat,0.)*(1.-exp(-48.*added));
}
fn sourceMixtureDeficit(deficit:f32,added:f32,incomingOxygen:f32)->f32{return (deficit+added*(1.-incomingOxygen))/(1.+added);}
fn sourceOxygenDeficit(deficit:f32,added:f32)->f32{return (deficit+added)/(1.+added);}
fn sourceSensibleHeat(heat:f32,fuel:f32,added:f32,incoming:f32)->f32{
 return (heat*(1.+fuel)+added*incoming)/(1.+fuel+added);
}
// Incoming power fuel is warm vapor, not a pre-rendered incandescent body.
// A bounded igniter acts where oxygen can support combustion. Rich interiors
// retain advected heat but are not forced to the same white-hot temperature.
fn powerIgnitionHeat(heat:f32,fuel:f32,added:f32,pilot:f32,oxygen:f32)->f32{
 let mixed:f32=sourceSensibleHeat(heat,fuel,added,.08);
 let oxygenWeight:f32=.45+.55*smoothstep(.1,.75,clamp(oxygen,0.,1.));
 return sourceIgnition(mixed,added,max(pilot,0.)*.47*oxygenWeight);
}
fn densityBuoyancy(temperature:f32,referenceAcceleration:f32)->f32{
 return referenceAcceleration*1.25*max(temperature,0.)/(.25+max(temperature,0.));
}

fn sourceMomentumFraction(oldFuel:f32,added:f32)->f32{return added/(1.+max(oldFuel,0.)+added);}
`;
export const sourceMixingGLSL=shaderFunctionsToGLSL(sourceMixingWGSL);
