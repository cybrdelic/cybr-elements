import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const studioRoot = process.env.FIRE_STUDIO_ROOT
  ? path.resolve(process.env.FIRE_STUDIO_ROOT)
  : fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/', import.meta.url));
const { FIRE_PRESETS, sourceOrigin } = await import(pathToFileURL(path.join(studioRoot, 'pyro-gpu/presets.js')).href);
const { powerDefinition, powerDirection, normalizePowerSettings } = await import(pathToFileURL(path.join(studioRoot, 'fire-powers.js')).href);
const app = fs.readFileSync(path.join(studioRoot, 'pyro-gpu/app.js'), 'utf8');

// Execute the production closure functions. This fixture supplies delayed GPU
// operations and controls; it does not substitute a reset implementation.
function functionSource(name, method = false) {
  const match = new RegExp(method ? `^    async ${name}\\(` : `^  (?:async )?function ${name}\\(`, 'm').exec(app);
  assert.ok(match, `production function ${name} must exist`);
  const open = app.indexOf('{', match.index);
  let depth = 0, quote = null, comment = null;
  for (let i = open; i < app.length; i++) {
    const c = app[i], next = app[i + 1];
    if (comment === 'line') { if (c === '\n') comment = null; continue; }
    if (comment === 'block') { if (c === '*' && next === '/') { comment = null; i++; } continue; }
    if (quote) { if (c === '\\') i++; else if (c === quote) quote = null; continue; }
    if (c === '/' && next === '/') { comment = 'line'; i++; continue; }
    if (c === '/' && next === '*') { comment = 'block'; i++; continue; }
    if (c === "'" || c === '"' || c === '`') { quote = c; continue; }
    if (c === '{') depth++;
    if (c === '}' && --depth === 0) return method
      ? app.slice(match.index, i + 1).replace(`async ${name}(`, `async function ${name}(`)
      : app.slice(match.index, i + 1);
  }
  throw Error(`Unterminated production function ${name}`);
}

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const turn = () => new Promise((resolve) => setImmediate(resolve));

function fixture({ initiallyBusy = true, visible = false, waitForFrameStop = false, deferPresentation = false } = {}) {
  const reset = deferred(), calls = [], failures = [];
  const prepare = deferred(), firstFrame = deferred(), drain = deferred();
  if (!deferPresentation) { prepare.resolve(); firstFrame.resolve(); drain.resolve(); }
  const elements = new Map();
  const $ = (key) => {
    if (!elements.has(key)) elements.set(key, { value: '', checked: false });
    return elements.get(key);
  };
  const frameStop = deferred();
  const scope = { disposed: false, visible, async stop() {
    this.disposed = true;
    calls.push('stop');
    if (waitForFrameStop) await frameStop.promise;
  } };
  const solver = {
    async selectPowerKind() {},
    source: [0, .58, 0],
    async prepareSource() { calls.push('prepare'); await prepare.promise; calls.push('prepare-complete'); },
    async reset() { calls.push('reset'); await reset.promise; calls.push('reset-complete'); },
    burst() { calls.push('burst'); },
    castPower(position, direction, strength) {
      calls.push('cast-power');this.lastCast={ position:[...position], direction:[...direction], strength };return true;
    },
    camera() { calls.push('camera'); },
    async frame(dt) { assert.equal(dt, 1 / 60); calls.push('first-frame'); await firstFrame.promise; calls.push('first-frame-complete'); },
    async drain() { calls.push('drain'); await drain.promise; calls.push('drain-complete'); },
    destroy() { calls.push('destroy'); },
  };
  const dependencies = { placeKindling() {}, $, scope, solver, FIRE_PRESETS, sourceOrigin, powerDefinition, powerDirection, normalizePowerSettings, URL,
    location: { href: 'https://example.com/firesim/?simulation=volume' },
    history: { replaceState() {} },
    onFailure: (error) => failures.push(error),
    fireHelp: () => calls.push('help'), sync: () => calls.push('sync'),
    presentationStatus: () => calls.push('presentation-status'),
    resizeObserver: { disconnect() { calls.push('disconnect'); } },
    viewUniform: () => [],
    gpuSessionTimeout: (promise, name, timeout) => {
      assert.equal(name, 'source presentation');
      assert.equal(timeout, 8000);
      return promise;
    },
  };
  const functions = ['configureFire', 'triggerSource', 'releaseBusy', 'restart', 'applyFire','sourceAction','cast','burst'].map((name) => functionSource(name)).join('\n') + '\n' + functionSource('dispose', true);
  const create = new Function(...Object.keys(dependencies), `
    'use strict';
    let busy=${initiallyBusy}, resetQueued=false, resetWaiters=[], resetCompletion=null, resetPending=false,pendingSourceActions=[],pendingOutput=null,
      benchmarkActive=false, cancelBenchmark=false, testScenario=null, testStopped=false,
      activeFire=FIRE_PRESETS.find(p=>p.id==='bonfire'), flameColor='natural', embers=true,
      powers=normalizePowerSettings({}),smoke=false, paused=false, trace=[], captureIndex=0, saved=false;
    ${functions}
    return {
      applyFire, restart, releaseBusy, dispose,castPower:burst,queueAction:sourceAction,
      state:()=>({busy,resetQueued,paused}),
    };
  `);
  const runtime = create(...Object.values(dependencies));
  return { runtime, scope, solver, prepare, reset, firstFrame, drain, frameStop, calls, failures, elements };
}

