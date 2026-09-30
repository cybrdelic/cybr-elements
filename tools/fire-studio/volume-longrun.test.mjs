// Executes the production app frame closure and active PyroSolver CPU command
// paths against a delayed recording driver. No GPU, fluid fields or pixels are
// simulated here: physical stability, visual quality and native cost have their
// own gates. This protects scheduling and fixed quality during long sessions.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = process.env.FIRE_STUDIO_ROOT
  ? path.resolve(process.env.FIRE_STUDIO_ROOT)
  : fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/', import.meta.url));
const { PyroSolver } = await import(pathToFileURL(path.join(root, 'pyro-gpu/solver.js')).href);
const { simulationShaders, pressureShaders } = await import(pathToFileURL(path.join(root, 'pyro-gpu/shaders.js')).href);
const { FIRE_PRESETS, sourceOrigin } = await import(pathToFileURL(path.join(root, 'pyro-gpu/presets.js')).href);
const app = fs.readFileSync(path.join(root, 'pyro-gpu/app.js'), 'utf8');
globalThis.GPUMapMode = { READ: 1 };

function functionSource(name) {
  const match = new RegExp(`^  (?:async )?function ${name}\\(`, 'm').exec(app);
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
    if (c === '}' && --depth === 0) return app.slice(match.index, i + 1);
  }
  throw Error(`Unterminated production function ${name}`);
}

