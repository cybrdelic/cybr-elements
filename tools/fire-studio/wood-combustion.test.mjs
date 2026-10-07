import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load=file=>import(pathToFileURL(resolve(root,file)).href);
const {WOOD_GAS_HEAT_RELEASE,woodCombustionActivation,woodReactionRate,combustionWGSL,objectCombustionWGSL}=await load('pyro-gpu/combustion.js');
const {simulationShaders}=await load('pyro-gpu/shaders.js');
const {rendererShaders}=await load('pyro-gpu/renderer.js');
const {planBrickPool,brickPoolScalarShaders}=await load('pyro-gpu/brick-pool.js');
const {PyroSolver,woodIgnitionSpeedFloor}=await load('pyro-gpu/solver.js');
const smooth=(a,b,x)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t);};
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-12,`${a} != ${b}`);
test('fresh wood gas retains the original ignition barrier without hot products',()=>{
  for(const temperature of [0,.14,.15,.2,.3,.35,.5,.75,1.5]){
    close(woodCombustionActivation([0,temperature,1,0]),smooth(.35,.75,temperature));
  }
  assert.equal(woodReactionRate([0,.3,1,0]),0);
  assert.ok(woodReactionRate([0,.8,1,0])>0);
  assert.match(combustionWGSL,/return min\(max\(c\.z,0\.\),oxygen\/0.7\)\*5.8\*smoothstep\(0.35,0.75,c\.y\)/);
});
test('real soot or oxygen consumption sustains warm ignition but cold smoke always quenches',()=>{
  for(const products of [[.05,0],[0,.05],[.05,.1]]){
    const [soot,deficit]=products;
    assert.ok(woodCombustionActivation([soot,.25,1,deficit])>0);
    for(const temperature of [0,.1,.1499,.15])assert.equal(woodReactionRate([soot,temperature,1,deficit]),0);
  }
  assert.equal(woodCombustionActivation([.005,.25,1,0]),0);
  assert.ok(woodCombustionActivation([.02,.25,1,0])<woodCombustionActivation([.05,.25,1,0]));
});
test('reduced product memory never supplies fuel, oxygen or more than bounded reaction activity',()=>{
  for(const temperature of [0,.2,.3,.5,2])for(const soot of [0,.02,1])for(const deficit of [0,.05,.5,1]){
    const activation=woodCombustionActivation([soot,temperature,3,deficit]);
    assert.ok(activation>=0&&activation<=1);
    assert.ok(activation>=smooth(.35,.75,temperature));
    assert.ok(woodReactionRate([soot,temperature,3,deficit])<=Math.min(3,(1-deficit)/.7)*4+1e-12);
    assert.equal(woodReactionRate([soot,temperature,0,deficit]),0);
  }
  assert.equal(woodReactionRate([1,2,4,1]),0);
  assert.throws(()=>woodCombustionActivation([0,NaN,1,0]),/Invalid wood combustion/);
});
test('closed reactive packets conserve fuel and stoichiometric oxygen across timestep partitions',()=>{
  for(const partitions of [1,3,12]){
    let c=[0,.8,4,0],burnedTotal=0;const dt=1/(60*partitions);
    for(let step=0;step<180*partitions;step++){
      const burned=Math.min(c[2],woodReactionRate(c)*(1-Math.exp(-4*dt))/4);
      burnedTotal+=burned;c[2]-=burned;c[3]=Math.min(c[3]+.7*burned,1);
      c[1]=(c[1]+burned*WOOD_GAS_HEAT_RELEASE/(1+c[2]))*Math.exp(-dt*(.9+.7*Math.max(c[1]-1.4,0)));
      c[0]+=burned*1.8;
      assert.ok(c.every(Number.isFinite));
      close(c[2]+burnedTotal,4);close(c[3],.7*burnedTotal);
    }
    assert.ok(burnedTotal>0&&burnedTotal<=1/.7);
    // Temperature is still mandatory once a fully established product cloud cools.
    assert.equal(woodReactionRate([c[0],.14,c[2],c[3]]),0);
  }
});
test('dense and pooled scalar transport and thermal expansion use identical wood routing',()=>{
  const shaders=simulationShaders(128,256),pooled=brickPoolScalarShaders(planBrickPool({D:256,capacity:1024}),{N:128,shaders});
  for(const code of [shaders.correctScalar,pooled.correctScalar])assert.match(code,/let reaction=select\(sceneReactionLedger\(c,p\.step\.x/);
  assert.match(shaders.correctVelocity,/completedVolumeSourceAt\(x,N\)/);
  assert.match(objectCombustionWGSL,/if\(abs\(object\.tint\.w\)>\.5\)\{return woodReactionRate\(c\);\}return reactionRate\(c\)/);
  assert.match(objectCombustionWGSL,/if\(abs\(object\.tint\.w\)>\.5\)\{return woodFlameActivity\(c\);\}return flameActivity\(c\)/);
});
test('camera rays and both lighting gathers evaluate the same physical wood activity',()=>{
  for(const tree of [false,true])for(const sparse of [false,true]){
    const family=rendererShaders(tree,sparse);
    assert.match(family.render,/fn emission\(c:vec4f,reaction:f32\)/);
    assert.match(family.render,/if\(sigma<\.0001&&consumed<\.0001\)/);
    assert.match(family.gather,/max\(consumedReactionAt\(at\),c\.x\*max\(c\.y-\.55,0\.\)\)/);
    assert.match(family.gatherAdaptive,/let value=emission\(field\(at\),consumedReactionAt\(at\)\)/);
  }
});
test('wood source timestep margin is finite, requires active structured wood and survives Relight',()=>{
  for(const tree of [false,true]){
    const end=tree?3:4.5;
    assert.equal(woodIgnitionSpeedFloor(true,true,0,tree),12);
    assert.equal(woodIgnitionSpeedFloor(true,true,end-1e-6,tree),12);
    assert.equal(woodIgnitionSpeedFloor(true,true,end,tree),0);
    assert.equal(woodIgnitionSpeedFloor(true,true,end+10,tree),0);
    assert.equal(woodIgnitionSpeedFloor(true,false,.5,tree),0);
    assert.equal(woodIgnitionSpeedFloor(false,true,.5,tree),0);
    assert.equal(woodIgnitionSpeedFloor(true,true,-.1,tree),0);
    assert.equal(woodIgnitionSpeedFloor(true,true,0,tree),12,'Relight starts a fresh bounded window');
  }
});
test('production frame binds the newly live object uniform in coarse light gather and chooses safe startup dt',async()=>{
  const solver=Object.create(PyroSolver.prototype),calls=[],dts=[];
  const gather={id:'gather'},refine={id:'refine'},objectSettings={id:'object-settings'};
  const pass={setPipeline(){},setBindGroup(){},dispatchWorkgroups(){},end(){}};
  Object.assign(solver,{lost:false,errors:[],N:128,maxSpeed:0,burstAge:.5,active:true,
    woodStructure:{},objectId:'logs',frameNumber:0,completedFrames:0,inFlight:[],latestTelemetry:{sampleFrame:0},
    lightReady:false,roomVisible:false,usingTree:false,useLightWork:false,useLightReceivers:false,source:[0,1,0],D:256,reactionLedger:{},reactionOffset:0,
    c:[{}],ci:0,sampler:{},view:{},lightSeeds:{},fireLights:{},objectSettings,
    roomTargets:[{}],opticalMasks:[{}],telemetrySlots:[],stats:{},gatherPipeline:gather,gatherAdaptivePipeline:refine,
    prepareSource:async()=>{},updateObject(){},stamp(){},render(){},dispatch(){},
    step(encoder,dt){dts.push(dt);},group(pipeline,entries){calls.push({pipeline,entries});return{};},
    chemistryBindings(){return[];},objectBindings(){return[[13,{buffer:objectSettings}]];},meshShadowBindings(){return[];},
    device:{createCommandEncoder:()=>({clearBuffer(){},beginComputePass:()=>pass,finish:()=>({})}),
      queue:{submit(){},onSubmittedWorkDone:()=>Promise.resolve()}}});
  await solver.frame(1/60);
  const entries=calls.find(call=>call.pipeline===gather).entries;
  assert.deepEqual(entries.map(([binding])=>binding),[61,0,1,2,5]);
  assert.ok(entries.some(([binding])=>binding===61),"gather reads the actual consumed-fuel ledger");
  assert.equal(dts.length,3);assert.ok(dts.every(dt=>dt===1/180));
});

test('wood vapor reaction heat converts joules to the gas temperature coordinate',()=>{
 close(WOOD_GAS_HEAT_RELEASE*1200*1200,19200000*.7);
 for(const fuel of [.01,.5,2]){
   const burned=Math.min(fuel,.2),heat=burned*WOOD_GAS_HEAT_RELEASE/(1+fuel);
   close(heat*(1+fuel)*1200*1200/(burned*19200000*.7),1);
 }
});
