import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load = file => import(pathToFileURL(resolve(root, file)).href);
const { FIRE_PRESETS, LEGACY_PRESETS, ALL_FIRE_PRESETS } = await load('pyro-gpu/presets.js');
const { sourceGroups } = await load('source-picker.js');
const { matchingPreset } = await load('preset-pairs.js');
const { isExperimental } = await load('demo-presets.js');
const { filterLibrary, libraryItemSimulation } = await load('pyro-gpu/library.js');
const { cleanLook } = await load('look-storage.js');
const { emitterKindFor } = await load('original-source-profile.js');
const { POWER_DEFINITIONS, powerExpansion } = await load('fire-power-definitions.js');
const { powerSourceWGSL, powerSourceFor } = await load('fire-powers.js');
const powerSourceGLSL=powerSourceFor(null,'glsl');
const { PowerCastPool } = await load('fire-abilities.js');

const ids = ['radial-blast', 'fireball', 'fire-rain', 'fire-tornado', 'floor-trail', 'combustion-bomb',
  'flame-dash', 'flame-whip', 'ember-orbit', 'heat-seeker', 'phoenix-dive', 'dragon-breath',
  'solar-lance', 'flame-wall', 'inferno-ring', 'meteor-strike', 'meteor-barrage', 'eruption-chain',
  'combustion-mine', 'vortex-burst', 'flame-serpent', 'cinder-scatter', 'fire-cross', 'flame-crescent'];
const powers = ALL_FIRE_PRESETS.filter(p => p.family === 'Powers');

test('every authored ability is available in the ordinary source menu of both engines', () => {
  assert.deepEqual(POWER_DEFINITIONS.map(p => p.id), ids);
  assert.equal(powers.length, ids.length * 2);
  for (const engine of ['legacy', 'volume', 'sparse']) {
    const group = sourceGroups(engine).find(p => p.label === 'Powers');
    assert.ok(group, engine);
    assert.deepEqual(group.options.map(p => p.value), ids);
  }
  for (const [index, id] of ids.entries()) {
    const volume = FIRE_PRESETS.find(p => p.id === id);
    const original = LEGACY_PRESETS.find(p => p.id === 'legacy:' + id);
    const definition = POWER_DEFINITIONS.find(p => p.id === id);
    assert.ok(volume && original, id);
    assert.equal(volume.effect[0], 22 + index);
    assert.equal(volume.effect[0], definition.kind + 21);
    assert.equal(volume.effect[2], definition.duration, id + ' lifetime');
    assert.equal(volume.effect[3], Number(definition.continuous), id + ' sustain');
    assert.equal(volume.power, id);
    assert.equal(original.power, id);
    assert.equal(emitterKindFor(volume), 22 + index);
    assert.equal(original.name, volume.name);
    assert.equal(isExperimental(volume), false);
    assert.equal(isExperimental(original), false);
    assert.equal(volume.object, undefined);
    assert.equal(volume.preview, undefined);
    assert.ok(volume.abilityGroup, id + ' movement group');
    assert.ok(['gas', 'oil'].includes(volume.fuel), id);
    for (const parameter of [...volume.effect, ...volume.dynamics, ...volume.chemistry, ...volume.source])
      assert.ok(Number.isFinite(parameter), id);
  }
});

test('powers remain the same authored effect when changing engine or saving a look', () => {
  for (const id of ids) {
    assert.equal(matchingPreset('legacy', id), 'legacy:' + id);
    assert.equal(matchingPreset('volume', 'legacy:' + id), id);
    assert.equal(matchingPreset('sparse', 'legacy:' + id), id);
    for (const simulation of ['legacy', 'volume', 'sparse']) {
      const fire = simulation === 'legacy' ? 'legacy:' + id : id;
      const saved = cleanLook({ name: id, fire, simulation, room: true }, ALL_FIRE_PRESETS);
      assert.equal(saved?.fire, fire);
      assert.equal(saved?.simulation, simulation);
    }
  }
});

