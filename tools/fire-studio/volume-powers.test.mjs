// These gates execute production host hooks and inspect their generated WGSL.
// Native replay separately compiles the shaders and evolves the gas fields.
import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load=file=>import(pathToFileURL(resolve(root,file)).href);
const {PyroSolver}=await load('pyro-gpu/solver.js');
const {simulationShaders}=await load('pyro-gpu/shaders.js');
const {adaptiveFlowShaders}=await load('pyro-gpu/adaptive-flow.js');
const {FuelBrush}=await load('fuel-ground.js');
const {POWER_DEFINITIONS}=await load('fire-powers.js');

function solver(kind=22){
  const s=Object.create(PyroSolver.prototype);
  Object.assign(s,{effect:[kind,1,.18,0],source:[0,.8,0],powerDirection:[1,0,0],
    powerStrength:1,burstAge:2,time:3,seed:2,stateEpoch:0,maxSpeed:1,active:false,
    previousDt:1/60,lightReady:true,fuel:1,smoke:false,
    floorFuelKind:null,hasFloorFuel:false,floorIgnition:false,fuelBrush:new FuelBrush(),
    device:{createTexture(){throw Error('Unexpected power GPU allocation');},
      createBuffer(){throw Error('Unexpected power GPU allocation');}}});
  return s;
}
const pendingMass=s=>s.fuelBrush.pending.reduce((a,b)=>a+b,0);
// Execute the production scalar helpers directly after the minimal WGSL
// scalar-to-JS translation. This checks their physics invariants, not a
// second implementation that could disagree with the GPU source.
function scalarHelper(name){
  const code=simulationShaders(128,256).correctScalar;
  const match=new RegExp('fn '+name+'\\(([^)]*)\\)->(?:f32|bool)\\{').exec(code);
  assert.ok(match,'production helper '+name);
  const args=match[1].split(',').map(arg=>arg.trim().split(':')[0]);
  const start=match.index+match[0].length;let end=start,depth=1;
  while(depth){if(code[end]==='{')depth++;if(code[end]==='}')depth--;end++;}
  const body=code.slice(start,end-1).replace(/\b(max|min|exp|abs|pow|sqrt)\(/g,'Math.$1(');
  return new Function(...args,body);
}

test('source work uses the shared phase and trajectory support for all bounded cast records',()=>{
 const fine=simulationShaders(128,256),adaptive=adaptiveFlowShaders(128,256);
 for(const code of [fine.buildBricks,adaptive.sourceWork]){
  const support=code.slice(code.indexOf('fn powerBrickLive('),code.indexOf('fn charge('));
  assert.ok(support.includes('i<4u'),'work is bounded to four cast records');
  assert.ok(support.includes('actor.kindScale.z<.5'),'inactive sources cannot allocate chemistry work');
  assert.ok(support.includes('halfBrick*1.733'),'support includes a conservative brick sphere padding');
  assert.ok(support.includes('powerCastSupport(actor.kindScale.x,at,actor.originAge.xyz,actor.kindScale.y,actor.originAge.w'));
  assert.ok(support.includes('actor.targetCharge.xyz,actor.directionStrength.xyz,actor.targetCharge.w'),'aim and charge use the same source support');
 }
});

test('power ignition is bounded, preserves hot gas and is independent of source substeps',()=>{
  const ignite=scalarHelper('powerIgnition');
  for(const preheat of [.65,.72,.75]){
    const target=preheat*1.8;
    for(const heat of [0,.35,.7,1.6])for(const added of [0,.01,.3,1,10]){
      const next=ignite(heat,added,preheat);
      assert.ok(next>=heat&&next<=Math.max(heat,target)+1e-12);
      if(heat>=target)assert.equal(next,heat,'a pilot cannot cool or reheat already hot gas');
    }
    let subdivided=0;for(let i=0;i<120;i++)subdivided=ignite(subdivided,.5/120,preheat);
    assert.ok(Math.abs(subdivided-ignite(0,.5,preheat))<1e-12);
    assert.ok(subdivided>.75*target,'moving packets receive ignition before leaving their source');
    assert.ok(ignite(0,.02,preheat)>.6*target,
      'a brief thin source receives ignition before sweeping out of a voxel');
  }
});

test('fuel injection dilutes available oxygen while preserving its existing mass',()=>{
  const oxygen=scalarHelper('powerOxygen');
  for(const deficit of [0,.1,.5,1])for(const added of [0,.001,.1,1,10]){
    const next=oxygen(deficit,added);
    assert.ok(next>=deficit&&next<=1);
    assert.ok(Math.abs((1-next)*(1+added)-(1-deficit))<1e-12);
  }
  let rich=0;for(let i=0;i<100;i++)rich=oxygen(rich,.1);
  assert.ok(rich>.9999,'an unmixed fuel-rich core cannot receive artificial fresh oxygen');
});

test('casting each power normalizes aim, clamps strength and resets only its source clock',()=>{
  for(let kind=22;kind<=27;kind++){
    const s=solver(kind),at=[.4,.7,-.3];
    assert.equal(s.castPower(at,[2,.4,-1],3),true);
    assert.deepEqual(s.source,at);assert.notEqual(s.source,at);
    assert.ok(Math.abs(Math.hypot(...s.powerDirection)-1)<1e-12);
    assert.equal(s.powerStrength,2);assert.equal(s.burstAge,0);
    assert.equal(s.time,3,'casting keeps the transported scene time');
    assert.equal(s.active,true);assert.equal(s.previousDt,0);assert.equal(s.lightReady,false);
    assert.ok(s.maxSpeed>=12,'new impulse is covered before delayed velocity telemetry');
  }
});

test('invalid power inputs cannot partially replace a valid cast',()=>{
  for(const [at,direction,strength] of [[[0,0,0],[0,0,0],1],[[NaN,0,0],[1,0,0],1],
    [[0,0,0],[1,0,0],NaN],[[0,0],[1,0,0],1]]){
    const s=solver(),before={source:[...s.source],direction:[...s.powerDirection],age:s.burstAge,epoch:s.stateEpoch};
    assert.equal(s.castPower(at,direction,strength),false);
    assert.deepEqual(s.source,before.source);assert.deepEqual(s.powerDirection,before.direction);
    assert.equal(s.burstAge,before.age);assert.equal(s.stateEpoch,before.epoch);
  }
  assert.equal(solver(0).castPower([0,1,0],[1,0,0],1),false);
  const s=solver(23);s.castPower([0,.8,0],[1,0,0],1);
  const before=s.powerCasts.snapshot();
  assert.equal(s.castPower([1,.8,0],[0,0,1],1,{target:[NaN,0,0]}),false);
  assert.deepEqual(s.powerCasts.snapshot(),before,'an invalid target preserves active casts');
});

test('the shared registry controls membership, movement and launch snapshots for every ability',()=>{
  for(const definition of POWER_DEFINITIONS){
    const effect=definition.kind+21,s=solver(effect);
    assert.deepEqual(s.selectedPower(),definition);
    assert.equal(s.castPower([0,.8,0],[1,0,0],.75),true,definition.id+' casts');
    s.powerDirection=[0,0,-1];s.powerStrength=2;
    assert.deepEqual(s.powerUniform(),definition.continuous?[0,0,-1,2]:[1,0,0,.75],definition.id+' aim lifetime');
    assert.equal(s.movePower([.5,.8,.5]),definition.continuous&&definition.movable!==false,definition.id+' movement');
  }
  const unknown=Math.max(...POWER_DEFINITIONS.map(p=>p.kind))+22;
  const s=solver(unknown);
  assert.equal(s.selectedPower(),null);assert.equal(s.castPower(),false);assert.equal(s.movePower([0,1,0]),false);
  const code=simulationShaders(128,256).correctScalar;
  const membership=code.match(/fn isPower\(\)->bool\{([^}]+)\}/)[1];
  for(const definition of POWER_DEFINITIONS)assert.ok(membership.includes('p.effect.x=='+(definition.kind+21)+'.'),definition.id+' GPU membership');
  assert.ok(!membership.includes('p.effect.x=='+unknown+'.'),'unregistered IDs do not enter power physics');
  assert.ok(!code.includes('powerBombBrick'),'new abilities do not enter the old bomb classifier');
});

