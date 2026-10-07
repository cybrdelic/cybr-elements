import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const root = resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const { WOOD_THERMO, advanceWood, woodHeatCapacity, woodConductivity, woodPyrolysisRate,
  gasHeatToWoodHeat, woodHeatToGasHeat, woodThermoWGSL, woodThermoGLSL } =
  await import(pathToFileURL(resolve(root, 'wood-thermo.js')).href);
const { surfaceWGSL, basicSurfaceWGSL, damageResetWGSL, woodStateWGSL, objectWGSL } =
  await import(pathToFileURL(resolve(root, 'pyro-gpu/objects.js')).href);

const fresh = moisture => ({stock: [1, 0, 0, 0], wear: [moisture ?? WOOD_THERMO.dryMoistureFraction, 0, 0, 1]});
test('char shields externally imposed starter heat instead of amplifying it',()=>{
 const common={wear:[0,0,0,1],incomingHeat:0,dt:1/60,ignite:280000,oxygen:0,cellSize:.15,timeScale:12};
 const bare=advanceWood({...common,stock:[1,0,0,0]}),charred=advanceWood({...common,stock:[.8,0,0,.2]});
 assert.ok(charred.stock[1]<bare.stock[1]);
 assert.ok(charred.stock[1]<.1);
});
function run({seconds = 2, partitions = 1, moisture, gasHeat = 1, starterSeconds = 1,
  oxygen = .8, timeScale = 12, initial} = {}) {
  let state = initial ?? fresh(moisture), vapor = 0, oxidation = 0, water = 0;
  const count = Math.round(seconds * 60 * partitions), dt = 1 / (60 * partitions);
  let smallestVirgin = 1, biggestHeat = 0, lastCrack = state.wear[2], lastStiffness = state.wear[3];
  for (let i = 0; i < count; i++) {
    const next = advanceWood({...state, incomingHeat: gasHeatToWoodHeat(gasHeat), dt,
      ignite: i * dt < starterSeconds ? WOOD_THERMO.starterFluxWm2 : 0,
      oxygen, timeScale});
    assert.ok([...next.stock, ...next.wear].every(Number.isFinite));
    assert.ok(next.stock[0] >= 0 && next.stock[3] >= 0 && next.wear[0] >= 0);
    assert.ok(next.stock[2] >= 0 && next.volatileMass >= 0 && next.oxidizedMass >= 0);
    assert.ok(next.wear[2] + 1e-12 >= lastCrack, 'cracks are irreversible');
    assert.ok(next.wear[3] <= lastStiffness + 1e-12, 'irreversible section damage cannot heal on a clock');
    lastCrack = next.wear[2]; lastStiffness = next.wear[3];
    smallestVirgin = Math.min(smallestVirgin, next.stock[0]); biggestHeat = Math.max(biggestHeat, next.stock[1]);
    vapor += next.volatileMass; oxidation += next.oxidizedMass; water += next.evaporatedMass;
    state = {stock: next.stock, wear: next.wear};
  }
  return {...state, vapor, oxidation, water, smallestVirgin, biggestHeat};
}

test('temperature conversions preserve absolute Kelvin without altering gas emission units', () => {
  for (const heat of [0, .4, 1, 2.5, 8]) {
    const wood = gasHeatToWoodHeat(heat);
    assert.ok(Math.abs(293.15 + 500 * wood - (300 + 1200 * heat)) < 1e-10);
    assert.ok(Math.abs(woodHeatToGasHeat(wood) - heat) < 1e-12);
  }
  assert.equal(WOOD_THERMO.gasFuelDensityKgM3, 1);
  assert.equal(WOOD_THERMO.dryDensityKgM3, 495);
  assert.ok(woodHeatCapacity(293.15) > 1000 && woodHeatCapacity(293.15) < 2500);
  assert.ok(woodPyrolysisRate(700).rate > woodPyrolysisRate(500).rate);
});

test('cold unignited wood stays intact and does not generate fuel or fake char', () => {
  const cold = run({seconds: 60, starterSeconds: 0, gasHeat: 0});
  assert.equal(cold.stock[0], 1);
  assert.equal(cold.stock[3], 0);
  assert.equal(cold.vapor, 0);
  assert.equal(cold.oxidation, 0);
  assert.equal(cold.wear[2], 0);
  assert.equal(cold.wear[3], 1);
});

test('wood-to-vapor/char and char-to-products close the dry mass ledger', () => {
  for (const partitions of [1, 2, 3, 12]) {
    const result = run({seconds: 6, partitions});
    const dryMass = result.stock[0] + result.stock[3] + result.vapor + result.oxidation;
    assert.ok(Math.abs(dryMass - 1) < 1e-10, `dry mass closes for ${partitions} substeps`);
    assert.ok(Math.abs(result.wear[0] + result.water - WOOD_THERMO.dryMoistureFraction) < 1e-10);
    assert.ok(result.vapor > .1 && result.stock[3] > 0);
    assert.notEqual(result.stock[3], 1 - result.stock[0], 'char is a separate retained stock, not a conversion mask');
  }
});

