import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load=file=>import(pathToFileURL(resolve(root,file)).href);
const {mixWoodVaporHeat,woodPacketFraction,woodFluxVolumeSource,WOOD_FLUX,woodFluxWGSL,WOOD_GAS_PILOT,
  woodGasPilotSites,woodGasPilotHeat}=await load('pyro-gpu/wood-flux.js');
const {advanceWood,gasHeatToWoodHeat,WOOD_THERMO}=await load('wood-thermo.js');
const {simulationShaders}=await load('pyro-gpu/shaders.js');
const {surfaceWGSL}=await load('pyro-gpu/objects.js');
const {planBrickPool,brickPoolScalarShaders}=await load('pyro-gpu/brick-pool.js');
const close=(a,b)=>assert.ok(Math.abs(a-b)<=1e-11*Math.max(1,Math.abs(a),Math.abs(b)),`${a} != ${b}`);

test('the unchanged scale-four Sigil pilot budget does not imply fresh gas ignition',()=>{
  const placement={origin:[0,1.9,0],scale:4},[site]=woodGasPilotSites(placement),dose=woodGasPilotHeat(site.center,{...placement,active:true,age:0,dt:4,fuel:0});
  close(WOOD_GAS_PILOT.powerW*WOOD_GAS_PILOT.durationS,480000);close(dose,.19714970139198407);assert(dose<.35);
  close(.35/dose*480000,852144.3289735094);
  assert.equal(woodGasPilotHeat(site.center,{...placement,active:false,age:0,dt:4,fuel:0}),0);
});

test('wood flux enthalpy uses the same intensive temperature units as floor fuel',()=>{
  const mass=.75,sourceK=689,sourceHeat=(sourceK-WOOD_FLUX.gasAmbientK)/WOOD_FLUX.gasHeatScaleK;
  const energyJ=mass*WOOD_FLUX.gasHeatCapacityJkgK*(sourceK-WOOD_FLUX.gasAmbientK);
  const enthalpy=energyJ/(WOOD_FLUX.gasHeatCapacityJkgK*WOOD_FLUX.gasHeatScaleK);
  close(enthalpy,mass*sourceHeat);
  close(mixWoodVaporHeat(0,0,[mass,enthalpy]),sourceHeat*mass/(1+mass));
  close(mixWoodVaporHeat(2,41.875,[mass,enthalpy]),(2*42.875+mass*sourceHeat)/(42.875+mass));
});

test('sensible energy closes for cold and fuel-dense gas without changing the source mass',()=>{
  for(const heat of [0,.3,1.4,4.207,501])for(const fuel of [0,.01,1,41.875])
    for(const mass of [1e-8,.05,1,10,512])for(const sourceHeat of [0,.324,.8,4]){
      const addedEnergy=mass*sourceHeat,capacity=1+fuel;
      const next=mixWoodVaporHeat(heat,fuel,[mass,addedEnergy]);
      close(next*(capacity+mass),heat*capacity+addedEnergy);
      assert.ok(next>=Math.min(heat,sourceHeat)-1e-12);
      assert.ok(next<=Math.max(heat,sourceHeat)+1e-12,'vapor must not manufacture a hotter temperature');
    }
});

test('cold vapor cools a hot mixture and an empty or subquantum packet is well defined',()=>{
  assert.equal(mixWoodVaporHeat(2,0,[1,0]),1);
  assert.equal(mixWoodVaporHeat(2,9,[10,0]),1);
  assert.equal(mixWoodVaporHeat(2,9,[0,0]),2);
  // Integer mass and energy have different quanta. A zero-mass represented
  // packet may retain a positive, tiny energy increment; no mass division.
  close(mixWoodVaporHeat(2,9,[0,1e-9]),2+1e-10);
  assert.throws(()=>mixWoodVaporHeat(NaN,0,[1,1]),/Invalid wood vapor/);
});

test('sequential packets and CFL partitions preserve the same aggregate sensible energy',()=>{
  const packets=[[.4,.1],[1,.3],[2,.5],[.05,0]],initialHeat=1.4,initialFuel=41.875;
  const mass=packets.reduce((sum,p)=>sum+p[0],0),energy=packets.reduce((sum,p)=>sum+p[1],0);
  const aggregate=mixWoodVaporHeat(initialHeat,initialFuel,[mass,energy]);
  for(const partitions of [1,3,12])for(const reverse of [false,true]){
    let heat=initialHeat,fuel=initialFuel;
    for(const packet of reverse?[...packets].reverse():packets)for(let i=0;i<partitions;i++){
      heat=mixWoodVaporHeat(heat,fuel,packet.map(value=>value/partitions));
      fuel+=packet[0]/partitions;
    }
    close(heat,aggregate);close(fuel,initialFuel+mass);
  }
});