test('the power library filters movement groups and applies within the chosen simulation', () => {
  for (const simulation of ['legacy', 'volume', 'sparse']) {
    const items = filterLibrary(powers, '', simulation, 'bonfire', 'volume');
    assert.equal(items.length, ids.length);
    assert.deepEqual(items.map(p => p.id.replace(/^legacy:/, '')), ids);
    for (const item of items)
      assert.equal(libraryItemSimulation(item, simulation, 'bonfire', 'volume'), simulation);
  }
  const blasts = filterLibrary(powers, 'radial blast', 'all');
  assert.equal(blasts.length, 2);
  assert.ok(blasts.every(p => p.id.replace(/^legacy:/, '') === 'radial-blast'));
  const projectiles = filterLibrary(powers, 'projectiles', 'volume');
  assert.ok(projectiles.some(p => p.id === 'ember-orbit'));
  assert.ok(projectiles.some(p => p.id === 'heat-seeker'));
  assert.ok(projectiles.every(p => p.abilityGroup === 'Projectiles'));
  const terrain = filterLibrary(powers, 'terrain', 'legacy');
  assert.ok(terrain.some(p => p.id === 'legacy:fire-cross'));
  assert.ok(terrain.some(p => p.id === 'legacy:floor-trail'));
});

test('finite cast metadata protects late impulses and expires with the authored recovery', () => {
  for (const definition of POWER_DEFINITIONS.filter(p => !p.continuous)) {
    assert.ok(definition.duration > definition.windup, definition.id);
    let previous = 0;
    for (const phase of definition.phases) {
      assert.ok(phase.until > previous && phase.until <= definition.duration, definition.id);
      previous = phase.until;
    }
    assert.equal(previous, definition.duration, definition.id + ' final phase');
    for (const impulse of definition.impulses) {
      const pool = new PowerCastPool();
      pool.cast(definition, {origin:[0,.8,0], direction:[1,0,0], strength:2, scale:1.25});
      pool.step(Math.max(0, impulse.at - .001));
      assert.equal(pool.crossesImpulse(.002), true, definition.id + ' ' + impulse.at);
      assert.ok(pool.speedFloor(.002) >= definition.maxSpeed * Math.sqrt(2) * 1.25,
        definition.id + ' pre-telemetry speed');
      pool.step(definition.duration + .01);
      assert.equal(pool.snapshot().active, 0, definition.id + ' finite recovery');
      assert.equal(pool.expansion(), 0);
      assert.equal(pool.crossesImpulse(10), false);
    }
  }
});

function scalarShaderFunction(source, name) {
  const begin = source.indexOf(name + '(');
  assert.ok(begin >= 0, name);
  const open = source.indexOf('{', begin);
  let nesting = 1, end = open + 1;
  for (; nesting && end < source.length; end++) {
    if (source[end] === '{') nesting++;
    if (source[end] === '}') nesting--;
  }
  assert.equal(nesting, 0);
  // This generated function contains scalar comparisons and returns only.
  // Evaluate its actual shipped conditions independently of the JS registry.
  return new Function('kind', 'age', source.slice(open + 1, end - 1));
}

test('Original and Volume expansion shaders match every authored blast-window boundary', () => {
  const sampleWGSL = scalarShaderFunction(powerSourceWGSL, 'powerCastExpansion');
  const sampleGLSL = scalarShaderFunction(powerSourceGLSL, 'powerCastExpansion');
  for (const definition of POWER_DEFINITIONS) {
    const times = [-1, 0, definition.windup, definition.duration + .01,
      ...definition.blastWindows.flatMap(w => [w.from-.0001, w.from, (w.from+w.until)/2, w.until, w.until+.0001])];
    for (const age of times) {
      const expected = powerExpansion(definition, age);
      assert.equal(sampleWGSL(definition.kind, age), expected, definition.id + ' WGSL ' + age);
      assert.equal(sampleGLSL(definition.kind, age), expected, definition.id + ' GLSL ' + age);
    }
  }
  const pool = new PowerCastPool();
  const actor = pool.cast('fireball', {
    origin:[-2.84,.35,-2.84], target:[2.84,5.76,2.84], direction:[1,0,0], strength:1,
  });
  const range = Math.hypot(...actor.target.map((x,i) => x-actor.origin[i]));
  assert.ok(range <= actor.definition.range + 1e-12, 'explicit aim retains authored travel range');
  pool.step(.7);
  const velocity = actor.target.map((x,i) => (x-actor.origin[i]-(i===1?.4:0))/.65);
  velocity[1] += .28*Math.PI*Math.cos((actor.age-.22)/.65*Math.PI)/.65;
  assert.ok(Math.hypot(...velocity) <= pool.speedFloor(), 'late fireball flight remains inside the predicted bound');
});
