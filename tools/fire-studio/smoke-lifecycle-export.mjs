// Export production WGSL and production cadence schedules for the native gate.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {advanceSmokeDecay,SMOKE_CLEAR_DENSITY}=await import(pathToFileURL(path.join(root,'smoke-lifecycle.js')).href);
const {simulationShaders}=await import(pathToFileURL(path.join(root,'pyro-gpu/shaders.js')).href);
const actual=simulationShaders(8,8).correctScalar;
const oldFactor='exp(-p.lifecycle.x*.045)',oldCleanup=`c<vec4f(${SMOKE_CLEAR_DENSITY},.00001,.000001,.0001)`;
if(actual.split(oldFactor).length!==2||actual.split(oldCleanup).length!==2)throw Error('Production soot expression changed; review native control');
// Isolate the previous two soot expressions; all other production logic,
// resources and operators remain identical to the actual current shader.
const legacy=actual.replace(oldFactor,'exp(-p.step.x*.045)').replace(oldCleanup,'c<vec4f(.000001,.00001,.000001,.0001)');
function scenario(kind,density,seconds,substeps,shader='actual'){
 const steps=Math.round(seconds*60*substeps),dt=1/(60*substeps),schedule=[];let remainder=0;
 for(let i=0;i<steps;i++){
  const next=advanceSmokeDecay(remainder,dt);remainder=next.remainder;
  schedule.push([dt,i*dt,next.decayDt]);
 }
 return {kind,density,substeps,shader,seconds:steps*dt,schedule,decayTotal:schedule.reduce((sum,s)=>sum+s[2],0)};
}
const scenarios=[];
for(const substeps of [1,2,3,12]){
 scenarios.push(scenario('normal',.04,2,substeps),scenario('tail',.000035,12,substeps),scenario('tiny',.00001,1/60,substeps),scenario('fresh',1,1/60,substeps));
}
for(const substeps of [1,2,3,12])scenarios.push(scenario('legacy-normal',.04,2,substeps,'legacy'),scenario('legacy-tail',.000035,2,substeps,'legacy'));
const target=path.resolve(process.argv[2]||'work/fuel-studio-qa/smoke-lifecycle-fixture.json');fs.mkdirSync(path.dirname(target),{recursive:true});
fs.writeFileSync(target,JSON.stringify({root,N:8,D:8,threshold:SMOKE_CLEAR_DENSITY,actual,legacy,scenarios}));
console.log(JSON.stringify({target,scenarios:scenarios.length,dispatches:scenarios.reduce((n,s)=>n+s.schedule.length,0),bytes:fs.statSync(target).size}));
