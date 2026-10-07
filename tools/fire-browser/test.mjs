import {test} from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {stats,resolveAsset,performanceSummary} from './helpers.mjs';
test('static server refuses traversal and malformed paths',()=>{
  const root=path.resolve('fixture');
  assert.equal(resolveAsset(root,'/assets/a.js'),path.join(root,'assets/a.js'));
  assert.throws(()=>resolveAsset(root,'/../../secret'));
  assert.throws(()=>resolveAsset(root,'/%2e%2e/%2e%2e/secret'));
  assert.throws(()=>resolveAsset(root,'/%00'));
});
test('performance summary does not invent GPU timing or count RAF as rendered FPS',()=>{
  assert.equal(stats([]),null);
  const result=performanceSummary({frames:[10,10,10,100],draws:120,gpu:[],longTasks:[80],renderer:'SwiftShader',adapter:null},2);
  assert.equal(result.frameIntervalMs.p95,100);assert.equal(result.framesOver50ms,1);
  assert.equal(result.drawsPerSecond,60);assert.equal(result.sampledOriginalSubmissionGpuMs,null);
  assert.equal(result.softwareRenderer,true);assert(!('renderedFps' in result));
});

import {gpuCosts} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/gpu-costs.js';
test('GPU stage accounting counts nested intervals once and excludes stale paused simulation',()=>{
 const t=new BigUint64Array(102);const set=(i,ms)=>t[i]=BigInt(ms)*1000000n;
 for(const [i,ms]of [[0,100],[1,103],[2,103],[3,113],[4,113],[5,118],[6,118],[7,120],[96,100],[97,120],[98,120],[99,122],[100,122],[101,125]])set(i,ms);
 const cost=gpuCosts(t,1);assert.equal(cost.source,3);assert.equal(cost.velocity,10);assert.equal(cost.pressure,5);assert.equal(cost.transport,2);assert.equal(cost.simulation,20);assert.equal(cost.auxiliary,0);assert.equal(cost.simulation+cost.lighting+cost.render,25);
 const paused=gpuCosts(t,0);assert.equal(paused.simulation,0);assert.equal(paused.source+paused.velocity+paused.pressure+paused.transport,0);assert.equal(paused.lighting+paused.render,5);
 t[3]=0n;assert.throws(()=>gpuCosts(t,1),/timestamp/);
});
import {simulationShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/shaders.js';
import {adaptiveFlowShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/adaptive-flow.js';
test('ordinary fire and adaptive flow generate without the power registry',()=>{
 const ordinary=simulationShaders(128,256,{hasPowers:false});
 const powers=simulationShaders(128,256,{hasPowers:true});
 assert(ordinary.correctScalar.length<powers.correctScalar.length-20000);
 assert(ordinary.correctScalar.includes('fn isPower()->bool{return false;}'));
 assert.doesNotThrow(()=>adaptiveFlowShaders(128,256,8,{hasPowers:false}));
});


test('browser stage summaries keep real GPU timings separate from RAF cadence',()=>{
 const result=performanceSummary({frames:[5,5],draws:0,gpu:[],longTasks:[],gpuStages:[[40,0,12,8,10,0,6,4,4.02],[60,0,20,12,16,0,8,4,4.52]]},1);
 assert.equal(result.webGpuStageMs.flow.mean,16);
 assert.equal(result.webGpuStageMs.total.mean,50);
 assert.equal(result.webGpuStageMs.total.count,2);
 assert.equal(result.sampledOriginalSubmissionGpuMs,null);
 const empty=performanceSummary({frames:[],draws:0,gpu:[],longTasks:[]},1);
 assert.equal(empty.webGpuStageMs.total,null);
});

import {simulationAdvanced} from './helpers.mjs';
test('stall detection uses actual simulation time even when the throttled metric label stays unchanged',()=>{
 assert(simulationAdvanced({simulationTime:2.5,metrics:'same'},{simulationTime:2.6,metrics:'same'}));
 assert(!simulationAdvanced({simulationTime:2.5,metrics:'old'},{simulationTime:2.5,metrics:'new'}));
 assert(simulationAdvanced({simulationTime:null,metrics:'old'},{simulationTime:null,metrics:'new'}));
});