test('drying absorbs heat and damp fuel delays conversion under matched flux', () => {
  const dry = run({moisture: WOOD_THERMO.dryMoistureFraction});
  const damp = run({moisture: WOOD_THERMO.dampMoistureFraction});
  assert.ok(damp.stock[0] > dry.stock[0], 'wet stock must lose less virgin mass');
  assert.ok(damp.vapor < dry.vapor);
  assert.ok(damp.water > dry.water, 'stored moisture actually evaporates');
  assert.ok(dry.stock[1] > dry.wear[1] && dry.wear[1] > 0, 'surface and core retain a thermal gradient');
});

test('hot wood continues pyrolysis without the starter and char oxidation respects oxygen', () => {
  const hot = run({seconds: .5, starterSeconds: 0, gasHeat: 1,
    initial: {stock: [1, 1.4, 0, 0], wear: [0, 1.1, 0, 1]}});
  assert.ok(hot.vapor > 0 && hot.stock[0] < 1);
  const carbon = {stock: [0, 1.8, 0, .25], wear: [0, 1.5, .5, .1]};
  const inert = run({seconds: 2, starterSeconds: 0, oxygen: 0, initial: carbon});
  const oxygenated = run({seconds: 2, starterSeconds: 0, oxygen: 1, initial: carbon});
  assert.equal(inert.oxidation, 0);
  assert.equal(inert.stock[3], .25);
  assert.ok(oxygenated.oxidation > 0 && oxygenated.stock[3] < .25);
  assert.equal(oxygenated.vapor, 0, 'char oxidation products must never be fed back as combustible vapor');
});

test('finer CFL partitions retain mass and approach the same thermal/conversion state', () => {
  const base = run({partitions: 1});
  for (const partitions of [2, 3, 12]) {
    const fine = run({partitions});
    assert.ok(Math.abs(fine.stock[0] - base.stock[0]) < .002);
    assert.ok(Math.abs(fine.stock[3] - base.stock[3]) < .002);
    assert.ok(Math.abs(fine.stock[1] - base.stock[1]) < .02);
    assert.ok(Math.abs(fine.vapor - base.vapor) < .002);
  }
  const paused = advanceWood({...fresh(), incomingHeat: 3, ignite: 280000, dt: 0});
  assert.deepEqual(paused.stock, [1, 0, 0, 0]);
  assert.deepEqual(paused.wear, fresh().wear);
});

test('char insulation reduces boundary heating and disabled acceleration does no chemistry', () => {
  assert.ok(woodConductivity(293.15, 1) < woodConductivity(293.15, 0));
  const bare = advanceWood({stock: [.7, 0, 0, 0], wear: [0, 0, 0, 1], incomingHeat: 2,
    dt: 1 / 60, oxygen: 0});
  const coated = advanceWood({stock: [.7, 0, 0, .2], wear: [0, 0, 0, 1], incomingHeat: 2,
    dt: 1 / 60, oxygen: 0});
  assert.ok(coated.stock[1] < bare.stock[1]);
  const disabled = advanceWood({...fresh(), incomingHeat: 2, ignite: 280000, dt: 1, timeScale: 0});
  assert.deepEqual(disabled.stock, [1, 0, 0, 0]);
  assert.equal(disabled.volatileMass, 0);
});

test('production Volume kernel has F32 persistent interiors and starter-only activity gating', () => {
  assert.equal(basicSurfaceWGSL, surfaceWGSL);
  assert.match(surfaceWGSL, /next:texture_storage_3d<rgba32float,write>/);
  assert.match(surfaceWGSL, /nextDamage:texture_storage_3d<rgba32float,write>/);
  assert.match(surfaceWGSL, /mat\.x<=0\./, 'solid interior cells are active');
  assert.match(surfaceWGSL, /woodThermoStep\(state,wear,incoming,p\.step\.x,ignition,oxygen/);
  assert.match(surfaceWGSL, /conduction=sum\/max\(heatCapacity/);
  assert.match(surfaceWGSL, /woodNodes\[owner\]\.axisRadius\.xyz/, 'conduction follows the authored branch grain');
  assert.match(surfaceWGSL, /2\.\*kFace\*otherFace\/max\(kFace\+otherFace/, 'both grains share one harmonic face conductance');
  assert.match(surfaceWGSL, /woodPiece\(owner\)!=woodPiece\(otherOwner\)/, 'separated pieces have no ghost thermal bridge');
  assert.equal((surfaceWGSL.match(/p\.source\.w/g) || []).length, 1, 'only the starter depends on source activity');
  assert.doesNotMatch(surfaceWGSL, /state\.w=1\.-state\.x/);
  assert.match(damageResetWGSL, /vec4f\(moisture,0,0,1\)/);
});

test('shared shader helpers preserve F32 manual access and generate complete GLSL syntax', () => {
  assert.match(objectWGSL, /surfaceState.*woodTrilinear\(skin/);
  assert.match(objectWGSL, /surfaceWear.*woodTrilinear\(damage/);
  assert.match(woodStateWGSL, /textureLoad\(field,at,0\)/);
  assert.doesNotMatch(woodStateWGSL, /textureSample|binding/);
  assert.match(woodThermoWGSL, /let consumed:f32=s\.x-nextVirgin/);
  assert.match(woodThermoWGSL, /candidateGain<=consumed/);
  assert.match(woodThermoGLSL, /vec2 woodPyro\(float T\)/);
  assert.match(woodThermoGLSL, /void woodThermoStep\(/);
  assert.doesNotMatch(woodThermoGLSL, /\bfn\b|\blet\b|\bvar\b|->|:f32|vec[234]f|undefined/);
});
