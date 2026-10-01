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

const ids = ['radial-blast', 'fireball', 'fire-rain', 'fire-tornado', 'floor-trail', 'combustion-bomb'];
const powers = ALL_FIRE_PRESETS.filter(p => p.family === 'Powers');

test('all six live powers are available in the ordinary source menu of both engines', () => {
  assert.equal(powers.length, 12);
  for (const engine of ['legacy', 'volume', 'sparse']) {
    const group = sourceGroups(engine).find(p => p.label === 'Powers');
    assert.ok(group, engine);
    assert.deepEqual(group.options.map(p => p.value), ids);
  }
  for (const [index, id] of ids.entries()) {
    const volume = FIRE_PRESETS.find(p => p.id === id);
    const original = LEGACY_PRESETS.find(p => p.id === 'legacy:' + id);
    assert.ok(volume && original, id);
    assert.equal(volume.effect[0], 22 + index);
    assert.equal(volume.power, id);
    assert.equal(original.power, id);
    assert.equal(emitterKindFor(volume), 22 + index);
    assert.equal(original.name, volume.name);
    assert.equal(isExperimental(volume), false);
    assert.equal(isExperimental(original), false);
    assert.equal(volume.object, undefined);
    assert.equal(volume.preview, undefined);
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

test('the power library filters and applies within the chosen simulation', () => {
  for (const simulation of ['legacy', 'volume', 'sparse']) {
    const items = filterLibrary(powers, '', simulation, 'bonfire', 'volume');
    assert.equal(items.length, 6);
    assert.deepEqual(items.map(p => p.id.replace(/^legacy:/, '')), ids);
    for (const item of items)
      assert.equal(libraryItemSimulation(item, simulation, 'bonfire', 'volume'), simulation);
  }
  const blasts = filterLibrary(powers, 'radial blast', 'all');
  assert.equal(blasts.length, 2);
  assert.ok(blasts.every(p => p.id.replace(/^legacy:/, '') === 'radial-blast'));
});