test('dense nonreacting vapor cannot heat air above its source temperature',()=>{
  const sourceHeat=(689-300)/1200;let heat=0,fuel=0,energy=0;
  for(let frame=0;frame<180;frame++){
    const mass=.35,addedEnergy=mass*sourceHeat;
    heat=mixWoodVaporHeat(heat,fuel,[mass,addedEnergy]);fuel+=mass;energy+=addedEnergy;
    assert.ok(300+1200*heat<=689+1e-10);
    close(heat*(1+fuel),energy);
  }
  // The previous additive-temperature rule would exceed 24,000 K here.
  assert.ok(300+1200*energy>24000);
});

function closedWoodGas(partitions){
  let stock=[1,0,0,0],wear=[WOOD_THERMO.dryMoistureFraction,0,0,1],heat=0,fuel=0;
  let vapor=0,oxidized=0,maxGasK=300,maxWoodK=293.15;
  const dt=1/(60*partitions);
  for(let i=0;i<180*partitions;i++){
    const next=advanceWood({stock,wear,incomingHeat:gasHeatToWoodHeat(heat),dt,
      ignite:i*dt<1.2?WOOD_THERMO.starterFluxWm2:0,oxygen:1,timeScale:12});
    stock=next.stock;wear=next.wear;vapor+=next.volatileMass;oxidized+=next.oxidizedMass;
    // One-half of a 495 kg/m³ wood donor's vapor enters this unit-density
    // gas cell. No chemical heat, advection or artistic temperature cap.
    const added=495*.5*next.volatileMass;
    const sourceHeat=Math.max(293.15+500*stock[1]-300,0)/1200;
    heat=mixWoodVaporHeat(heat,fuel,[added,added*sourceHeat]);fuel+=added;
    maxGasK=Math.max(maxGasK,300+1200*heat);maxWoodK=Math.max(maxWoodK,293.15+500*stock[1]);
    assert.ok([...stock,...wear,heat,fuel].every(Number.isFinite));
  }
  close(stock[0]+stock[3]+vapor+oxidized,1);
  close(fuel,vapor*495*.5);
  return {fuel,maxGasK,maxWoodK};
}

test('closed wood/gas feedback remains bounded at 1/60 and 1/180 with 12× wood time',()=>{
  const coarse=closedWoodGas(1),fine=closedWoodGas(3);
  for(const state of [coarse,fine]){
    // Correct char shielding reduces this isolated starter's yield from the
    // old flux-leaking result. It still releases >8% of the donor's dry mass.
    assert.ok(state.fuel>20,'real finite wood release is retained');
    assert.ok(state.maxGasK<800&&state.maxWoodK<800,'sensible feedback must not run away');
  }
  assert.ok(Math.abs(coarse.fuel-fine.fuel)/fine.fuel<.005,'CFL partition does not manufacture extra mass');
  assert.ok(Math.abs(coarse.maxGasK-fine.maxGasK)<25);
});

