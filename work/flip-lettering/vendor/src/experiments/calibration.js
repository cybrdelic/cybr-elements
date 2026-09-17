/** Bounded inverse art-direction experiment, evaluated by the actual FLIP core.
 * No learned surrogate, test rewriting, or unchecked neural pressure solution.
 * Targets are normalized particle second moments at specified simulated times.
 */
import {FlipSolver} from '../flip.js';
const copy=x=>JSON.parse(JSON.stringify(x));
function moments(sim){const n=sim.count,mean=[0,0,0],variance=[0,0,0];for(let i=0;i<n;i++)for(let c=0;c<3;c++)mean[c]+=sim.p[i*3+c]/n;for(let i=0;i<n;i++)for(let c=0;c<3;c++)variance[c]+=(sim.p[i*3+c]-mean[c])**2/n;const trace=variance.reduce((a,b)=>a+b,0);return {center:mean,variance,normalized:variance.map(v=>v/Math.max(trace,1e-20))};}
export function observeLiquid(config,{dt=1/120,frames=24,sampleEvery=4}={}){
 if(!(dt>0&&dt<=.05&&Number.isInteger(frames)&&frames>=1&&frames<=1000&&Number.isInteger(sampleEvery)&&sampleEvery>0))throw Error('Invalid experiment time range.');
 const sim=new FlipSolver(copy(config)),observations=[];let maximumResidual=0;
 for(let f=1;f<=frames;f++){const info=sim.advance(dt);if(!info.finite||info.solidViolations||info.capacityRejected||info.pressureFailures)throw Error('Forward simulation violates fixed feasibility constraints.');maximumResidual=Math.max(maximumResidual,info.pressure.relativeResidual);if(f%sampleEvery===0)observations.push({frame:f,time:info.time,...moments(sim)});}
 return {observations,maximumResidual,particles:sim.count,pressureSolves:sim.pressureSolveCount,finite:true};
}
export function fitSurfaceTension(config,target,{min=.02,max=.20,budget=25,time={dt:1/120,frames:24,sampleEvery:4}}={}){
 if(!(min>=0&&max>min&&max<=2&&Number.isInteger(budget)&&budget>=9&&budget<=256))throw Error('Invalid bounded optimization request.');
 if(!Array.isArray(target)||target.length!==Math.floor(time.frames/time.sampleEvery)||target.some(r=>!Array.isArray(r.normalized)||r.normalized.length!==3||r.normalized.some(x=>!Number.isFinite(x))))throw Error('Invalid target observations.');
 const trials=[],memo=new Map();let best=null;
 const evaluate=sigma=>{sigma=Math.max(min,Math.min(max,sigma));const key=sigma.toPrecision(14);if(memo.has(key))return memo.get(key);if(trials.length>=budget)return null;
  let trial={sigma,feasible:false,loss:null};try{const c=copy(config);c.surfaceTension=sigma;const state=observeLiquid(c,time);let loss=0;for(let i=0;i<target.length;i++){if(Math.abs(target[i].time-state.observations[i].time)>1e-8)throw Error('Target/sample times disagree.');for(let j=0;j<3;j++)loss+=(state.observations[i].normalized[j]-target[i].normalized[j])**2;}trial={...trial,feasible:true,loss:loss/(target.length*3),state};if(!best||trial.loss<best.loss)best=trial;}catch(e){trial.error=String(e.message??e);}
  trials.push(trial);memo.set(key,trial);return trial;};
 // A coarse sweep avoids relying on a monotonic oscillatory response, then a
 // shrinking trust interval refines the best actually evaluated candidate.
 const baseline=evaluate(config.surfaceTension??.072);
 for(let i=0;i<8;i++)evaluate(min+(max-min)*i/7);
 if(!best)throw Error('No feasible forward simulations.');let step=(max-min)/14;
 while(trials.length<budget&&step>1e-8){const before=best.loss,center=best.sigma;evaluate(center-step);evaluate(center+step);if(best.loss>=before*(1-1e-10))step*=.5;else step*=.75;}
 return {parameter:'surfaceTension',units:'N/m',bounds:[min,max],baseline:baseline?.loss??null,bestSigma:best.sigma,bestLoss:best.loss,configuration:{...copy(config),surfaceTension:best.sigma},trials,budget,evaluations:trials.length,target,time,fixedFeasibilityChecks:['finite primary state','no analytic-solid penetration','no rejected emitter volume','no failed pressure solves'],scope:'Synthetic low-resolution capillary-shape fit; not real-video reconstruction or a general differentiable fluid solver.'};
}