test('10,000 active display ticks keep quality fixed and queue/readback/cache growth bounded', async () => {
  const resource = (name) => ({ name });
  const tex = (name, n) => ({ n, view: resource(name) });
  const pipeline = (label) => ({ label, getBindGroupLayout: () => ({ label }) });
  let tick = 0, gpuFinishTick = 0, submitted = 0, createdGroups = 0,
    maxInFlight = 0, maxMappings = 0, scheduled = 0, stepCalls = 0;
  const fences = [], mappings = [];
  const drawCalls = new Map(), dispatchCounts = new Map();
  const pass = () => {
    let current;
    return {
      setPipeline(p) { current = p; }, setBindGroup() {}, end() {},
      dispatchWorkgroups() { dispatchCounts.set(current.label, (dispatchCounts.get(current.label) || 0) + 1); },
      dispatchWorkgroupsIndirect() { dispatchCounts.set(current.label, (dispatchCounts.get(current.label) || 0) + 1); },
      draw(...args) { drawCalls.set(current.label, args); },
    };
  };
  const encoder = () => ({ clearBuffer() {}, copyBufferToBuffer() {},
    beginComputePass: pass, beginRenderPass: pass, finish: () => ({}) });
  const device = {
    createCommandEncoder: encoder,
    createBindGroup({ entries }) {
      createdGroups++;
      assert.equal(new Set(entries.map((v) => v.binding)).size, entries.length);
      return { entries };
    },
    createTexture() { throw Error('Unexpected active-frame texture allocation'); },
    createBuffer() { throw Error('Unexpected active-frame buffer allocation'); },
    queue: {
      writeBuffer() {},
      submit() {
        submitted++;
        const cost = tick < 2000 || tick >= 6500 ? 1 : tick < 4500 ? 2 : 3;
        gpuFinishTick = Math.max(tick, gpuFinishTick) + cost;
      },
      onSubmittedWorkDone() {
        return new Promise((resolve) => fences.push({ due: gpuFinishTick, resolve }));
      },
    },
  };
  const statsBuffer = () => ({
    mapState: 'unmapped',
    mapAsync() {
      assert.equal(this.mapState, 'unmapped', 'readback buffer cannot be mapped twice');
      this.mapState = 'pending';
      return new Promise((resolve) => mappings.push({
        due: gpuFinishTick + (tick % 271 < 24 ? 12 : 2),
        resolve: () => { this.mapState = 'mapped'; resolve(); },
      }));
    },
    getMappedRange: () => new Float32Array([6, 1, .01, 1]).buffer,
    unmap() { this.mapState = 'unmapped'; },
  });
  const preset = FIRE_PRESETS.find((v) => v.id === 'bonfire');
  const s = Object.assign(Object.create(PyroSolver.prototype), {
    device, adapter: { description: 'Recording CPU contract' }, N: 128, D: 256, canvas: { width: 1280, height: 720 },
    time: 1, burstAge: 1, maxSpeed: 6, frameNumber: 0, completedFrames: 0,
    active: true, seed: 2, stateEpoch: 0, destroyed: false, errors: [], inFlight: [],
    latestTelemetry: { sampleFrame: 0, maxSpeed: 6, preDivergence: 1, postDivergence: .01, gpu: null },
    telemetrySlots: Array.from({ length: 3 }, () => ({ stats: statsBuffer(), pending: false, queryPending: false })),
    source: sourceOrigin(preset), effect: [...preset.effect], dynamics: [...preset.dynamics], chemistry: [...preset.chemistry],
    fuel: .35, color: 'natural', embers: true, smoke: false, roomVisible: true, usingTree: false,
    objectId: null, objectModels: {}, forestMesh: null, objectSettings: resource('object-settings'),
    params: Array.from({ length: 12 }, (_, i) => resource('params-' + i)),
    v: [tex('v-a', 129), tex('v-b', 129), tex('v-c', 129)],
    c: [tex('c-a', 256), tex('c-b', 256), tex('c-c', 256)], vort: tex('vorticity', 128),
    surface: [tex('surface-a', 64), tex('surface-b', 64)], emptyObject: tex('empty-object', 1),
    masks: [resource('mask-a'), resource('mask-b')], opticalMasks: [resource('optical-mask-a'), resource('optical-mask-b')],
    bricks: resource('bricks'), indirect: resource('indirect'),
    stats: resource('stats'), groupStats: resource('group-stats'), sigilSource: tex('sigil-source'),
    visibleBricks: resource('visible-bricks'), sampler: resource('sampler'), view: resource('view'),
    light: tex('incident', 64), lightSeeds: resource('seeds'), fireLights: resource('lights'),
    roomTargets: [tex('room-direct'), tex('room-bounce')], emberBuffer: resource('embers'),
    outputView: resource('output'), context: { getCurrentTexture: () => ({ createView: () => resource('canvas') }) },
    cache: new Map(), ids: new WeakMap(), nextId: 0, vi: 0, ci: 0, si: 0,
    pipelines: {}, levels: [], lightReady: false,
    floorFuel:[tex('floor-a',128),tex('floor-b',128)],floorIndex:0,hasFloorFuel:false,
  });
  for (const name of Object.keys(simulationShaders(s.N, s.D))) s.pipelines[name] = pipeline(name);
  for (let n = s.N; n >= 4; n /= 2) s.levels.push({ n, current: 0,
    p: [tex('p-' + n + '-a', n), tex('p-' + n + '-b', n)], b: tex('rhs-' + n, n),
    kernels: Object.fromEntries(Object.keys(pressureShaders(n)).map((name) => [name, pipeline('pressure-' + name + '-' + n)])),
  });
  for (const key of ['dilatePipeline', 'gatherPipeline', 'gatherAdaptivePipeline', 'roomPipeline', 'bouncePipeline',
    'lightPipeline', 'renderPipeline', 'present', 'emberPipeline', 'emberRender']) s[key] = pipeline(key);
  s.step = function (...args) { stepCalls++; return PyroSolver.prototype.step.apply(this, args); };
  const viewData = Array(48).fill(0); viewData[16] = 1; viewData[19] = 24;
  s.camera(viewData);

  const elements = new Map([['#fuel', { value: 'wood' }]]);
  const $ = (name) => {
    if (!elements.has(name)) elements.set(name, { textContent: '', checked: false });
    return elements.get(name);
  };
  const scope = { visible: true, disposed: false, schedule() { scheduled++; } };
  const dependencies = { solver: s, scope, $, params: new URLSearchParams(), metrics: {}, message: {}, sync() {},
    canvas: s.canvas, activeFire: preset, flameColor: 'natural', embers: true, fireLight: 24,
    smoke: false, zoom: 1.25, angle: 16, lightState: () => ({}), viewUniform: () => viewData,
    advanceTest() {}, releaseBusy: null, onFailure(error) { throw error; },
  };
  const create = new Function(...Object.keys(dependencies), `
    'use strict';
    let busy=false, resetQueued=false, benchmarkQueued=false, dirty=true, revision=0,
      pendingOutput=null, paused=false, trace=[], frameCount=0, queueLimitedRafs=0,
      captureIndex=0, saved=false;
    releaseBusy=()=>{busy=false;};
    ${functionSource('summary')}
    ${functionSource('frame')}
    return {frame,state:()=>({busy,paused,traceLength:trace.length})};
  `);
  const runtime = create(...Object.values(dependencies));
  const quality = () => ({ N: s.N, D: s.D, output: [s.canvas.width, s.canvas.height], source: [...s.source],
    effect: [...s.effect], dynamics: [...s.dynamics], chemistry: [...s.chemistry],
    fuel: s.fuel, color: s.color, embers: s.embers, smoke: s.smoke, room: s.roomVisible, active: s.active });
  const expectedQuality = quality(), cacheSamples = [];
  const settle = () => new Promise((resolve) => setImmediate(resolve));
  const completeDue = async () => {
    for (const list of [fences, mappings]) {
      for (let i = list.length - 1; i >= 0; i--) {
        if (list[i].due <= tick) { const [item] = list.splice(i, 1); item.resolve(); }
      }
    }
    await settle();
  };
  let skipped = 0;
  for (tick = 0; tick < 10_000; tick++) {
    await completeDue();
    const count = submitted;
    await runtime.frame();
    if (count === submitted) skipped++;
    maxInFlight = Math.max(maxInFlight, s.inFlight.length);
    maxMappings = Math.max(maxMappings, mappings.length);
    assert.ok(s.inFlight.length <= 2, 'accepted active frames must never build an unbounded GPU queue');
    assert.ok(mappings.length <= 3, 'readbacks must remain within their fixed ring');
    assert.deepEqual(quality(), expectedQuality, 'backpressure/readback delays must not silently reduce quality');
    assert.ok(runtime.state().traceLength <= 180, 'normal runtime trace must remain bounded');
    if (tick === 1500 || tick === 4000 || tick === 9000) cacheSamples.push({ tick, entries: s.cache.size, createdGroups });
  }
  tick += 100;
  await completeDue();
  assert.ok(submitted > 4_000 && skipped > 1_000, 'fixture must cover sustained active work and genuine backpressure');
  assert.ok(stepCalls > submitted, 'fixture must execute active multi-substep simulation paths');
  assert.equal(s.completedFrames, submitted, 'completed queue fences must settle');
  assert.equal(s.inFlight.length, 0);
  assert.equal(mappings.length, 0);
  assert.equal(scheduled, 10_000, 'exactly one next display callback per production app frame');
  assert.equal(runtime.state().busy, false);
  assert.equal(runtime.state().paused, false);
  assert.equal(runtime.state().traceLength, 180);
  assert.ok(Math.abs(s.time - (1 + submitted / 60)) < 1e-8, 'accepted fixed steps must preserve their simulation clock');
  assert.equal(s.cache.size, cacheSamples.at(-1).entries, 'bind groups must stop growing once all stable combinations are seen');
  assert.equal(cacheSamples[1].entries, cacheSamples[2].entries, 'delayed telemetry must not create new bind-group identities');
  assert.deepEqual(drawCalls.get('emberRender'), [6, 2048], 'ember capacity/render contract remains fixed');
  for (const label of ['roomPipeline', 'bouncePipeline', 'lightPipeline', 'renderPipeline']) {
    assert.ok(dispatchCounts.has(label) || drawCalls.has(label), label + ' must remain active throughout the run');
  }
  assert.equal(s.errors.length, 0);
  console.log(JSON.stringify({ scope: 'CPU command/scheduling contract only; no GPU, pixels or physical fluid state',
    displayTicks: 10_000, submitted, skipped, stepCalls, simulationSeconds: s.time, maxInFlight, maxMappings,
    bindGroups: s.cache.size, cacheSamples, fixedQuality: true }));
});
