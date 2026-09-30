import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
const root = resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname, '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const { FIRE_PRESETS, LEGACY_PRESETS, sourceOrigin } = await import(pathToFileURL(resolve(root, 'pyro-gpu/presets.js')).href);
const sceneIds = ['simulation', 'preset', 'fuel', 'show-experiments', 'pause', 'restart', 'burst', 'extinguish', 'fire-tool', 'pan-tool', 'zoom', 'zoom-in', 'zoom-out', 'orbit', 'room', 'focus-fire', 'reset-view', 'fullscreen', 'flame-color', 'embers', 'smoke-only', 'benchmark', 'retry-runtime', 'use-original'];
const cameraIds = ['fire-tool', 'pan-tool', 'zoom', 'zoom-in', 'zoom-out', 'orbit', 'room', 'focus-fire', 'reset-view', 'fullscreen'];
let serial = 0;
const volumeSource = readFileSync(resolve(root, 'pyro-gpu/app.js'), 'utf8');
const volumeFireStart = volumeSource.indexOf('  function applyFire(id) {');
const volumeFireEnd = volumeSource.indexOf('  function setFireLight(', volumeFireStart);
assert.ok(volumeFireStart >= 0 && volumeFireEnd > volumeFireStart, 'Production applyFire extraction changed');
const volumeFireBody = volumeSource.slice(volumeFireStart, volumeFireEnd);
function volumeFireContract($, solver, location, history, configured, restarted) {
  // Execute the production source selection function with a delayed reset
  // double. This catches missing reset Promise propagation in the real app.
  return Function('FIRE_PRESETS', '$', 'solver', 'location', 'history', 'configured', 'restart', 'sourceOrigin',
    'let benchmarkActive=false,cancelBenchmark=false,testScenario=null,testStopped=false,activeFire,flameColor,smoke;\n' +
    'const configureFire=()=>configured(activeFire,flameColor,smoke),fireHelp=()=>{};\n' + volumeFireBody + '\nreturn applyFire;')
    (FIRE_PRESETS, $, solver, location, history, configured, restarted, sourceOrigin);
}

// This runs the actual shell and its real state/source/camera serializers.
// GPU engines are contract doubles: no browser, shader or displayed FPS claim.
class Node {
  constructor(id = '', tag = 'div', document) {
    this.id = id; this.tagName = tag.toUpperCase(); this.ownerDocument = document;
    this.dataset = {}; this.attributes = {}; this.children = []; this.listeners = new Map();
    this.hidden = false; this.disabled = false; this.checked = false; this._value = '';
    this.textContent = ''; this.type = ''; this.min = ''; this.max = '';
  }
  set value(value) { this._value = String(value); }
  get value() { return this._value; }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  getAttribute(key) { return this.attributes[key] ?? null; }
  removeAttribute(key) { delete this.attributes[key]; }
  toggleAttribute(key, force) {
    const present = force ?? !Object.hasOwn(this.attributes, key);
    if (present) this.setAttribute(key, ''); else this.removeAttribute(key);
    return present;
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = [...children]; }
  insertAdjacentHTML(_position, html) { this.ownerDocument.parse(html); }
  cloneNode() { const node = new Node(this.id, this.tagName, this.ownerDocument); return node; }
  replaceWith(node) { this.ownerDocument.nodes.set(this.id, node); }
  closest(selector) { return selector === 'label' ? this.ownerDocument.ensure(this.id + '-label') : null; }
  matches(selector) {
    return selector.split(',').some(part => {
      const value = part.trim();
      return value.startsWith('#') ? value.slice(1) === this.id : value.toUpperCase() === this.tagName;
    });
  }
  addEventListener(type, fn) { this.listeners.set(type, [...(this.listeners.get(type) || []), fn]); }
  removeEventListener(type, fn) { this.listeners.set(type, (this.listeners.get(type) || []).filter(item => item !== fn)); }
  dispatchEvent(event) {
    Object.defineProperty(event, 'target', { configurable: true, value: this });
    this['on' + event.type]?.(event);
    for (const fn of this.listeners.get(event.type) || []) fn(event);
    if (event.bubbles) this.ownerDocument?.dispatchEvent(event);
    return true;
  }
  focus() { this.focused = true; }
}

