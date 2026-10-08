// Small CPU fixture: execute emitted scalar helpers and the live reaction block.
// No transport, shader compiler, GL context, browser or substitute rendered fire.
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {createOriginalShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-shaders.js';
import {GAS_THERMO,PLUME_THERMAL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/gas-thermodynamics.js';
import {GAS_CHEMISTRY} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/reduced-chemistry.js';
import {FIRE_PRESETS} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/presets.js';
import {abilityMotionWGSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-ability-motions.js';
const runtime=new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url);
const emitterSource=await readFile(new URL('fire-emitters.js',runtime),'utf8'),context={window:{}};vm.runInNewContext(emitterSource,context);
const assembled=createOriginalShaders({domain:{nx:640,ny:360,depth:32,extent:[14,7.875,1.8],minimum:[-7,-1.05,-.9],extentGLSL:'vec3(14.00000,7.87500,1.80000)',minimumGLSL:'vec3(-7.00000,-1.05000,-.90000)',object:false},hasPowers:false,hasWood:false,initialPowerKind:2,MAX_POWER_EMITTER:45,renderSize:[896,504],emittersGLSL:context.window.FireEmitters,propsGLSL:'',woodMaterialGLSL:''});
export const simulation=typeof assembled.simulation==='function'?assembled.simulation(2,{pressureGLSL:'',vorticityGLSL:'',advectionGLSL:''}):assembled.simulation;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x)),smoothstep=(a,b,x)=>{const t=clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);},mix=(a,b,t)=>a+(b-a)*t;
const math={max:Math.max,min:Math.min,exp:Math.exp,abs:Math.abs,pow:Math.pow,sqrt:Math.sqrt,log:Math.log,sin:Math.sin,cos:Math.cos,atan2:Math.atan2,clamp,smoothstep,mix};
function block(source,name){const match=new RegExp('float '+name+'\\(([^)]*)\\)\\{').exec(source);assert(match,'Missing emitted helper '+name);let p=match.index+match[0].length,end=p,depth=1;while(depth){if(source[end]==='{')depth++;if(source[end]==='}')depth--;end++;}return {args:match[1].split(',').filter(Boolean).map(a=>a.trim().split(/\s+/).at(-1)),body:source.slice(p,end-1)};}
const js=source=>source.replace(/\bfloat\s+(?=\w+\s*[=;,])/g,'let ');
const helpers={};for(const name of ['sourceSensibleHeat','sourceIgnition','sourceMixtureDeficit','sourceSampleAge','sourceClock','ordinaryFuelRate','boundedPilotDose','powerIgnitionHeat','coolGasTemperature','richSootYield','smokeLossRate']){
 const part=block(simulation,name),deps={...math,...helpers},run=new Function(...part.args,...Object.keys(deps),js(part.body));helpers[name]=(...args)=>run(...args,...Object.values(deps));
}
export const {boundedPilotDose,sourceSampleAge,sourceClock,powerIgnitionHeat}=helpers;
const pilot=simulation.match(/temp=sourceSensibleHeat\(temp,fuel,added,0\.08000000\);[\s\S]*?temp\+=dose[^;]+;/)[0];
const pilotCode=js(pilot.replace(/\s*vec3 q=[^;]+;\s*vec3 pilotQ=[^;]+;/,'').replace('dot(pilotQ,pilotQ)','pilotNormSquared'));
const pilotRun=new Function('temp','fuel','added','burstAge','delta','sourceHeat','pilotNormSquared',...Object.keys(helpers),'exp',pilotCode+'return {temperature:temp,dose};');
export const livePilotAgeArgument=pilot.match(/boundedPilotDose\(([^,]+),/)[1];
export function plumeInjection(state,{added,endAge,delta,sourceHeat=1,pilotNormSquared=0}){
 const output=pilotRun(state.temperature,state.fuel,added,endAge,delta,sourceHeat,pilotNormSquared,...Object.values(helpers),Math.exp);
 const sensible=helpers.sourceSensibleHeat(state.temperature,state.fuel,added,.08),capacity=1+state.fuel+added;
 return {...state,fuel:state.fuel+added,oxygen:1-helpers.sourceMixtureDeficit(1-state.oxygen,added,0),temperature:output.temperature,
  pilotDose:output.dose,sourceEnergyJPerM3:energyUnit*added*.08,pilotEnergyJPerM3:energyUnit*capacity*(output.temperature-sensible)};
}
export const energyUnit=GAS_THERMO.referenceDensityKgM3*GAS_THERMO.heatCapacityJkgK*GAS_THERMO.temperatureScaleK;
const reaction=simulation.slice(simulation.indexOf('    float activation;'),simulation.indexOf('    // Buoyancy, resolved swirl'));
assert(reaction.includes('soot+=burn*sootYield;'));
const reactionRun=new Function('state','delta','smokeDecayDt','fuelProfile','smokeOnly','woodEnabled',...Object.keys(math),...Object.keys(helpers),
 'let {fuel,oxygen,temperature:temp,soot}=state;'+js(reaction)+';return {fuel,oxygen,temperature:temp,soot,burn,mixtureCapacity,activation,oxidized};');
export function react(state,delta,{sootYield=.708,smokeOnly=false}={}){
 const next=reactionRun(state,delta,delta,{y:sootYield},Number(smokeOnly),0,...Object.values(math),...Object.values(helpers));
 return {...next,chemicalFuelConsumedKgPerM3:GAS_THERMO.referenceDensityKgM3*next.burn,oxygenConsumedKgPerM3:GAS_THERMO.referenceDensityKgM3*(.7*next.burn+.08*next.oxidized),reactionHeatAtPreReactionCapacityJPerM3:energyUnit*GAS_CHEMISTRY.heatRelease*next.burn};
}
export function pilotBudget(parts){let age=0,dose=0;for(const delta of parts){age+=delta;dose+=plumeInjection({temperature:0,fuel:0,oxygen:1,soot:0},{added:0,endAge:age,delta}).pilotDose;}return {age,dose,expected:PLUME_THERMAL.pilotHeatingRate*age+PLUME_THERMAL.startupHeatingRate*Math.min(age,PLUME_THERMAL.startupDurationS)};}
const fuelProfiles={wood:[1,.708,1],gas:[.85,.12,1.25],oil:[1.15,1.8,.85]};
const r2Formula=emitterSource.match(/float x=local\.x\/sourceScale,y=local\.y\/sourceScale,z=depth\/sourceScale;\s*r2=([^;]+);/)[1];
const r2Run=new Function('x','y','z','pow','return '+r2Formula);
export function plumeProbe(preset='sooty-plume',{seconds=.5,delta=1/30,active=true,pilotNormSquared=0}={}){
 const profile=FIRE_PRESETS.find(p=>p.id===preset),fuel=profile?.fuel||'wood',feed=fuelProfiles[fuel][0]*(profile?.chemistry[1]??1),sourceHeat=profile?.chemistry[0]??1;
 const [x,y,z]=PLUME_THERMAL.pilotOffset,r2=r2Run(x,y,z,Math.pow),plumeFeed=mix(.90,1,smoothstep(.08,.92,.5)),brush=Math.exp(-1.5*r2)*plumeFeed;
 let state={fuel:0,oxygen:1,temperature:0,soot:0},burned=0,pilotEnergy=0,sensibleEnergy=0,firstBurn=null;
 for(let step=0;step<Math.round(seconds/delta);step++){
  const endAge=(step+1)*delta,pulse=.94+.06*Math.sin(endAge*2.3+.7),added=active?brush*delta*helpers.ordinaryFuelRate(profile?.effect[0]??-1,1)*pulse*feed:0;
  const injection=active?plumeInjection(state,{added,endAge,delta,sourceHeat,pilotNormSquared}):state;
  pilotEnergy+=injection.pilotEnergyJPerM3||0;sensibleEnergy+=injection.sourceEnergyJPerM3||0;
  state=react(injection,delta,{sootYield:fuelProfiles[fuel][1]*(profile?.chemistry[2]||1)});burned+=state.burn;if(state.burn>0&&firstBurn===null)firstBurn=endAge;
 }
 return {preset,fuel,active,seconds,delta,firstBurn,normalizedFuelBurned:burned,pilotEnergyJPerM3:pilotEnergy,sensibleEnergyJPerM3:sensibleEnergy,final:state,kelvin:GAS_THERMO.ambientK+GAS_THERMO.temperatureScaleK*state.temperature,scope:'Manufactured stationary parcel at actual plume pilot offset with fixed feed-noise sample0.5. Live scalar helpers and reaction block, including local grey-body cooling; excludes transport, diffusion, geometry, spatial integration and native F16/F32 execution. Not a native flame claim.'};
}
const cue=abilityMotionWGSL.match(/fn abilityCue\([^\n]+\{([\s\S]*?)\n\}/)[1]
 .replace(/return vec4f\(0\)/g,'return 0')
 .replace('let d:vec3f=q-vec3f(0,.36+.08*u,0);','let d={x:q.x,y:q.y-(.36+.08*u),z:q.z};')
 .replace('length(d.xz)','Math.hypot(d.x,d.z)')
 .replace(/let radial:vec3f=[^;]+;/,'')
 .replace(/return vec4f\([^\n]+;/,'return w;')
 .replace(/\blet (\w+):f32=/g,'let $1=');
const cueRun=new Function('q','t','end','clock',...Object.keys(math),cue);
export function fireballCueWeight(q,t,clock=t){return cueRun(q,t,.22,clock,...Object.values(math));}
export function fireballDoseProbe({added=.02,oxygen=1,oldTemperature=0,delta=1/80}={}){
 const profile=FIRE_PRESETS.find(p=>p.id==='fireball'),newOxygen=oxygen/(1+added),temperature=powerIgnitionHeat(oldTemperature,0,added,profile.chemistry[0],newOxygen);
 const state=react({fuel:added,oxygen:newOxygen,temperature,soot:0},delta,{sootYield:.12*profile.chemistry[2]});
 return {added,oxygenBefore:oxygen,oxygenAfterMixing:newOxygen,sourceTemperature:temperature,temperatureK:300+1200*temperature,afterReaction:state,scope:'Exact shared bounded power-igniter and Original reaction for one manufactured released dose; excludes moving carrier/geometry/entrainment.'};
}