test('rain and tornado move without recasting; projectiles and bombs retain launch origin',()=>{
  for(const kind of [22,23,27]){
    const s=solver(kind);assert.equal(s.movePower([1,1,1]),false);
    assert.deepEqual(s.source,[0,.8,0]);assert.equal(s.burstAge,2);
  }
  for(const kind of [24,25]){
    const s=solver(kind);assert.equal(s.movePower([1,1,1],[0,0,-4]),true);
    assert.deepEqual(s.source,[1,1,1]);assert.deepEqual(s.powerDirection,[0,0,-1]);
    assert.equal(s.burstAge,2);assert.equal(s.time,3);assert.ok(s.maxSpeed>=8);
  }
});

test('launch aim and strength stay fixed until recast while continuous controls stay live',()=>{
  for(const kind of [22,23,27]){
    const s=solver(kind);s.castPower([0,.8,0],[1,0,0],.75);
    s.powerDirection=[0,0,-1];s.powerStrength=2;
    assert.deepEqual(s.powerUniform(),[1,0,0,.75]);
    s.castPower();assert.deepEqual(s.powerUniform(),[0,0,-1,2]);
  }
  for(const kind of [24,25,26]){
    const s=solver(kind);s.castPower([0,.8,0],[1,0,0],.75);
    s.powerDirection=[0,0,-1];s.powerStrength=2;
    assert.deepEqual(s.powerUniform(),[0,0,-1,2]);
  }
});

