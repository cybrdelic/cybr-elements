import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {pilotBudget,plumeInjection,plumeProbe,energyUnit,react,boundedPilotDose,sourceSampleAge,sourceClock,fireballCueWeight,fireballDoseProbe,livePilotAgeArgument} from './original-ignition-fixture.mjs';
const close=(a,b)=>assert(Math.abs(a-b)<=2e-12*Math.max(1,Math.abs(a),Math.abs(b)),`${a} != ${b}`);

test('live Original plume pilot consumes the prescribed startup budget using the physical step start',t=>{
 for(const parts of [Array(30).fill(1/30),Array(60).fill(1/60),[.12,.13,.01,.24,.5]]){const row=pilotBudget(parts);close(row.dose,row.expected);}
 t.diagnostic(JSON.stringify({argument:livePilotAgeArgument,oneSecond:pilotBudget(Array(30).fill(1/30)),unitJPerM3:energyUnit}));
});
test('pilot budget percentages state separate total-dose and startup-increment denominators',()=>{
 const loss=9-(8+4*(.25-1/30));close(loss,4/30);
 close(100*loss/9,1.4814814814814814);close(100*loss/(4*.25),13.333333333333334);
 close(energyUnit,1440000);close(loss*energyUnit,192000);
});
test('live pilot call clips negative initial ages and variable steps at zero and the startup boundary',()=>{
 const ambient={fuel:0,oxygen:1,temperature:0,soot:0};
 // Independent interval overlap: never add energy before age zero.
 for(const [start,end] of [[-.2,-.1],[-.1,0],[-.02,.02],[0,1/30],[0,.5],[.23,.30],[.25,.31],[.3,.9]]){
  const delta=end-start,active=Math.max(0,end-Math.max(start,0)),startup=Math.max(0,Math.min(end,.25)-Math.max(start,0));
  close(plumeInjection(ambient,{added:0,endAge:end,delta}).pilotDose,8*active+4*startup);
 }
 close(plumeInjection(ambient,{added:0,endAge:0,delta:0}).pilotDose,0);
 for(const parts of [[.5,.5],[.249,.002,.749],[.001,.019,.03,.2,.75]])close(pilotBudget(parts).dose,9);
});
test('source mixing exactly accounts incoming sensible energy and the compact pilot dose',()=>{
 for(const added of [0,.001,.03,.2])for(const fuel of [0,.1,2]){
  const state={fuel,oxygen:1,temperature:.12,soot:0},next=plumeInjection(state,{added,endAge:.1,delta:1/30,sourceHeat:.9,pilotNormSquared:1});
  const before=(1+fuel)*state.temperature*energyUnit,after=(1+next.fuel)*next.temperature*energyUnit;
  close(after-before,next.sourceEnergyJPerM3+next.pilotEnergyJPerM3);
  close(next.pilotEnergyJPerM3,next.pilotDose*Math.exp(-1)*energyUnit);
  close(next.fuel-state.fuel,added);
 }
 close(boundedPilotDose(1e20,.001,8,4,.25),.008);
 close(boundedPilotDose(0,0,8,4,.25),0);
});
test('live reaction obeys fuel/oxygen inventories and distinguishes a cold cell from a burning parcel',()=>{
 const cold=react({fuel:.2,oxygen:1,temperature:.08,soot:0},1/30);assert.equal(cold.burn,0);assert.equal(cold.soot,0);
 for(const fuel of [0,.01,.3,2])for(const oxygen of [0,.1,.8,1]){
  const state={fuel,oxygen,temperature:.8,soot:0},next=react(state,1/30);
  assert(next.burn>=0&&next.burn<=fuel&&next.burn<=oxygen/.7);
  close(next.fuel+next.burn,fuel);close(next.oxygen+next.oxygenConsumedKgPerM3,oxygen);
  assert(next.reactionHeatAtPreReactionCapacityJPerM3>=0&&Number.isFinite(next.temperature));
 }
 const smoke=react({fuel:.2,oxygen:1,temperature:.8,soot:0},1/30,{smokeOnly:true});assert.equal(smoke.burn,0);
});
test('plume pilot and free-source lifecycle are capable of ignition without changing authored heat or time',t=>{
 const free=plumeProbe('free'),sooty=plumeProbe('sooty-plume'),unlit=plumeProbe('free',{active:false}),away=plumeProbe('sooty-plume',{pilotNormSquared:100});
 assert(free.normalizedFuelBurned>0&&sooty.normalizedFuelBurned>0);assert.equal(unlit.normalizedFuelBurned,0);assert.equal(away.normalizedFuelBurned,0);
 assert(sooty.final.soot>0);t.diagnostic(JSON.stringify({free,sooty,unlit,away}));
});
test('Fireball startup is a finite cue before .22seconds and uses start-age midpoint source sampling',t=>{
 const dt=1/80;close(sourceSampleAge(0,1,dt),dt/2);close(sourceSampleAge(.1,2,dt),.1);close(sourceClock(.1,0,dt),.1+dt/2);
 const positive=fireballCueWeight({x:.26,y:.4,z:0},.1);assert(positive>0);assert.equal(fireballCueWeight({x:.26,y:.4,z:0},.22),0);
 const thin=fireballDoseProbe({added:.001}),resolved=fireballDoseProbe({added:.02}),rich=fireballDoseProbe({added:1,oxygen:.1});
 assert.equal(thin.afterReaction.burn,0);assert(resolved.afterReaction.burn>0);assert.equal(rich.afterReaction.burn,0);
 t.diagnostic(JSON.stringify({windupSeconds:.22,cueWeight:positive,thin,resolved,rich}));
});
test('Original host clock advances before chemistry while Volume submits its source age before advancing',async()=>{
 const root=new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url),fire=await readFile(new URL('fire.js',root),'utf8'),volume=await readFile(new URL('pyro-gpu/solver.js',root),'utf8');
 assert(fire.indexOf('elapsed += step')<fire.indexOf('try{runStep(step)'));
 assert.match(fire,/uniform\(simProgram,'burstAge'\),elapsed-burstStart/);
 assert(volume.indexOf('this.burstAge,')<volume.indexOf('this.burstAge += dt'));
 assert.match(fire,/else if\(freeMode\)\{extinguishButton.disabled=true/);
});