async function studio(url = 'https://example.com/firesim/?simulation=volume&firePreset=bonfire') {
  const originals = Object.fromEntries(['window', 'document', 'location', 'history', 'Option', 'sessionStorage', '__fireStudioFixture'].map(key => [key, globalThis[key]]));
  const document = new Node('document');
  document.nodes = new Map();
  document.ensure = (id, tag) => {
    if (!document.nodes.has(id)) document.nodes.set(id, new Node(id, tag, document));
    return document.nodes.get(id);
  };
  document.parse = html => {
    for (const match of html.matchAll(/<([a-z][\w-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
      const node = document.ensure(match[3], match[1]);
      node.hidden = /\bhidden\b/.test(match[2]); node.disabled = /\bdisabled\b/.test(match[2]);
      node.checked = /\bchecked\b/.test(match[2]); node.type = /\btype="([^"]+)"/.exec(match[2])?.[1] || '';
      node.value = /\bvalue="([^"]+)"/.exec(match[2])?.[1] || '';
    }
  };
  document.parse(readFileSync(resolve(root, 'index.html'), 'utf8'));
  document.body = { dataset: {} };
  document.querySelector = selector => {
    if (selector === 'main') return document.ensure('main');
    if (selector === '.fire-light-control') return document.ensure('fire-light-control');
    if (selector === '.fire-light-control small') return document.ensure('fire-light-help');
    if (selector === '.stamp strong') return document.ensure('stamp-title');
    return document.nodes.get(selector.replace(/^#/, ''));
  };
  const panelButtons = ['scene', 'library', 'lighting'].map(panel => {
    const button = new Node('', 'button', document); button.dataset.panel = panel; return button;
  });
  document.querySelectorAll = selector => {
    if (selector === '[data-panel]') return panelButtons;
    if (selector.startsWith('#scene-panel button')) return sceneIds.map(id => document.ensure(id));
    if (selector.startsWith('.playback-bar')) return ['pause', 'restart', 'burst', 'extinguish', ...cameraIds, 'benchmark'].map(id => document.ensure(id));
    return [];
  };
  document.ownerDocument = null;
  document.createElement = tag => new Node('', tag, document);
  const window = new Node('window');
  let lights = { ambient: .05, bounce: .2, key: 0, rim: 0, tint: '#ffffff' };
  window.SceneLights = {
    get snapshot() { return { ...lights }; },
    setTransient(value) { this.transient = value; },
    apply(value) { lights = typeof value === 'object' ? { ...lights, ...value } : { ...lights, key: value === 'fire' ? 0 : 190 }; },
  };
  window.createFireOptics = () => '';
  window.createFireRoom = () => {};
  const location = { href: url };
  globalThis.document = document; globalThis.window = window; globalThis.location = location;
  globalThis.history = { replaceState(_state, _title, next) { location.href = String(next); } };
  globalThis.Option = class extends Node { constructor(name, value) { super('', 'option', document); this.textContent = name; this.value = value; } };
  const storage = new Map();
  globalThis.sessionStorage = { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
  const calls = [], runtimes = [];
  const fixture = {
    nodes: document.nodes, calls, runtimes, location, document, window, nextMountFailure: null,
    load: async kind => async options => {
      calls.push(['mount', kind, options.initialPreset]);
      if (fixture.nextMountFailure) { const error = fixture.nextMountFailure; fixture.nextMountFailure = null; throw error; }
      const original = kind === 'legacy';
      let state = { fire: '', fuel: 'wood', room: new URL(location.href).searchParams.get('room') !== '0', color: 'natural', smoke: false, fireLight: 24,
        ...(original ? {} : { embers: true }), camera: { zoom: original ? 1.8 : 1.25, angle: 16, pan: [0, original ? -1 : 0] } };
      const synchronize = () => {
        for (const [id, key] of [['fuel', 'fuel'], ['flame-color', 'color'], ['fire-light', 'fireLight']]) document.ensure(id).value = state[key];
        for (const [id, key] of [['room', 'room'], ['smoke-only', 'smoke'], ['embers', 'embers']]) if (state[key] !== undefined) document.ensure(id).checked = state[key];
        document.ensure('zoom').value = state.camera.zoom * 100;
        document.ensure('orbit').value = state.camera.angle;
        document.ensure('orbit').disabled = original && !state.room;
        document.ensure('focus-fire').disabled = state.fire.endsWith('sigil') || state.fire.endsWith('free');
      };
      const originalFire = async key => {
        if (fixture.fireGate) await fixture.fireGate;
        const preset = (original ? LEGACY_PRESETS : FIRE_PRESETS).find(item => item.id === (original ? 'legacy:' : '') + key);
        assert.ok(preset, key);
        state = { ...state, fire: preset.id, fuel: preset.fuel, color: preset.color || 'natural', smoke: !!preset.smokeSimulation || key === 'smoke-burst' };
        if (original) state.camera = { zoom: key.startsWith('sigil') ? 1 : 1.8, angle: state.camera.angle, pan: [0, key.startsWith('sigil') ? 0 : -1] };
        calls.push(['fire', kind, key]); synchronize();
      };
      const fire = original ? originalFire : volumeFireContract(
        selector => document.querySelector(selector), {}, location, globalThis.history,
        (preset, color, smoke) => {
          state = { ...state, fire: preset.id, fuel: document.ensure('fuel').value, color, smoke };
          calls.push(['fire', kind, preset.id]); synchronize();
        },
        () => fixture.fireGate || Promise.resolve(),
      );
      const runtime = {
        kind, disposed: false, visible: true,
        async dispose() { this.disposed = true; calls.push(['dispose', kind]); },
        setVisible(value) { this.visible = value; }, fire,
        snapshot: () => structuredClone(state),
        look(item) {
          calls.push(['look', kind, structuredClone(item)]);
          for (const key of ['fuel', 'room', 'smoke', 'color', 'fireLight', 'embers']) if (item[key] !== undefined && (!original || key !== 'embers')) state[key] = item[key];
          if (item.camera) state.camera = { ...state.camera, ...item.camera,
            angle: Math.max(original ? -30 : -75, Math.min(original ? 30 : 75, item.camera.angle ?? state.camera.angle)),
            pan: [...(item.camera.pan || state.camera.pan)] };
          synchronize();
        }, fail: options.onFailure,
      };
      await fire(options.initialPreset);
      document.ensure('fuel').onchange = () => { state.fuel = document.ensure('fuel').value; };
      document.ensure('room').onchange = () => { state.room = document.ensure('room').checked; synchronize(); };
      document.ensure('smoke-only').onchange = () => { state.smoke = document.ensure('smoke-only').checked; };
      document.ensure('flame-color').onchange = () => { state.color = document.ensure('flame-color').value; };
      document.ensure('fire-light').oninput = () => { state.fireLight = Number(document.ensure('fire-light').value); };
      document.ensure('orbit').oninput = () => { state.camera.angle = Number(document.ensure('orbit').value); };
      document.ensure('zoom').oninput = () => { state.camera.zoom = Number(document.ensure('zoom').value) / 100; };
      if (!original) document.ensure('embers').onchange = () => { state.embers = document.ensure('embers').checked; };
      runtimes.push(runtime); return runtime;
    },
    mountLibrary(api) { this.api = api; return { refresh() {} }; },
    restore() { Object.assign(globalThis, originals); },
    get runtime() { return runtimes.at(-1); },
    async settle() { for (let i = 0; i < 8; i++) await new Promise(resolve => setImmediate(resolve)); },
    async change(id, value, type = 'change') {
      const node = document.ensure(id);
      if (typeof value === 'boolean') node.checked = value; else node.value = value;
      node.dispatchEvent(new Event(type, { bubbles: true })); await this.settle();
    },
  };
  globalThis.__fireStudioFixture = fixture;
  const fixtureDirectory = resolve(import.meta.dirname, '../../work/studio-regression-fixtures');
  mkdirSync(fixtureDirectory, { recursive: true });
  const runtimeStub = resolve(fixtureDirectory, 'runtime-stub.mjs');
  const libraryStub = resolve(fixtureDirectory, 'library-stub.mjs');
  writeFileSync(runtimeStub, 'export const loadRuntime = kind => globalThis.__fireStudioFixture.load(kind);');
  writeFileSync(libraryStub, 'export const mountLibrary = api => globalThis.__fireStudioFixture.mountLibrary(api);');
  let source = readFileSync(resolve(root, 'studio.js'), 'utf8');
  source = source.replace(/from\s+(['"])([^'"]+)\1/g, (_match, quote, specifier) => {
    const href = specifier.startsWith('./runtime-loader.js')
      ? pathToFileURL(runtimeStub).href
      : specifier.startsWith('./pyro-gpu/library.js')
        ? pathToFileURL(libraryStub).href
        : new URL(specifier, pathToFileURL(resolve(root, 'studio.js'))).href;
    return 'from ' + quote + href + quote;
  });
  const fixturePath = resolve(fixtureDirectory, 'studio-fixture-' + (++serial) + '.mjs');
  writeFileSync(fixturePath, source);
  try { await import(pathToFileURL(fixturePath).href); assert.ok(fixture.runtime, document.ensure('gpu-status').textContent); return fixture; }
  catch (error) { fixture.restore(); throw error; }
}

test('engine switching preserves shared comparison settings and remembered camera for each matching source', async () => {
  const f = await studio();
  try {
    await f.change('fuel', 'oil'); await f.change('smoke-only', true); await f.change('flame-color', 'cobalt');
    await f.change('room', false); await f.change('fire-light', 0, 'input');
    await f.change('zoom', 210, 'input'); await f.change('orbit', 70, 'input');
    await f.change('simulation', 'legacy');
    const original = f.runtime.snapshot();
    assert.equal(original.fire, 'legacy:bonfire');
    assert.deepEqual([original.fuel, original.smoke, original.color, original.room, original.fireLight], ['oil', true, 'cobalt', false, 0]);
    await f.change('smoke-only', false); await f.change('flame-color', 'natural'); await f.change('fire-light', 38, 'input');
    await f.change('simulation', 'volume');
    const volume = f.runtime.snapshot();
    assert.deepEqual([volume.fuel, volume.smoke, volume.color, volume.room, volume.fireLight], ['oil', false, 'natural', false, 38]);
    assert.deepEqual(volume.camera, { zoom: 2.1, angle: 70, pan: [0, 0] });
    assert.equal(new URL(f.location.href).searchParams.get('fireLight'), '38');
  } finally { f.restore(); }
});

test('Original domain remount does not restore an unrelated source camera or stale color', async () => {
  const f = await studio('https://example.com/firesim/?simulation=legacy&preset=bonfire');
  try {
    await f.change('flame-color', 'cobalt'); await f.change('zoom', 300, 'input');
    await f.api.fire('legacy:explosion');
    await f.api.fire('legacy:torch');
    const state = f.runtime.snapshot();
    assert.equal(state.fire, 'legacy:torch'); assert.equal(state.fuel, 'gas');
    assert.equal(state.color, 'natural'); assert.equal(state.smoke, false);
    assert.deepEqual(state.camera, { zoom: 1.8, angle: 16, pan: [0, -1] });
  } finally { f.restore(); }
});

test('failed runtime recovery restores usable capability controls and selected source', async () => {
  const f = await studio();
  try {
    f.runtime.fail(new Error('Fixture device lost'));
    assert.equal(f.nodes.get('benchmark').disabled, true);
    assert.equal(f.nodes.get('view-state').hidden, false);
    f.nodes.get('retry-runtime').onclick(); await f.settle();
    assert.equal(f.runtime.snapshot().fire, 'bonfire');
    assert.equal(f.nodes.get('benchmark').disabled, false);
    assert.equal(f.nodes.get('zoom').disabled, false);
    assert.equal(f.nodes.get('view-state').hidden, true);
    assert.equal(f.nodes.get('simulation').disabled, false);
  } finally { f.restore(); }
});

test('source activation locks controls for the whole async transition and restores them afterward', async () => {
  const f = await studio();
  try {
    let release; f.fireGate = new Promise(resolve => { release = resolve; });
    const changing = f.api.fire('torch'); await f.settle();
    assert.equal(f.nodes.get('main').getAttribute('aria-busy'), 'true');
    assert.equal(f.nodes.get('simulation').disabled, true);
    assert.equal(f.nodes.get('preset').disabled, true);
    assert.equal(f.nodes.get('scene-panel').getAttribute('inert'), '');
    release(); await changing;
    assert.equal(f.nodes.get('main').getAttribute('aria-busy'), 'false');
    assert.equal(f.nodes.get('simulation').disabled, false);
    assert.equal(f.nodes.get('scene-panel').getAttribute('inert'), null);
  } finally { f.restore(); }
});

test('selected experiments remain reachable while hidden defaults retain parity', async () => {
  const f = await studio('https://example.com/firesim/?simulation=volume&firePreset=explosion');
  try {
    const values = () => f.nodes.get('preset').children.flatMap(group => group.children.map(option => option.value));
    assert.ok(values().includes('explosion'));
    assert.equal(values().includes('burning-house'), false);
    await f.change('simulation', 'legacy');
    assert.equal(f.runtime.snapshot().fire, 'legacy:explosion'); assert.ok(values().includes('explosion'));
    await f.change('show-experiments', true);
    assert.ok(values().includes('burning-house'));
    await f.change('preset', 'burning-house');
    assert.equal(f.runtime.snapshot().fire, 'legacy:burning-house');
  } finally { f.restore(); }
});

test('a rejected reset unlocks the shell and a queued source recovers without stale controls', async () => {
  const f = await studio();
  try {
    await f.change('room', false); await f.change('fire-light', 37, 'input');
    let reject; f.fireGate = new Promise((_resolve, fail) => { reject = fail; });
    const first = f.api.fire('torch');
    const failure = assert.rejects(first, /Fixture reset rejected/);
    const second = f.api.fire('hearth');
    await f.settle();
    assert.equal(f.nodes.get('simulation').disabled, true);
    f.fireGate = null; reject(new Error('Fixture reset rejected'));
    await failure; await second;
    assert.equal(f.runtime.snapshot().fire, 'hearth');
    assert.equal(f.runtime.snapshot().room, false);
    assert.equal(f.runtime.snapshot().fireLight, 37);
    assert.equal(f.nodes.get('main').getAttribute('aria-busy'), 'false');
    assert.equal(f.nodes.get('scene-panel').getAttribute('inert'), null);
    assert.equal(f.nodes.get('simulation').disabled, false);
    assert.equal(f.nodes.get('benchmark').disabled, false);
    assert.equal(f.nodes.get('view-state').hidden, true);
  } finally { f.restore(); }
});

test('Use Original recovery keeps the selected counterpart and custom controls', async () => {
  const f = await studio('https://example.com/firesim/?simulation=volume&firePreset=ring');
  try {
    await f.change('fuel', 'oil'); await f.change('smoke-only', true); await f.change('fire-light', 0, 'input');
    f.runtime.fail(new Error('Fixture volume lost'));
    f.nodes.get('use-original').onclick(); await f.settle();
    assert.deepEqual([f.runtime.snapshot().fire, f.runtime.snapshot().fuel, f.runtime.snapshot().smoke, f.runtime.snapshot().fireLight], ['legacy:ring', 'oil', true, 0]);
    assert.equal(f.nodes.get('embers-label').hidden, true);
    assert.equal(f.nodes.get('use-original').hidden, false); // Recovery container is hidden on success.
    assert.equal(f.nodes.get('view-state').hidden, true);
  } finally { f.restore(); }
});

test('custom lights and zero-valued shared controls survive engine switching and URL reload', async () => {
  const f = await studio();
  let shared;
  try {
    f.window.SceneLights.apply({ key: 175, rim: 70, ambient: .12, bounce: 0, keyColor: '#88AAFF' });
    f.window.dispatchEvent(new Event('scene-light-change'));
    await f.change('room', false); await f.change('fire-light', 0, 'input'); await f.change('fuel', 'oil');
    await f.change('simulation', 'legacy');
    shared = f.location.href;
    const lights = JSON.parse(new URL(shared).searchParams.get('lights'));
    assert.deepEqual([lights.key, lights.rim, lights.ambient, lights.bounce, lights.keyColor], [175, 70, .12, 0, '#88aaff']);
  } finally { f.restore(); }
  const reloaded = await studio(shared);
  try {
    assert.deepEqual([reloaded.runtime.snapshot().fire, reloaded.runtime.snapshot().room, reloaded.runtime.snapshot().fuel, reloaded.runtime.snapshot().fireLight], ['legacy:bonfire', false, 'oil', 0]);
    assert.deepEqual([reloaded.window.SceneLights.snapshot.key, reloaded.window.SceneLights.snapshot.bounce], [175, 0]);
  } finally { reloaded.restore(); }
});

test('library visibility and the back-forward cache resume only the live runtime', async () => {
  const f = await studio();
  try {
    f.document.querySelectorAll('[data-panel]')[1].onclick();
    assert.equal(f.runtime.visible, false);
    const hide = new Event('pagehide'); hide.persisted = true; f.window.dispatchEvent(hide);
    assert.equal(f.runtime.disposed, false);
    const show = new Event('pageshow'); show.persisted = true; f.window.dispatchEvent(show);
    assert.equal(f.runtime.visible, false);
    f.document.querySelectorAll('[data-panel]')[0].onclick();
    assert.equal(f.runtime.visible, true);
  } finally { f.restore(); }
});