test('Volume source selection remains pending through an active frame and its queued GPU reset', async () => {
  const f = fixture();
  let settled = false;
  const selected = Promise.resolve(f.runtime.applyFire('hearth')).then(() => { settled = true; });
  await turn();
  assert.equal(settled, false, 'shell must not announce Ready while the previous frame is active');
  assert.equal(f.calls.includes('reset'), false, 'reset must wait for the active frame');
  assert.equal(f.elements.get('#preset').value, 'hearth');
  assert.equal(f.solver.fuel, .35);
  const released = f.runtime.releaseBusy();
  await turn();
  assert.equal(f.calls.filter((item) => item === 'reset').length, 1);
  assert.equal(settled, false, 'selection must still await the actual GPU reset');
  assert.equal(f.scope.visible, false, 'queued reset must flush without waiting for a visible RAF');
  f.reset.resolve();
  await Promise.all([selected, released]);
  assert.equal(settled, true);
  assert.equal(f.calls.filter((item) => item === 'burst').length, 1);
  assert.equal(f.runtime.state().busy, false);
  assert.equal(f.runtime.state().resetQueued, false);
});

test('a queued power source casts once after reset with its authored origin and saved aim', async () => {
  const f = fixture();
  const selected = f.runtime.applyFire('fireball');
  const released = f.runtime.releaseBusy();
  await turn();
  assert.equal(f.calls.includes('cast-power'), false, 'a queued cast must wait for the completed reset');
  f.reset.resolve();
  await Promise.all([selected, released]);
  assert.equal(f.calls.filter(value => value === 'cast-power').length, 1);
  assert.equal(f.calls.includes('burst'), false);
  assert.deepEqual(f.solver.lastCast, {
    position: sourceOrigin(FIRE_PRESETS.find(value => value.id === 'fireball')),
    direction: powerDirection({}), strength: 1,
  });
  assert.ok(f.calls.indexOf('cast-power') > f.calls.indexOf('reset-complete'));
});

test('a queued Volume reset failure rejects the source-selection Promise', async () => {
  const f = fixture();
  const error = Error('GPU reset failed');
  const selected = f.runtime.applyFire('hearth');
  const rejected = assert.rejects(selected, (value) => value === error);
  const released = Promise.resolve(f.runtime.releaseBusy()).catch(() => {});
  await turn();
  f.reset.reject(error);
  await Promise.all([rejected, released]);
  assert.equal(f.calls.includes('burst'), false);
  assert.equal(f.runtime.state().busy, false);
});

test('a cast requested during reset survives after the automatic starting cast',async()=>{
 const f=fixture();const selected=f.runtime.applyFire('fireball');
 f.runtime.castPower();assert.equal(f.calls.filter(v=>v==='cast-power').length,0);
 f.runtime.releaseBusy();await turn();f.reset.resolve();await selected;
 assert.equal(f.calls.filter(v=>v==='cast-power').length,2);
 assert.ok(f.calls.lastIndexOf('cast-power')>f.calls.indexOf('drain-complete'));
});