test('floor trail leaves finite ignited deposits and never refills a stationary cursor',()=>{
  const s=solver(26);s.effect[3]=1;
  assert.equal(s.castPower([0,.08,0],[1,0,0],1),true);
  assert.equal(s.fuelBrush.radius,.22);assert.equal(s.fuelBrush.amount,.65);
  const initial=pendingMass(s);assert.ok(initial>0);assert.equal(s.floorIgnition,true);
  assert.equal(s.floorFuelKind,1);assert.equal(s.hasFloorFuel,true);
  for(let i=0;i<120;i++)assert.equal(s.movePower([0,.08,0]),false);
  assert.equal(pendingMass(s),initial);
  assert.equal(s.movePower([1,.08,0]),true);assert.ok(pendingMass(s)>initial);
  assert.equal(s.burstAge,0,'trail movement retains its active clock');
  assert.equal(s.fuelBrush.consume().data.length,128**2);
  assert.equal(s.fuelBrush.consume(),null,'each floor dose is uploaded once');
});

test('overlapping casts retain separate clocks and aim in the fixed appended uniform pool',()=>{
  const s=solver(23);
  s.castPower([-.8,.8,0],[1,0,0],.75);
  s.powerCasts.step(.1);
  s.castPower([.4,.8,.2],[0,0,1],1.25);
  const out=new Float32Array(96);out.fill(19,0,32);s.powerCasts.write(out,32);
  assert.ok(out.subarray(0,32).every(v=>v===19),'the original 128-byte prefix is preserved');
  assert.ok(Math.abs(out[35]-.1)<1e-6);assert.equal(out[51],0,'recasting only starts the new actor clock');
  assert.ok(Math.abs(out[32]+.8)<1e-6);assert.ok(Math.abs(out[48]-.4)<1e-6);
  assert.deepEqual([...out.subarray(36,39)],[1,0,0]);assert.deepEqual([...out.subarray(52,55)],[0,0,1]);
  for(let i=0;i<9;i++)s.castPower([i*.01,.8,0],[1,0,0],1);
  assert.equal(s.powerCasts.snapshot().active,4,'repeated casts cannot grow GPU work without a bound');
  assert.equal(s.time,3,'the scene gas clock is retained');
  s.stopPower();s.powerCasts.write(out,32);
  for(let i=0;i<4;i++)assert.equal(out[42+i*16],0,'stopping retires every source record');
  assert.equal(s.time,3,'stopping leaves transported gas to the solver');
});

