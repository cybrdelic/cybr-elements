import {shaderFunctionsToGLSL} from './shader-language.js?v=studio-rc-37-repair';
// Reduced gas units match the wood sensible-energy conversion. A world-unit
// scene remains an authored scale; this is not detailed species chemistry.
export const GAS_THERMO=Object.freeze({ambientK:300,temperatureScaleK:1200,heatCapacityJkgK:1200,referenceDensityKgM3:1,stefanBoltzmann:5.670374419e-8,ambientMixingRate:.35});
// Prescribed warm-vapor feed and compact igniter for the continuous plume.
// Heating rates are normalized temperature/s in the reduced gas model.
export const PLUME_THERMAL=Object.freeze({fuelTemperatureK:396,pilotHeatingRate:8,startupHeatingRate:4,startupDurationS:.25,referencePilotHeat:.9,pilotOffset:Object.freeze([.18,-.08,.05]),pilotWidth:Object.freeze([.18,.10,.18])});
export const gasThermoWGSL=`
fn boundedPilotDose(age:f32,dt:f32,rate:f32,startupRate:f32,duration:f32)->f32{
 // Do not subtract two large ages: a long-running source must retain its
 // small per-step power dose when the age's float ULP exceeds dt.
 let activeTime:f32=max(0.,max(dt,0.)+min(age,0.));
 let startupTime:f32=min(activeTime,max(0.,max(duration,0.)-max(age,0.)));
 return max(rate,0.)*max(activeTime,0.)+max(startupRate,0.)*startupTime;
}
fn ordinaryFuelRate(effect:f32,continuous:f32)->f32{
 if(effect<.5){if(continuous>.5){return 1.8;}return 9.;}
 if(effect>18.5){return 6.;}return 3.;
}
fn coolGasTemperature(temperature:f32,fuel:f32,soot:f32,dt:f32)->f32{
 let heat:f32=max(temperature,0.);let offset:f32=1200.*heat;let kelvin:f32=300.+offset;
 // Factor T⁴-Tambient⁴: no transcendental power, and no subtraction of two
 // nearly equal large numbers in cold smoke. This is the same grey-gas law.
 let fourthDifference:f32=offset*(kelvin+300.)*(kelvin*kelvin+90000.);
 let radiation:f32=4.*max(soot,0.)*4.4*5.670374419e-8*fourthDifference/(1440000.*max(1.+fuel,1.));
 // A positive local implicit loss handles the stiff T^4 term without a clamp
 // or a cooling step that changes with display frequency.
 return heat/(1.+max(dt,0.)*(.35+max(radiation,0.)/max(heat,.000001)));
}
fn gasLog1p(value:f32)->f32{
 if(abs(value)<.01){let square:f32=value*value;return value-.5*square+value*square/3.-.25*square*square;}
 return log(1.+value);
}
fn thermalVolumeChange(oldTemperature:f32,newTemperature:f32,fuelBeforeSources:f32,fuelAfterSources:f32,dt:f32)->f32{
 if(dt<=0.){return 0.;}
 // Material derivative: exclude advection, include the completed heat step.
 // Fuel-to-products conversion does not remove gas mass. The mass ratio
 // uses the injected dose before reaction, not the remaining unburned fuel.
 let oldHeat:f32=max(oldTemperature,0.);let oldFuel:f32=max(fuelBeforeSources,0.);
 let heatChange:f32=(max(newTemperature,0.)-oldHeat)/(.25+oldHeat);
 let massChange:f32=(max(fuelAfterSources,0.)-oldFuel)/(1.+oldFuel);
 return (gasLog1p(heatChange)+gasLog1p(massChange))/dt;
}
`;
export const gasThermoGLSL=shaderFunctionsToGLSL(gasThermoWGSL);