test('a failed reset discards queued source input instead of touching invalid GPU state',async()=>{
 const f=fixture();const selected=f.runtime.applyFire('fireball');
 const rejection=assert.rejects(selected,/reset rejected/);f.runtime.castPower();f.runtime.releaseBusy();await turn();f.reset.reject(Error('reset rejected'));
 await rejection;await turn();assert.equal(f.calls.filter(v=>v==='cast-power').length,0);
});

test('an immediate Volume source selection awaits reset completion and propagates rejection', async () => {
  const f = fixture({ initiallyBusy: false, visible: true });
  const error = Error('Immediate reset failed');
  const selected = f.runtime.applyFire('hearth');
  assert.equal(typeof selected?.then, 'function');
  const rejected = assert.rejects(selected, (value) => value === error);
  await turn();
  assert.equal(f.calls.filter((item) => item === 'reset').length, 1);
  f.reset.reject(error);
  await rejected;
  assert.equal(f.calls.includes('burst'), false);
  assert.equal(f.runtime.state().busy, false);
});

test('disposing a busy Volume session settles queued source selection without touching the GPU', async () => {
  const f = fixture();
  const selected = f.runtime.applyFire('hearth');
  let settled = false;
  const completed = Promise.resolve(selected).then(() => { settled = true; }, () => { settled = true; });
  await turn();
  assert.equal(settled, false);
  await f.runtime.dispose();
  await completed;
  assert.equal(settled, true);
  assert.equal(f.calls.includes('reset'), false);
  assert.equal(f.calls.includes('burst'), false);
  assert.equal(f.calls.includes('destroy'), true);
});

test('multiple source selections queued by one active frame await one completed reset', async () => {
  const f = fixture();
  let count = 0;
  const first = f.runtime.applyFire('hearth').then(() => { count++; });
  const second = f.runtime.applyFire('bonfire').then(() => { count++; });
  await turn();
  assert.equal(count, 0);
  f.runtime.releaseBusy();
  await turn();
  assert.equal(f.calls.filter((item) => item === 'reset').length, 1);
  assert.equal(count, 0);
  f.reset.resolve();
  await Promise.all([first, second]);
  assert.equal(count, 2);
  assert.equal(f.calls.filter((item) => item === 'burst').length, 1);
  assert.equal(f.elements.get('#preset').value, 'bonfire');
  assert.equal(f.runtime.state().resetQueued, false);
});

test('a coalesced reset rejection settles every waiting source selection and reports one failure', async () => {
  const f = fixture();
  const error = Error('Coalesced GPU reset failed');
  const selections = [f.runtime.applyFire('hearth'), f.runtime.applyFire('bonfire')];
  const rejected = selections.map((promise) => assert.rejects(promise, (value) => value === error));
  f.runtime.releaseBusy();
  await turn();
  f.reset.reject(error);
  await Promise.all(rejected);
  await turn();
  assert.equal(f.failures.length, 1);
  assert.equal(f.failures[0], error);
  assert.equal(f.runtime.state().busy, false);
  assert.equal(f.runtime.state().resetQueued, false);
});

test('Volume disposal waits for an in-flight reset before destroying the solver and skips relight', async () => {
  const f = fixture({ initiallyBusy: false });
  const selected = f.runtime.applyFire('hearth');
  await turn();
  let disposed = false;
  const disposal = f.runtime.dispose().then(() => { disposed = true; });
  await turn();
  assert.equal(disposed, false);
  assert.equal(f.calls.includes('destroy'), false);
  f.reset.resolve();
  await Promise.all([selected, disposal]);
  assert.equal(disposed, true);
  assert.equal(f.calls.includes('burst'), false);
  assert.equal(f.calls.includes('sync'), false);
  assert.ok(f.calls.indexOf('destroy') > f.calls.indexOf('reset-complete'));
});