test('charged aiming stays separate from release and protects a later impulse before telemetry',()=>{
  const definition=POWER_DEFINITIONS.find(p=>p.hold);
  assert.ok(definition);
  const s=solver(definition.kind+21);
  s.castPower([0,.8,0],[1,0,0],1,{held:true,target:[1,.2,.5]});
  s.powerCasts.step(2);
  assert.equal(s.powerCasts.snapshot().held,true);
  assert.equal(s.aimPower([1.5,.14,-.5],[0,0,-1]),true);
  const out=new Float32Array(96);s.powerCasts.write(out,32);
  assert.equal(out[42],2,'held anticipation is explicitly encoded');
  assert.equal(s.releasePower([1.5,.14,-.5],[0,0,-1]),true);
  s.powerCasts.write(out,32);assert.equal(out[42],1);
  assert.ok(Math.abs(out[35]-definition.windup)<1e-6);
  const delayed=solver(27);delayed.castPower();
  delayed.powerCasts.step(1.19);
  assert.ok(delayed.powerCasts.speedFloor(.02)>=12,'delayed blast is safe before readback sees its speed');
  assert.equal(delayed.powerCasts.crossesImpulse(.02),true,'the impact step invalidates a stale pressure guess');
  const cancelled=solver(definition.kind+21);cancelled.castPower([0,.8,0],[1,0,0],1,{held:true});
  assert.equal(cancelled.cancelPower(),true);assert.equal(cancelled.powerCasts.snapshot().active,0);
  assert.equal(cancelled.releasePower(),false,'a cancelled gesture cannot launch when the pointer returns');
});

test('all generated gas paths use the same power source before the legacy jet branch',()=>{
  const fine=simulationShaders(128,256),adaptive=adaptiveFlowShaders(128,256);
  for(const [name,code] of [['velocity',fine.correctVelocity],['scalar',fine.correctScalar],
    ['coarse',adaptive.coarseCorrect],['fine',adaptive.fineCorrect]]){
    assert.ok(code.includes('power:vec4f'),name);
    const source=code.slice(code.indexOf('fn charge('),code.indexOf('fn sourceVelocity('));
    assert.ok(source.indexOf('if(isPower())')<source.indexOf('if(p.effect.x>18.5)'),name);
    assert.ok(code.includes('powerSample(x)'),name);
  }
  assert.ok(fine.correctScalar.includes('let added=s*p.step.x*6.*p.chemistry.y;'));
  assert.ok(fine.correctScalar.includes('c.y=powerIgnition(c.y,added,p.chemistry.x);c.z+=added;c.w=powerOxygen(c.w,added);'));
  assert.ok(fine.correctScalar.includes('burned*select(3.2,2.0,isPower())'));
  assert.ok(fine.correctScalar.includes('if(isPower()){c.w=powerOxygen(c.w,floorAdded);}'),'finite power floor vapor conserves existing oxygen mass too');
  assert.ok(fine.correctVelocity.includes('powerForce(x)'));
  for(const code of [fine.correctVelocity,adaptive.coarseCorrect,adaptive.fineCorrect]){
    assert.ok(code.includes('select(1.,p.dynamics.z,isPower())*cross('),'all flow paths use authored power confinement');
    const main=code.slice(code.lastIndexOf('@compute'));
    assert.equal((main.match(/powerInjection\(x\)/g)||[]).length,1,'velocity samples each power packet only once');
    assert.ok(main.includes('abs(object.tint.w)<=.5&&p.source.w>=.5'));
    assert.ok(main.includes('}else{s=charge(x);if(s>0.){out=mix(out,sourceVelocity(x),1.-exp(-s*p.step.x*65.));}}'),'ordinary source momentum keeps its existing path');
  }
  const injection=fine.correctVelocity.slice(fine.correctVelocity.indexOf('fn powerInjection('),fine.correctVelocity.indexOf('fn powerSample('));
  assert.equal((injection.match(/powerCastSource\(/g)||[]).length,1,'each bounded actor is sampled once');
  assert.ok(injection.includes('expansion+=value.w*powerCastExpansion(actor.kindScale.x,actor.originAge.w)'),'expansion follows each actor phase using its existing gas weight');
  assert.ok(fine.correctVelocity.includes('var s=0.;var sourceExpansion=45.;'),'ordinary source expansion remains unchanged');
  for(const code of [fine.buildBricks,adaptive.sourceWork]){
    assert.ok(code.includes('sourceLive=powerBrickLive(at,halfBrick)'));
    assert.ok(code.includes('powerCastSupport(actor.kindScale.x,at,actor.originAge.xyz'),'all cast trajectories use canonical support');
    assert.ok(code.indexOf('if(isPower()){')<code.indexOf('}else if(p.effect.x>.5){'));
  }
});
