import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load = file => import(pathToFileURL(resolve(root, file)).href);
const { readLook, writeLook } = await load('studio-location.js');
const { cleanLook, lookStore } = await load('look-storage.js');
const { ALL_FIRE_PRESETS, FIRE_PRESETS } = await load('pyro-gpu/presets.js');
const { POWER_DEFINITIONS, powerDefinition, normalizePowerSettings } = await load('fire-powers.js');
const { matchingPreset } = await load('preset-pairs.js');
const { runtimeFamily } = await load('simulation-modes.js');
const studio = readFileSync(resolve(root, 'studio.js'), 'utf8');

// Run the actual shell closures without loading an app or GPU device. Only
// their DOM/runtime dependencies are supplied by the fixture.
function shellFunction(name) {
  const match = new RegExp(`^function ${name}\\(`, 'm').exec(studio);
  assert.ok(match, 'production shell function ' + name);
  const open = studio.indexOf('{', match.index);
  let depth = 0, quote = null, comment = null;
  for (let i = open; i < studio.length; i++) {
    const c = studio[i], next = studio[i + 1];
    if (comment === 'line') { if (c === '\n') comment = null; continue; }
    if (comment === 'block') { if (c === '*' && next === '/') { comment = null; i++; } continue; }
    if (quote) { if (c === '\\') i++; else if (c === quote) quote = null; continue; }
    if (c === '/' && next === '/') { comment = 'line'; i++; continue; }
    if (c === '/' && next === '*') { comment = 'block'; i++; continue; }
    if (c === '"' || c === "'" || c === '`') { quote = c; continue; }
    if (c === '{') depth++;
    if (c === '}' && --depth === 0) return studio.slice(match.index, i + 1);
  }
  throw Error('Unterminated shell function ' + name);
}

test('shared power links round-trip strength and aim without changing lighting or camera', () => {
  const powers = { strength: 1.6, heading: -72, elevation: 36 };
  const camera = { zoom: 2.1, angle: 48, pan: [.3, -.8] };
  for (const definition of POWER_DEFINITIONS) for (const simulation of ['legacy', 'volume', 'sparse']) {
    const fire = simulation === 'legacy' ? 'legacy:' + definition.id : definition.id;
    const url = writeLook(new URL('https://example.com/firesim/?qa=1&lightWork=1'), {
      fire, simulation, powers, camera, fuel: 'gas', room: true,
      lights: { ambient: .8, key: 80, keyColor: '#eeddcc' }, fireLight: 12,
    });
    assert.equal(url.searchParams.get('simulation'), simulation);
    assert.equal(url.searchParams.get(simulation === 'legacy' ? 'preset' : 'firePreset'), definition.id);
    assert.equal(url.searchParams.get('qa'), '1');
    assert.equal(url.searchParams.get('lightWork'), '1');
    const restored = readLook(url.searchParams, { zoom: 1, angle: 16, pan: [0, 0] });
    assert.deepEqual(restored.powers, powers);
    assert.deepEqual(restored.camera, camera);
    assert.deepEqual(restored.lights, { ambient: .8, key: 80, keyColor: '#eeddcc' });
    assert.equal(restored.fireLight, 12);
  }
});

test('malformed power link parameters are bounded and do not synthesize a camera change', () => {
  const look = readLook(new URLSearchParams('powerStrength=Infinity&powerHeading=9999&powerElevation=-9999'),
    { zoom: 1.7, angle: 35, pan: [.1, -.2] });
  assert.deepEqual(look.powers, { strength: 1, heading: 180, elevation: -30 });
  assert.equal(look.camera, undefined);
  assert.deepEqual(readLook(new URLSearchParams('powerStrength=&powerHeading=garbage&powerElevation=0')).powers,
    { strength: 1, heading: 0, elevation: 0 });
  const url = writeLook(new URL('https://example.com/firesim/?powerStrength=2&powerHeading=40&powerElevation=20'),
    { fire: 'bonfire', simulation: 'volume', fuel: 'wood', room: true });
  for (const key of ['powerStrength', 'powerHeading', 'powerElevation'])
    assert.equal(url.searchParams.get(key), null, 'stale power setting ' + key);
});

