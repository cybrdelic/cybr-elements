import test from 'node:test';
import assert from 'node:assert/strict';
import {NativeFeedbackReadbacks} from './native-feedback-readbacks.mjs';
import {PyroSolver} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/solver.js';
globalThis.GPUMapMode={READ:1};

function host() {
  // Only encode methods are inert in this CPU gate. The production collector
  // and frame's CFL/substep selection remain the actual implementation.
  const pass={setPipeline(){},setBindGroup(){},dispatchWorkgroups(){},end(){}};
  const encoder={clearBuffer(){},copyBufferToBuffer(){},beginComputePass(){return pass;},finish(){return {};}};
  return Object.assign(Object.create(PyroSolver.prototype),{
    time:1,burstAge:1,N:128,maxSpeed:3,stateEpoch:1,errors:[],frameNumber:0,completedFrames:0,
    latestTelemetry:{maxSpeed:3,sampleFrame:0,gpu:null},inFlight:[],active:false,
    telemetrySlots:[],c:[{}],ci:0,opticalMasks:[{}],roomTargets:[{}],lightReady:true,roomVisible:false,
    device:{createCommandEncoder:()=>encoder,queue:{submit(){},onSubmittedWorkDone:async()=>{}}},
    prepareSource:async()=>{},updateObject(){},step(e,dt){this.time+=dt;},stamp(){},dispatch(){},
    group(){return {};},chemistryBindings:()=>[],objectBindings:()=>[],meshShadowBindings:()=>[],render(){},
  });
}
function startReadback(scheduler, solver, sampleFrame, speed, epoch=1) {
  scheduler.frame=sampleFrame;
  const stats=scheduler.attach({__rid:sampleFrame},16),slot={stats,pending:true};
  const collecting=solver.collectTelemetry(slot,1,sampleFrame,epoch,1/60,false);
  const [request]=scheduler.requests();
  scheduler.accept(request.request,new Float32Array([speed,10,2,100]));
  return {slot,collecting,request};
}
for(const lag of [0,4,8])test(`production collector consumes native bytes only after ${lag} completed-frame delay`,async()=>{
  const scheduler=new NativeFeedbackReadbacks(lag),solver=host();
  const {slot,collecting}=startReadback(scheduler,solver,1,18.2);
  if(lag){
    await scheduler.deliver(lag);
    assert.equal(slot.pending,true);assert.equal(solver.maxSpeed,3);
    assert.equal(solver.latestTelemetry.sampleFrame,0);
  }
  await scheduler.deliver(1+lag);await collecting;
  assert.equal(slot.pending,false);assert.equal(slot.stats.mapState,'unmapped');
  assert.equal(solver.maxSpeed,Math.fround(18.2));assert.equal(solver.latestTelemetry.sampleFrame,1);
  // Zero lag is the exact next-frame case. Larger lags preserve production's
  // lag prediction rather than resetting its sample frame in the harness.
  solver.frameNumber=1+lag;
  const result=await solver.frame(1/60);
  assert.ok(result.substeps>=5);assert.equal(result.maxSpeed,Math.fround(18.2));
  assert.equal(result.telemetryAge,1+lag);
});
test('three occupied readback slots remain pending until real delayed completion',async()=>{
  const scheduler=new NativeFeedbackReadbacks(8),solver=host();
  const reads=[1,2,3].map(frame=>startReadback(scheduler,solver,frame,frame+10));
  await scheduler.deliver(8);assert.equal(reads.filter(r=>r.slot.pending).length,3);
  await scheduler.deliver(9);assert.equal(reads.filter(r=>r.slot.pending).length,2);
  assert.equal(solver.latestTelemetry.sampleFrame,1);
  await scheduler.deliver(11);await Promise.all(reads.map(r=>r.collecting));
  assert.equal(solver.latestTelemetry.sampleFrame,3);assert.equal(solver.maxSpeed,13);
});
test('1558.85 native velocity triggers the exact production guard and stops the next production frame',async()=>{
  const scheduler=new NativeFeedbackReadbacks(),solver=host();solver.time=1.4833333333333;
  const {collecting,slot}=startReadback(scheduler,solver,89,1558.85);
  await scheduler.deliver(89);await collecting;
  assert.equal(slot.pending,false);assert.equal(solver.maxSpeed,3);
  const error='Invalid velocity state: '+JSON.stringify({time:solver.time,sampleFrame:89,maxSpeed:Math.fround(1558.85)});
  assert.deepEqual(solver.errors,[error]);await assert.rejects(solver.frame(1/60),e=>e.message===error);
});
test('finite excessive feedback stops at the production 12-substep budget guard',async()=>{
  const scheduler=new NativeFeedbackReadbacks(),solver=host();
  const {collecting}=startReadback(scheduler,solver,1,100);
  await scheduler.deliver(1);await collecting;solver.frameNumber=1;
  await assert.rejects(solver.frame(1/60),/CFL requires more than 12 steps/);
});
test('stale epoch readback is released without overwriting current production telemetry',async()=>{
  const scheduler=new NativeFeedbackReadbacks(),solver=host();
  const {collecting,slot}=startReadback(scheduler,solver,1,20,0);
  await scheduler.deliver(1);await collecting;
  assert.equal(slot.pending,false);assert.equal(solver.maxSpeed,3);assert.equal(solver.latestTelemetry.sampleFrame,0);
});
test('late older native completion cannot replace a newer production velocity sample',async()=>{
  const scheduler=new NativeFeedbackReadbacks(),solver=host();
  scheduler.frame=1;
  const older={stats:scheduler.attach({__rid:1},16),pending:true};
  const collecting=solver.collectTelemetry(older,1,1,1,1/60,false);
  const [olderRequest]=scheduler.requests();
  const newer=startReadback(scheduler,solver,2,22);
  await scheduler.deliver(2);await newer.collecting;
  assert.equal(solver.latestTelemetry.sampleFrame,2);
  scheduler.accept(olderRequest.request,new Float32Array([5,1,1,1]));
  await scheduler.deliver(3);await collecting;
  assert.equal(solver.maxSpeed,22);assert.equal(solver.latestTelemetry.sampleFrame,2);assert.equal(older.pending,false);
});
test('actual production sparse pool collector receives the full32-byte native status',async()=>{
  const scheduler=new NativeFeedbackReadbacks(4),solver=host();
  solver.chemistryPool={plan:{capacity:64,atlasBytes:123456}};scheduler.frame=1;
  const slot={poolStatus:scheduler.attach({__rid:99},32),poolPending:true};
  const collecting=solver.collectPoolTelemetry(slot,1,1);
  const [request]=scheduler.requests();scheduler.accept(request.request,new Uint32Array([0,40,32,8,24,0,7,1]));
  await scheduler.deliver(4);assert.equal(slot.poolPending,true);
  await scheduler.deliver(5);await collecting;
  assert.equal(slot.poolPending,false);assert.equal(solver.latestTelemetry.poolSampleFrame,1);
  assert.deepEqual(solver.latestTelemetry.brickPool,{mode:'sparse',requested:40,resident:32,allocated:8,free:24,
    overflow:0,epoch:7,migrationPending:true,capacity:64,additionalAtlasBytes:123456});
});
test('missing/short payloads cannot produce a fabricated mapped readback',async()=>{
  const scheduler=new NativeFeedbackReadbacks(),buffer=scheduler.attach({__rid:1},16);
  const mapping=buffer.mapAsync(1);const [request]=scheduler.requests();
  assert.throws(()=>scheduler.accept(request.request,new Uint8Array(15)),/payload/);
  assert.throws(()=>buffer.getMappedRange(),/not mapped/);
  scheduler.fail(Error('native worker failed'));
  await assert.rejects(mapping,/native worker failed/);
});
