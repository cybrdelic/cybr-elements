import test from 'node:test';
import assert from 'node:assert/strict';
import { cleanLights, cleanLook, lookStore } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/look-storage.js';
import { readLook, writeLook } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/studio-location.js';
import { sourceGroups } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/source-picker.js';
import { filterLibrary } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/library.js';
import { ALL_FIRE_PRESETS, FIRE_PRESETS, LEGACY_PRESETS } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/presets.js';
import { studioUI } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/studio-ui.js';
import { DEMO_PRESETS } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/demo-presets.js';

test('demo scenes explicitly reset fuel, color, smoke, illumination, and camera', () => {
  for (const scene of DEMO_PRESETS) {
    const preset = ALL_FIRE_PRESETS.find((item) => item.id === scene.fire);
    assert.equal(scene.fuel, preset.fuel, scene.id);
    assert.equal(scene.color, 'natural', scene.id);
    assert.equal(typeof scene.smoke, 'boolean', scene.id);
    assert.equal(scene.fireLight, 24, scene.id);
    assert.ok(scene.camera.zoom >= .7 && scene.camera.zoom <= 3, scene.id);
    assert.equal(scene.camera.pan.length, 2, scene.id);
    if (scene.fire.startsWith('legacy:')) {
      assert.ok(scene.camera.angle >= -30 && scene.camera.angle <= 30, scene.id);
      assert.equal(scene.embers, undefined, scene.id);
    }
  }
});

test('custom lighting survives a shared URL without untrusted fields', () => {
  const lights = { key: 190, keyColor: '#FFAF30', keyAz: -35, ambient: .1, bounce: 0, unrelated: 'discard' };
  const url = writeLook(new URL('https://example.com/firesim/?qa=kept'), {
    fire: 'legacy:torch', fuel: 'gas', room: true, lights,
  });
  assert.equal(url.searchParams.get('qa'), 'kept');
  assert.deepEqual(readLook(url.searchParams).lights, {
    ambient: .1, bounce: 0, key: 190, keyAz: -35, keyColor: '#ffaf30',
  });
  assert.deepEqual(readLook(new URLSearchParams('lights=invalid')), {});
  assert.deepEqual(cleanLights({ key: Infinity, rim: -100, keyColor: 'red', ambient: 10 }), { ambient: 2, rim: 0 });
});

test('links discard missing camera properties and stale lighting', () => {
  const url = writeLook(new URL('https://example.com/firesim/?zoom=3&angle=50&panX=4&panY=2&lights=old'), {
    fire: 'bonfire', fuel: 'wood', room: true, camera: { angle: 0 },
  });
  assert.equal(url.searchParams.get('angle'), '0');
  for (const key of ['zoom', 'panX', 'panY', 'lights']) assert.equal(url.searchParams.has(key), false);
});

test('source menus default to supported sources and retain an explicit experiment', () => {
  for (const engine of ['legacy', 'volume']) {
    const normal = sourceGroups(engine).flatMap((group) => group.options);
    assert.equal(normal.some((p) => p.value === 'explosion'), false);
    assert.equal(normal.some((p) => p.value === 'oil-burst'), false);
    assert.ok(normal.some((p) => p.value === 'bonfire'));
    const selected = sourceGroups(engine, false, 'explosion');
    assert.ok(selected.some((group) => group.label.includes('experimental') && group.options.some((p) => p.value === 'explosion')));
    const all = sourceGroups(engine, true).flatMap((group) => group.options);
    assert.equal(new Set(all.map((p) => p.value)).size, engine === 'legacy' ? LEGACY_PRESETS.length : FIRE_PRESETS.length);
  }
});