test('Volume disposal awaits the active-frame drain before destroying a queued reset session', async () => {
  const f = fixture({ waitForFrameStop: true });
  const selected = f.runtime.applyFire('hearth');
  const rejected = assert.rejects(selected, /closed before its reset completed/);
  const disposal = f.runtime.dispose();
  await turn();
  assert.equal(f.calls.includes('destroy'), false);
  // This is the completion callback of the already-running production frame.
  f.runtime.releaseBusy();
  f.frameStop.resolve();
  await Promise.all([rejected, disposal]);
  assert.equal(f.calls.includes('reset'), false);
  assert.equal(f.calls.includes('burst'), false);
  assert.equal(f.calls.includes('destroy'), true);
});

test('new Volume geometry stays pending through preparation, reset, first image and GPU drain', async () => {
  const f = fixture({ deferPresentation: true });
  const objectPreset = FIRE_PRESETS.find((item) => item.object === 'cybr-tree') || FIRE_PRESETS.find((item) => item.object);
  assert.ok(objectPreset, 'packaged Volume catalog must include geometry sources');
  let settled = false;
  const selected = f.runtime.applyFire(objectPreset.id).then(() => { settled = true; });
  f.runtime.releaseBusy();
  await turn();
  assert.equal(f.solver.objectId, objectPreset.object);
  assert.equal(f.calls.includes('prepare'), true);
  assert.equal(f.calls.includes('reset'), false, 'new geometry must load before resetting its surface fields');
  assert.equal(settled, false);
  f.prepare.resolve();
  await turn();
  assert.equal(f.calls.includes('reset'), true);
  assert.equal(f.calls.includes('first-frame'), false);
  assert.equal(settled, false);
  f.reset.resolve();
  await turn();
  assert.equal(f.calls.includes('first-frame'), true);
  assert.equal(f.calls.includes('drain'), false);
  assert.equal(settled, false, 'submitted source image is not completed presentation');
  f.firstFrame.resolve();
  await turn();
  assert.equal(f.calls.includes('drain'), true);
  assert.equal(settled, false, 'shell must stay locked until submitted GPU work finishes');
  f.drain.resolve();
  await selected;
  assert.equal(settled, true);
  assert.equal(f.runtime.state().busy, false);
  const stages = f.calls.filter((item) => /^(prepare|reset|first-frame|drain)(-complete)?$/.test(item));
  assert.deepEqual(stages, ['prepare', 'prepare-complete', 'reset', 'reset-complete', 'first-frame', 'first-frame-complete', 'drain', 'drain-complete']);
});

for (const stage of ['prepare', 'firstFrame', 'drain']) {
  test(`Volume source readiness propagates a ${stage} failure without leaving a queued Promise`, async () => {
    const f = fixture({ deferPresentation: true });
    const error = Error(stage + ' failed');
    const selected = f.runtime.applyFire('hearth');
    const rejected = assert.rejects(selected, (value) => value === error);
    f.runtime.releaseBusy();
    if (stage !== 'prepare') { f.prepare.resolve(); f.reset.resolve(); }
    if (stage === 'drain') f.firstFrame.resolve();
    await turn();
    f[stage].reject(error);
    await rejected;
    await turn();
    assert.equal(f.runtime.state().busy, false);
    assert.equal(f.runtime.state().resetQueued, false);
    assert.equal(f.failures.length, 1);
    assert.equal(f.failures[0], error);
    if (stage === 'prepare') {
      assert.equal(f.calls.includes('reset'), false);
      assert.equal(f.calls.includes('first-frame'), false);
    }
  });
}

test('source input queued for a replaced preset is discarded',async()=>{
 const f=fixture();const first=f.runtime.applyFire('fireball');let oldAction=false;
 f.runtime.queueAction(()=>{oldAction=true;});const second=f.runtime.applyFire('fire-rain');
 f.runtime.releaseBusy();await turn();f.reset.resolve();await Promise.all([first,second]);
 assert.equal(oldAction,false,'input belongs to the source selected when it was recorded');
});

test('a failed queued source action still releases the reset lock',async()=>{
 const f=fixture();const selected=f.runtime.applyFire('fireball');const rejected=assert.rejects(selected,/queued input failed/);
 f.runtime.queueAction(()=>{throw Error('queued input failed');});f.runtime.releaseBusy();await turn();f.reset.resolve();await rejected;
 assert.equal(f.runtime.state().busy,false);
});
