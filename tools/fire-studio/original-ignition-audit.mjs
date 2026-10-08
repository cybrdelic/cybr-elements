// Reproducible CPU evidence; does not create a browser or graphics context.
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {pilotBudget,plumeProbe,fireballCueWeight,fireballDoseProbe,energyUnit,livePilotAgeArgument} from './original-ignition-fixture.mjs';
const runtime=new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url);
const sourceHashes={};
for(const file of ['original-shaders.js','gas-thermodynamics.js','reduced-chemistry.js','fire.js','fire-emitters.js','fire-ability-motions.js','pyro-gpu/presets.js']){
 sourceHashes[file]=createHash('sha256').update(await readFile(new URL(file,runtime))).digest('hex');
}
const report={
 at:new Date().toISOString(),CPUOnly:true,GPUStarted:false,sourceHashes,livePilotAgeArgument,
 units:{temperature:'(kelvin-300)/1200',referenceDensityKgPerM3:1,heatCapacityJPerKgK:1200,energyJPerM3PerNormalizedTemperature:energyUnit,
  mass:'normalized concentrations times reference density; the reduced model does not track individual product species',
  energy:'Incoming sensible and external pilot energy are accounted at the actual mixture capacity. Reaction heat is a reduced-model source, not detailed species enthalpy.'},
 budgets:{steps30Hz:pilotBudget(Array(30).fill(1/30)),steps60Hz:pilotBudget(Array(60).fill(1/60)),unequal:pilotBudget([.12,.13,.01,.24,.5])},
 budgetLossAt30Hz:{missingNormalizedDose:4/30,totalOneSecondDose:9,totalDoseLossPercent:100*(4/30)/9,finiteStartupIncrement:1,startupIncrementLossPercent:100*(4/30)/1,
  missingEnergyAtReferencePilotCenterJPerM3:energyUnit*(4/30),totalOneSecondEnergyAtReferencePilotCenterJPerM3:energyUnit*9,startupIncrementEnergyAtReferencePilotCenterJPerM3:energyUnit},
 presets:{free:plumeProbe('free'),sooty:plumeProbe('sooty-plume'),unlitFree:plumeProbe('free',{active:false}),awayFromPilot:plumeProbe('sooty-plume',{pilotNormSquared:100})},
 fireball:{windupSeconds:.22,cueWeightAtPoint:fireballCueWeight({x:.26,y:.4,z:0},.1),
  thin:fireballDoseProbe({added:.001}),resolved:fireballDoseProbe({added:.02}),rich:fireballDoseProbe({added:1,oxygen:.1})},
 scope:'Executes emitted production scalar helpers, the plume injection block and the Original reaction block using JavaScript doubles. Manufactured stationary parcels; no advection, diffusion, spatial integration, native GLSL execution or rendered-flame claim.'
};
const output=JSON.stringify(report,null,2)+'\n';
if(process.argv[2])await writeFile(process.argv[2],output);else process.stdout.write(output);
