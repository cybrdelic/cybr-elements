import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {advanceFloorWood,floorFuelUpdateWGSL,floorFuelClearWGSL,
  floorWoodWearClearWGSL}=await import(pathToFileURL(resolve(root,'pyro-gpu/floor-fuel.js')).href);
const {WOOD_THERMO}=await import(pathToFileURL(resolve(root,'wood-thermo.js')).href);
function run({partitions=1,seconds=6,gasHeat=1,starterSeconds=1/60,timeScale=12,
  smokeOnly=false,initial,deposit=1.5}={}){
  let state=initial||{stock:[0,0,0,0],wear:[0,0,0,0]},vapor=0,oxidized=0,water=0,accepted=0;
  const dt=1/(60*partitions),n=Math.round(seconds/dt);let maximumHeat=0,first;
  for(let i=0;i<n;i++){
    const next=advanceFloorWood({...state,deposit:i===0?deposit:0,dt,
      incomingGasHeat:gasHeat,ignite:i*dt<starterSeconds,smokeOnly,timeScale});
    assert.ok([...next.stock,...next.wear].every(Number.isFinite));
    assert.ok(next.stock[0]>=0&&next.stock[3]>=0&&next.stock[2]>=0);
    assert.ok(next.wear[0]>=0&&next.wear[1]>=0);
    assert.ok(next.wear[3]+1e-12>=state.wear[3]);
    vapor+=next.volatileKgM2;oxidized+=next.oxidizedKgM2;water+=next.waterKgM2;accepted+=next.acceptedDeposit;
    maximumHeat=Math.max(maximumHeat,next.stock[1]);state={stock:next.stock,wear:next.wear};first??=next;
  }
  return {...state,vapor,oxidized,water,accepted,maximumHeat,first};
}

test('cold wood stays near ambient with only the fitted low-temperature kinetic tail',()=>{
  const cold=run({seconds:30,gasHeat:0,starterSeconds:0});
  // The calibrated Arrhenius rate is not a hard ignition threshold. A thin
  // bed exposes its tiny300K tail, which thick F32 voxels may round away.
  // Require a closed, negligible ledger, not an invented zero-rate cutoff.
  assert.ok(1.5-cold.stock[0]<1.5*.0002);
  assert.ok(cold.vapor<1.5*.0002);
  assert.ok(Math.abs(cold.stock[0]+cold.stock[3]+cold.vapor+cold.oxidized-1.5)<2e-6);
  assert.ok(cold.maximumHeat<.001,'no thermal fire rise without heat input');
  assert.equal(cold.wear[0],1.5);assert.equal(cold.wear[3],0);
  assert.ok(cold.first.stock[1]<0,'cold wood surface remains below the300K gas origin');
  assert.ok(300+1200*cold.first.stock[1]>=293.15);
});
test('finite wood dry mass and retained water close independently over multiple CFL partitions',()=>{
  for(const partitions of [1,2,3,12]){
    const result=run({partitions,seconds:8});
    const dry=result.stock[0]+result.stock[3]+result.vapor+result.oxidized;
    assert.ok(Math.abs(dry-result.accepted)<2e-6,`dry ledger ${partitions}: ${dry}`);
    const water=result.wear[0]*result.wear[1]+result.water;
    assert.ok(Math.abs(water-result.accepted*WOOD_THERMO.dryMoistureFraction)<2e-7);
    assert.ok(result.vapor>0);assert.ok(result.stock[3]>0);
    assert.notEqual(result.stock[3],result.accepted-result.stock[0],'char is retained mass, not consumed fuel');
  }
});
test('hot finite wood continues releasing gas after a single explicit thermal starter',()=>{
  const first=advanceFloorWood({deposit:1.5,dt:1/60,ignite:true,incomingGasHeat:0});
  assert.ok(first.stock[1]>0,'starter supplies sensible heat to the bed');
  const next=advanceFloorWood({stock:first.stock,wear:first.wear,dt:1/60,ignite:false,incomingGasHeat:1});
  assert.ok(next.volatileKgM2>0,'hot solid uses retained/gas heat after ignition ends');
  assert.ok(next.stock[0]<first.stock[0]);
  assert.equal(next.acceptedDeposit,0);
});
test('adding cold wood conserves capacity/moisture while cooling both thermal nodes',()=>{
  const old={stock:[.4,.8,0,.1],wear:[1,.03,.9,.4]};
  const next=advanceFloorWood({...old,deposit:.8,dt:0});
  assert.equal(next.wear[0],1.8);
  assert.ok(Math.abs(next.stock[0]-1.2)<1e-12);assert.ok(Math.abs(next.stock[3]-.1)<1e-12);
  assert.ok(next.stock[1]<old.stock[1]&&next.wear[2]<old.wear[2]);
  assert.ok(Math.abs(next.wear[1]*1.8-(.03+.8*WOOD_THERMO.dryMoistureFraction))<1e-12);
  assert.equal(next.wear[3],old.wear[3]);
  const saturated=advanceFloorWood({stock:[3.9,0,0,0],wear:[3.9,0,0,0],deposit:1,dt:0});
  assert.ok(Math.abs(saturated.acceptedDeposit-.1)<1e-12);assert.equal(saturated.stock[0],4);
});
test('smoke-only operation cannot use starter or burn floor stock',()=>{
  const result=run({seconds:1,gasHeat:2,smokeOnly:true});
  assert.equal(result.stock[0],1.5);assert.equal(result.stock[3],0);assert.equal(result.vapor,0);
  assert.equal(result.maximumHeat,0);assert.equal(result.wear[2],0);
});
test('floor wood uses actual shared WGSL and retains the liquid branch within baseline WebGPU limits',()=>{
  assert.match(floorFuelUpdateWGSL,/fn woodThermoStep\(/);
  assert.match(floorFuelUpdateWGSL,/p\.lifecycle\.y>\.5/);
  assert.match(floorFuelUpdateWGSL,/@binding\(6\) var previousWear:texture_2d/);
  assert.match(floorFuelUpdateWGSL,/@binding\(7\) var nextWear:texture_storage_2d<rgba32float/);
  assert.match(floorFuelUpdateWGSL,/let surfaceGas=\(293\.15\+500\.\*result\.stock\.y-300\.\)\/1200\./);
  assert.match(floorFuelUpdateWGSL,/smoothstep\(\.32,\.65,heat\)\*1\.3\*dt/);
  assert.match(floorFuelUpdateWGSL,/min\(4\.,old\.w\+burned\)/);
  for(const code of [floorFuelUpdateWGSL,floorFuelClearWGSL,floorWoodWearClearWGSL]){
    assert.ok((code.match(/texture_storage_2d/g)||[]).length<=4,'each stage stays within baseline storage limits');
  }
});
