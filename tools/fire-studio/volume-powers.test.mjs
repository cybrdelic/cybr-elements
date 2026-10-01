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
  assert.ok(fine.correctScalar.includes('c.y+=added*.8*p.chemistry.x/(1.+c.z);c.z+=added;c.w/=1.+added;'));
  assert.ok(fine.correctVelocity.includes('powerAcceleration(powerKind(),x'));
  for(const code of [fine.buildBricks,adaptive.sourceWork]){
    assert.ok(code.includes('sourceLive=powerBrickLive(at,halfBrick)'));
    assert.ok(code.includes('powerFireballCenter(p.source.xyz,scale,p.step.z,p.power.xyz)'));
    assert.ok(code.includes('powerRainCenter(vec2f(f32(x),f32(z)),p.step.z)'));
    assert.ok(code.indexOf('if(isPower()){')<code.indexOf('}else if(p.effect.x>.5){'));
  }
});