test('library filters preserve source parity and expose both simulations explicitly', () => {
  assert.equal(filterLibrary(ALL_FIRE_PRESETS, '', 'current', 'legacy:bonfire').length, LEGACY_PRESETS.length);
  assert.equal(filterLibrary(ALL_FIRE_PRESETS, '', 'current', 'bonfire').length, FIRE_PRESETS.length);
  assert.equal(filterLibrary(ALL_FIRE_PRESETS, '', 'all').length, ALL_FIRE_PRESETS.length);
  const results = filterLibrary(ALL_FIRE_PRESETS, 'bonfire', 'all');
  assert.ok(results.some((p) => p.id === 'bonfire'));
  assert.ok(results.some((p) => p.id === 'legacy:bonfire'));
  assert.equal(filterLibrary([{ id: 'fire', kind: 'lighting', name: 'Fire only' }], '', 'legacy').length, 1);
});

test('library capacity never silently drops imported looks and returned values are independent', () => {
  const data = new Map();
  const storage = { getItem: (key) => data.get(key), setItem: (key, value) => data.set(key, value) };
  const store = lookStore(storage, ALL_FIRE_PRESETS);
  for (let i = 0; i < 39; i++) store.add({ name: 'Look ' + i, fire: 'bonfire', lights: { key: 10 } });
  assert.throws(() => store.import({ version: 1, looks: [
    { name: 'A', fire: 'bonfire' }, { name: 'B', fire: 'bonfire' },
  ] }), /space/);
  assert.equal(store.items.length, 39);
  store.items[0].lights.key = 99;
  const exported = store.export();
  exported.looks[0].lights.key = 88;
  assert.equal(store.items[0].lights.key, 10);
  assert.throws(() => store.remove(-1), /no longer/);
  assert.equal(cleanLook({ name: 'Null camera', fire: 'bonfire', camera: { zoom: null, angle: null } }, ALL_FIRE_PRESETS).camera.zoom, 1.25);
});

test('the shell preserves its previous panel through presentation and handles recovery safely', () => {
  const previous = { document: globalThis.document, location: globalThis.location, history: globalThis.history };
  const selectors = ['#session-status', '#library-panel', '#scene-panel', '#lighting-panel', '#demo-mode', '#view', '#view-state', '#view-state-title', '#view-state-description', '#recovery-actions', '#use-original', '#message', '#library-category', '#lighting-preset'];
  const elements = new Map(selectors.map((selector) => [selector, {
    dataset: {}, attributes: {}, hidden: false,
    setAttribute(key, value) { this.attributes[key] = value; },
    focus() { this.focused = true; },
  }]));
  const panelButtons = ['scene', 'library', 'lighting'].map((panel) => ({
    dataset: { panel }, attributes: {}, setAttribute(key, value) { this.attributes[key] = value; },
  }));
  const controls = [{ disabled: false }];
  globalThis.document = Object.assign(new EventTarget(), {
    body: { dataset: {} }, querySelector: (selector) => elements.get(selector),
    querySelectorAll: (selector) => selector === '[data-panel]' ? panelButtons : controls,
  });
  globalThis.location = { href: 'https://example.com/firesim/' };
  globalThis.history = { replaceState(_state, _title, url) { globalThis.location.href = String(url); } };
  const visibility = [];
  try {
    const ui = studioUI((visible) => visibility.push(visible));
    ui.showPanel('library');
    assert.equal(ui.visible, false);
    ui.present(true);
    assert.equal(ui.visible, true);
    assert.equal(elements.get('#demo-mode').attributes['aria-pressed'], 'true');
    ui.present(false);
    assert.equal(ui.visible, false);
    assert.equal(elements.get('#library-category').focused, true);
    ui.loading();
    assert.equal(elements.get('#view').attributes['aria-busy'], 'true');
    ui.failure(new Error('Device lost'), 'volume');
    assert.equal(elements.get('#view').attributes['aria-busy'], 'false');
    assert.equal(elements.get('#use-original').hidden, false);
    assert.equal(controls[0].disabled, true);
    ui.ready();
    assert.equal(elements.get('#view-state').hidden, true);
    ui.showPanel('unknown');
    assert.equal(ui.visible, true);
    assert.deepEqual(visibility, [false, true, false, true]);
  } finally { Object.assign(globalThis, previous); }
});