test('dense and pooled chemistry apply identical heat mixing before optional fuel storage',()=>{
  assert.match(woodFluxWGSL,/return \(heat\*capacity\+vapor\.y\)\/\(capacity\+vapor\.x\)/);
  for(const flowSupport of [false,true]){
    const shaders=simulationShaders(128,256,{flowSupport});
    const pooled=brickPoolScalarShaders(planBrickPool({D:256,capacity:1024}),{N:128,shaders});
    for(const family of [shaders,pooled]){
      const code=family.correctScalar;
      assert.match(code,/let vapor=woodFlux(?:Fine)?Density\(x(?:,brick)?\);c\.y=woodMixGas\(c\.y,c\.z,vapor\);\s*if\(p\.step\.w<\.5\)\{c\.w=sourceOxygenDeficit\(c\.w,vapor\.x\);c\.z\+=vapor\.x;/);
      assert.doesNotMatch(code,/c\.y\+=vapor\.y/);
      // Smoke-only discards fuel storage; sensible mixing still includes
      // the incoming packet capacity. The scoped fix leaves oxygen intact.
      const branch=code.slice(code.indexOf('let vapor=woodFluxDensity(x)'),code.indexOf('}else if(s>0.&&object.options.x>.5)'));
      assert.doesNotMatch(branch,/c\.w\s*=/);
    }
  }
});

test('gas starter is a finite physical watt budget with normalized compact support',()=>{
  const dt=.2,sigma=WOOD_GAS_PILOT.sigmaLocal;
  const placement={origin:[0,1,0],scale:1};
  const [site]=woodGasPilotSites(placement);
  const capacityUnits=WOOD_FLUX.gasFuelDensityKgM3*WOOD_FLUX.gasHeatCapacityJkgK*WOOD_FLUX.gasHeatScaleK;
  const centerEnergy=woodGasPilotHeat(site.center,{...placement,dt})*capacityUnits;
  close(centerEnergy,site.powerW*dt/((2*Math.PI)**1.5*sigma**3*WOOD_GAS_PILOT.gaussianFraction));
  // Integrate the actual compact radial kernel, not an untruncated Gaussian.
  const intervals=6000,h=3*sigma/intervals;
  let integral=0;
  for(let i=0;i<=intervals;i++){
    const radius=i*h,point=[site.center[0]+radius,site.center[1],site.center[2]];
    const energy=woodGasPilotHeat(point,{...placement,dt})*capacityUnits;
    integral+=energy*4*Math.PI*radius**2*(i===0||i===intervals?1:i%2?4:2);
  }
  assert.ok(Math.abs(integral*h/3-site.powerW*dt)<.01);
  assert.equal(woodGasPilotHeat([site.center[0]+3.01*sigma,...site.center.slice(1)],{...placement,dt}),0);
  assert.equal(WOOD_GAS_PILOT.powerW*WOOD_GAS_PILOT.durationS,480000);
  assert.equal(WOOD_GAS_PILOT.allPowerW*WOOD_GAS_PILOT.durationS,640000);
  assert.equal(WOOD_GAS_PILOT.powerW*WOOD_GAS_PILOT.treeDurationS,300000);
});

test('starter stops, expires and respects real-time partitions across its finite endpoint',()=>{
  const placement={origin:[0,1,0],scale:1};const [site]=woodGasPilotSites(placement);
  assert.equal(woodGasPilotHeat(site.center,{...placement,active:false,dt:1}),0);
  assert.equal(woodGasPilotHeat(site.center,{...placement,age:-.1,dt:1}),0);
  assert.equal(woodGasPilotHeat(site.center,{...placement,age:4,dt:1}),0);
  assert.equal(woodGasPilotHeat(site.center,{...placement,age:12,dt:1}),0);
  for(const partitions of [1,3,12]){
    let total=0;const dt=4.4/(96*partitions);
    for(let i=0;i<96*partitions;i++)total+=woodGasPilotHeat(site.center,{...placement,age:i*dt,dt});
    close(total,woodGasPilotHeat(site.center,{...placement,age:0,dt:4}));
  }
  const full=woodGasPilotHeat(site.center,{...placement,age:0,dt:4});
  close(woodGasPilotHeat(site.center,{...placement,age:3.99,dt:.1}),full/400);
  const crown={origin:[0,1.9,0],tree:true,ignition:2};const [crownSite]=woodGasPilotSites(crown);
  assert.ok(woodGasPilotHeat(crownSite.center,{...crown,age:2.4,dt:.1})>0);
  assert.equal(woodGasPilotHeat(crownSite.center,{...crown,age:2.5,dt:.1}),0);
  // Relight deliberately starts a new finite external starter, not a gain.
  assert.ok(woodGasPilotHeat(site.center,{...placement,age:0,dt:.01})>0);
});

test('wood starter placements follow the bounded source and preserve the all-ignition power',()=>{
  const normal={origin:[0,.64,0],scale:1};const [log]=woodGasPilotSites(normal);
  close(log.center[1],.19);assert.ok(log.center[1]>0);
  const all=woodGasPilotSites({...normal,ignition:1});
  assert.equal(all.length,3);close(all.reduce((sum,site)=>sum+site.powerW,0),160000);
  for(const tree of [true,false])for(const ignition of [0,1,2]){
    const low=woodGasPilotSites({origin:[0,.01,0],scale:.8,tree,ignition});
    assert.ok(low.every(site=>site.center[1]>=.07));
    const shifted=woodGasPilotSites({origin:[1,.01,-.5],scale:.8,tree,ignition});
    for(let i=0;i<low.length;i++){
      close(shifted[i].center[0]-low[i].center[0],1);
      close(shifted[i].center[2]-low[i].center[2],-.5);
    }
  }
  assert.throws(()=>woodGasPilotSites({scale:0}),/Invalid wood gas pilot/);
  assert.match(surfaceWGSL,/let centre=select\(vec3f\(-\.45,-\.45,\.15\),vec3f\(-\.45,-\.30,\.69\)/);
  const [house]=woodGasPilotSites({...normal,objectId:'house'});
  assert.deepEqual(house.center,[-.45,.34,.69]);
  assert.doesNotMatch(surfaceWGSL,/let offset=local-vec3f\(-\.45,-\.85,\.15\)/);
  assert.match(surfaceWGSL,/p\.step\.z<4\.0/);
  assert.match(surfaceWGSL,/ignition=select\(280000\.\*exp/);
});

test('external pilot energy closes at dense fuel and does not acquire 12× wood acceleration',()=>{
  const placement={origin:[0,1,0],scale:1};const [site]=woodGasPilotSites(placement);
  for(const initialFuel of [0,41.875])for(const partitions of [1,3,12]){
    const dt=.6/partitions;let heat=.2,fuel=initialFuel,energy=.2*(1+initialFuel);
    for(let i=0;i<partitions;i++){
      const packet=[.3/partitions,.3*.324/partitions];
      heat=mixWoodVaporHeat(heat,fuel,packet);fuel+=packet[0];energy+=packet[1];
      const pilot=woodGasPilotHeat(site.center,{...placement,age:i*dt,dt});
      heat+=pilot/(1+fuel);energy+=pilot;
      close(heat*(1+fuel),energy);
    }
    close(energy,.2*(1+initialFuel)+.3*.324+woodGasPilotHeat(site.center,{...placement,dt:.6}));
  }
  const shaders=simulationShaders(128,256);
  assert.match(shaders.correctScalar,/c\.y\+=woodGasPilotHeat\(x,p\.step\.z,p\.step\.x,p\.source\.w\)\/\(1\.\+c\.z\)/);
  assert.match(shaders.buildBricks,/woodGasPilotLive\(at,halfBrick,p\.step\.z,p\.step\.x,p\.source\.w\)/);
  assert.match(woodFluxWGSL,/let near=max\(abs\(world-woodGasPilotCenter\(site\)\)-vec3f\(halfBrick\),vec3f\(0\)\)/);
  assert.doesNotMatch(woodFluxWGSL,/seconds\s*\*\s*(12|object\.options\.z)/);
});


test('frame-cadence solid packets preserve gas mass, energy and integrated pressure expansion',()=>{
 const frameDt=1/60,packet=[.8,.21],initialFuel=2,initialHeat=.7;
 const words=new Uint32Array([80000000,0,0,0,0,0]);
 for(const fractions of [[1],[.5,.5],[.1,.2,.3,.4],Array(12).fill(1/12)]){
  let fuel=initialFuel,heat=initialHeat,expansion=0,weight=0;
  for(const fraction of fractions){
   const dt=frameDt*fraction,w=woodPacketFraction(dt,frameDt);weight+=w;
   heat=mixWoodVaporHeat(heat,fuel,packet.map(x=>x*w));fuel+=packet[0]*w;
   expansion+=woodFluxVolumeSource(words,dt)*w*dt;
  }
  close(weight,1);close(fuel,initialFuel+packet[0]);
  close(heat*(1+fuel),initialHeat*(1+initialFuel)+packet[1]);
  close(expansion,woodFluxVolumeSource(words,frameDt)*frameDt);
 }
 for(const args of [[0,frameDt],[-1,frameDt],[NaN,frameDt],[1,0],[frameDt*2,frameDt]])
  assert.throws(()=>woodPacketFraction(...args),/partition/);
 const shaders=simulationShaders(128,256,{woodCadence:true,hasPowers:false});
 assert.match(shaders.correctScalar,/return woodPacket.x\*woodFluxDensity\(world\)/);
 assert.match(shaders.correctScalar,/let fuelAfterSources=c.z/);
 assert.match(shaders.correctVelocity,/completedVolumeSourceAt\(x,N\)/);
});
