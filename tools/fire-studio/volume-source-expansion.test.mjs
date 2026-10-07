import test from 'node:test';
import assert from 'node:assert/strict';
import {simulationShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/shaders.js';
import {adaptiveFlowShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/adaptive-flow.js';
import {gasThermoWGSL,PLUME_THERMAL,GAS_THERMO} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/gas-thermodynamics.js';
import {reactionLedgerWGSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/reaction-ledger.js';
function evaluate(name,args,extras={}){
 const start=gasThermoWGSL.indexOf('fn '+name+'('),open=gasThermoWGSL.indexOf('{',start);let end=open+1,depth=1;
 for(;depth;end++){if(gasThermoWGSL[end]==='{')depth++;if(gasThermoWGSL[end]==='}')depth--;}
 const body=gasThermoWGSL.slice(open+1,end-1).replace(/\b(let|var)\s+(\w+)\s*:\s*f32/g,'let $2');
 const fn=new Function(...args,'max','abs','log',...Object.keys(extras),body);
 return (...values)=>fn(...values,Math.max,Math.abs,Math.log,...Object.values(extras));
}
const log1p=evaluate('gasLog1p',['value']);
const source=evaluate('thermalVolumeChange',['oldTemperature','newTemperature','fuelBeforeSources','fuelAfterSources','dt'],{gasLog1p:log1p});
const close=(a,b)=>assert.ok(Math.abs(a-b)<=5e-9*Math.max(1,Math.abs(a),Math.abs(b)),a+' != '+b);
const adaptive=adaptiveFlowShaders(128,256);
for(const [name,code] of Object.entries({volume:simulationShaders(128,256).correctVelocity,supported:simulationShaders(128,256,{flowSupport:true}).correctVelocity,coarse:adaptive.coarseCorrect,fine:adaptive.fineCorrect}))test(name+' pressure uses completed fine chemistry without a second source count',()=>{
 assert.match(code,/var expansion=completedVolumeSourceAt\(x,N\)/);
 assert.doesNotMatch(code,/expansion\+=woodFluxVolumeSource|thermalExpansionRate\(sceneReactionRate/);
 const scalar=simulationShaders(128,256).correctScalar;
 assert.ok(scalar.indexOf('let fuelBeforeSources=c.z')<scalar.indexOf('let added=s*p.step.x*6.'));
 assert.ok(scalar.indexOf('let fuelAfterSources=c.z')<scalar.indexOf('let reaction=select(sceneReactionLedger'));
 assert.ok(scalar.indexOf('c.y=coolGasTemperature')<scalar.indexOf('let volumeSource=thermalVolumeChange'));
 assert.match(scalar,/storeCombustion\(i,/);
});
test('recorded volume reconstructs the density change of heating, cooling and injection',()=>{
 for(const [oldT,newT,oldF,newF] of [[0,0,0,0],[0,0,0,1e-9],[1,.7,0,0],[.7,1.3,.4,.6],[2,.1,2,2]])for(const dt of [1/30,1/120,.001]){
  const div=source(oldT,newT,oldF,newF,dt),ratio=(.25+newT)/(.25+oldT)*(1+newF)/(1+oldF);
  close(Math.exp(div*dt),ratio);assert.ok(Number.isFinite(div));
 }
 assert.ok(source(1,.7,0,0,1/30)<0,'cooling contracts, rather than injecting more volume');
 assert.ok(source(0,0,0,1e-9,1/30)>0,'tiny finite wood doses survive float cancellation');
 assert.equal(source(1,1,1,1,1/30),0,'fuel-to-products conversion does not remove gas mass');
});
test('wood dose partitions retain the same integrated volume and do not lose pressure to normalization',()=>{
 const total=.8,initial=2,frameDt=1/60;
 for(const parts of [[1],[.5,.5],[.1,.2,.3,.4],Array(12).fill(1/12)]){
  let fuel=initial,integral=0;
  for(const fraction of parts){const next=fuel+total*fraction;integral+=source(.7,.7,fuel,next,frameDt*fraction)*frameDt*fraction;fuel=next;}
  close(Math.exp(integral),(1+initial+total)/(1+initial));
 }
});
test('global and refined pressure restrict all fine source cells by volume',()=>{
 const code=reactionLedgerWGSL(256);
 assert.match(code,/span=max\(1u,REACTION_D\/gridN\)/);
 assert.match(code,/total\/f32\(span\*span\*span\)/);
 for(const span of [2,4]){
  const values=Array.from({length:span**3},(_,i)=>(i%5-2)*.01);
  const mean=values.reduce((a,b)=>a+b,0)/values.length;
  close(mean*(span*.0234375)**3,values.reduce((a,b)=>a+b,0)*.0234375**3);
 }
});

const pilotDose=evaluate('boundedPilotDose',['age','dt','rate','startupRate','duration'],{min:Math.min});
test('plume ignition has a finite timestep-independent power budget',()=>{
 const p=PLUME_THERMAL;
 for(const parts of [[4],Array(240).fill(1/60),[.12,.13,.01,.99,2.75]]){
  let age=0,total=0;
  for(const dt of parts){total+=pilotDose(age,dt,p.pilotHeatingRate,p.startupHeatingRate,p.startupDurationS);age+=dt;}
  close(total,p.pilotHeatingRate*age+p.startupHeatingRate*p.startupDurationS);
 }
 assert.equal(pilotDose(-1,.1,8,4,.25),0,'a pending source does not deposit heat');
 close(pilotDose(-.1,.2,8,4,.25),1.2);
 assert.equal(pilotDose(1,0,8,4,.25),0,'pausing supplies no energy');
 close(pilotDose(5,.01,8,4,.25),.08);
 close(pilotDose(1e20,.001,8,4,.25),.008); // large age cannot erase a small steady dose
 const incoming=(p.fuelTemperatureK-GAS_THERMO.ambientK)/GAS_THERMO.temperatureScaleK;
 assert.ok(incoming<.35,'the incoming plume fuel cannot ignite the entire source bed');
});
test('compact external pilot heat enters completed expansion after source mixing',()=>{
 const shader=simulationShaders(128,256,{hasPowers:false}).correctScalar;
 assert.ok(shader.indexOf('let temperatureBeforeReaction=c.y')<shader.indexOf('c.y+=externalPilotHeat'));
 assert.ok(shader.indexOf('c.y+=externalPilotHeat')<shader.indexOf('let reaction=select(sceneReactionLedger'));
 assert.ok(shader.indexOf('let reaction=select(sceneReactionLedger')<shader.indexOf('let volumeSource=thermalVolumeChange'));
 assert.match(shader,/externalPilotHeat=pilotDose\*exp\(-dot\(pilotQ,pilotQ\)\)\/\(1\.\+c\.z\+added\)/);
});