test('saved power looks export and import aim with independent camera and settings copies', () => {
  const data = new Map();
  const storage = { getItem: key => data.get(key), setItem: (key, value) => data.set(key, value) };
  const store = lookStore(storage, ALL_FIRE_PRESETS);
  store.add({ name: 'Aimed fireball', fire: 'legacy:fireball', simulation: 'legacy',
    powers: { strength: 1.4, heading: 22, elevation: 15 }, camera: { zoom: 1.8, angle: 40, pan: [.2, -.3] } });
  const copied = store.export();
  copied.looks[0].powers.heading = -150;
  copied.looks[0].camera.pan[0] = 5;
  assert.equal(store.items[0].powers.heading, 22);
  assert.equal(store.items[0].camera.pan[0], .2);
  const imported = lookStore(storage, ALL_FIRE_PRESETS);
  assert.equal(imported.import(store.export()), 1);
  assert.deepEqual(imported.items[1].powers, store.items[0].powers);
  assert.deepEqual(imported.items[1].camera, store.items[0].camera);
  assert.deepEqual(cleanLook({ name: 'Old save', fire: 'bonfire' }, ALL_FIRE_PRESETS).powers,
    { strength: 1, heading: 0, elevation: 9 });
});

test('production power controls show only relevant aim fields and update powers alone', () => {
  const elements = new Map();
  const $ = id => {
    if (!elements.has(id)) elements.set(id, { value: '', hidden: false, textContent: '' });
    return elements.get(id);
  };
  const calls = [], state = { powers: { strength: 1.25, heading: -45, elevation: 30 } };
  const runtime = {
    snapshot: () => ({ powers: { ...state.powers } }),
    look: item => { calls.push(item);state.powers = normalizePowerSettings(item.powers); },
  };
  const sync = new Function('$', 'runtime', 'powerDefinition', 'normalizePowerSettings',
    shellFunction('syncPowerControls') + ';return syncPowerControls;')($, runtime, powerDefinition, normalizePowerSettings);
  const floorHeading = new Set(['flame-dash', 'eruption-chain', 'fire-cross', 'flame-wall',
    'phoenix-dive', 'meteor-strike', 'meteor-barrage']);
  for (const definition of POWER_DEFINITIONS) for (const prefix of ['', 'legacy:']) {
    $('#preset').value = prefix + definition.id;sync();
    assert.equal($('#power-controls').hidden, false);
    assert.equal($('#power-aim-fields').hidden,
      !(['aim', 'projectile'].includes(definition.targetMode) || floorHeading.has(definition.id)), definition.id);
    assert.equal($('#power-elevation-field').hidden, definition.floor, definition.id);
    assert.equal($('#power-description').textContent, definition.hint);
  }
  $('#power-strength').value = '175';$('#power-heading').value = '36';$('#power-elevation').value = '20';
  $('#power-strength').oninput();
  assert.deepEqual(calls, [{ powers: { strength: 1.75, heading: 36, elevation: 20 } }]);
  assert.equal($('#power-strength-value').textContent, '175%');
  assert.equal($('#power-heading-value').textContent, '36°');
  $('#preset').value = 'bonfire';sync();
  assert.equal($('#power-controls').hidden, true);
});

test('production simulation transitions preserve power aim while respecting each engine camera', () => {
  const remembered = new Map(), camera = { zoom: 1.8, angle: 22, pan: [.2, -.5] };
  const volumeCamera = { zoom: 1.25, angle: 16, pan: [0, 0] };
  remembered.set('volume', { fire: 'fireball', camera: volumeCamera, embers: true });
  const create = new Function('engine', 'remembered', 'matchingPreset', 'runtimeFamily', 'powerDefinition', 'normalizePowerSettings',
    shellFunction('transitionLook') + ';return transitionLook;');
  const old = { fire: 'legacy:fireball', powers: { strength: 1.5, heading: 60, elevation: 18 },
    camera, fuel: 'gas', room: true, tool: 'pan', fireLight: 24 };
  const chosen = FIRE_PRESETS.find(p => p.id === 'fireball');
  const cross = create('legacy', remembered, matchingPreset, runtimeFamily, powerDefinition, normalizePowerSettings)('volume', chosen, old, false);
  assert.deepEqual(cross.powers, old.powers);
  assert.deepEqual(cross.camera, volumeCamera);
  const same = create('volume', remembered, matchingPreset, runtimeFamily, powerDefinition, normalizePowerSettings)('sparse', chosen,
    { ...old, fire: 'fireball' }, false);
  assert.deepEqual(same.powers, old.powers);
  assert.deepEqual(same.camera, camera);
  assert.equal(same.tool, 'pan');
  const wall = FIRE_PRESETS.find(p=>p.id==='flame-wall');
  const next = create('volume', remembered, matchingPreset, runtimeFamily, powerDefinition, normalizePowerSettings)('volume',wall,{...old,fire:'fireball'},false);
  assert.deepEqual(next.powers,{strength:1.5,heading:90,elevation:9});
});
