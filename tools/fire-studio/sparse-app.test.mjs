import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const app = readFileSync(resolve(root, 'pyro-gpu/app.js'), 'utf8');
const { volumeOptions } = await import(pathToFileURL(resolve(root, 'simulation-modes.js')).href);
const { normalizePowerSettings } = await import(pathToFileURL(resolve(root, 'fire-powers.js')).href);

// Execute the production closure functions with CPU-only dependencies. The
// fixture cannot create a GPU device or replace the production option policy.
function block(start, open) {
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
    if (c === '}' && --depth === 0) return app.slice(start, i + 1);
  }
  throw Error('Unterminated production block');
}
function functionSource(name) {
  const match = new RegExp(`^  function ${name}\\(`, 'm').exec(app);
  assert.ok(match, `${name} exists`);
  return block(match.index, app.indexOf('{', match.index));
}
function statusFixture(simulation = 'sparse', enabled = true) {
  const solver = { useBrickPool: enabled, latestTelemetry: {}, adapter: { description: 'Fixture GPU' } };
  const target = { textContent: '' };
  const functions = ['runtimeStatus', 'presentationStatus'].map(functionSource).join('\n');
  const runtime = new Function('solver', 'simulation', '$',
    `${functions}\nreturn {runtimeStatus,presentationStatus};`)(solver, simulation, () => target);
  return { solver, target, ...runtime };
}

test('actual app solver creation uses explicit mode before the URL changes', async () => {
  const call = /solver = await PyroSolver\.create\(canvas, volumeOptions\(params, simulation\)\);/.exec(app);
  assert.ok(call, 'production creation must consume the explicit mode policy');
  const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
  for (const simulation of ['volume', 'sparse']) {
    // All stale flags are present; the mount argument remains authoritative.
    const params = new URLSearchParams('simulation=volume&solver=adaptive&pressureWork=1&bricks=1&lightWork=1&receivers=1');
    let captured;
    const canvas = {};
    const expected = volumeOptions(params, simulation);
    const create = new AsyncFunction('PyroSolver', 'canvas', 'params', 'simulation', 'volumeOptions',
      `let solver; ${call[0]} return solver;`);
    const value = await create({ async create(target, options) {
      assert.equal(target, canvas); captured = options; return { ready: true };
    } }, canvas, params, simulation, volumeOptions);
    assert.equal(value.ready, true);
    assert.deepEqual(captured, expected);
    assert.equal(captured.brickPool, simulation === 'sparse');
    if (simulation === 'sparse') assert.deepEqual(captured, {
      adaptive: false, pressureWork: false, brickPool: true, lightWork: false, lightReceivers: false,
    });
  }
  assert.match(app, /simulation = 'volume'/);
});

test('sparse status follows completed GPU topology and reset/failure states', () => {
  const f = statusFixture();
  assert.match(f.runtimeStatus(), /telemetry pending/);
  f.solver.latestTelemetry = { brickPool: { mode: 'sparse', resident: 71, capacity: 1024, overflow: 0 } };
  f.presentationStatus();
  assert.equal(f.target.textContent, 'Sparse volume (experimental) · active bricks 71/1024 pages · Fixture GPU');
  f.solver.latestTelemetry.brickPool.migrationPending = true;
  assert.match(f.runtimeStatus(), /dense migration pending/);
  assert.doesNotMatch(f.runtimeStatus(), /active bricks/);
  f.solver.latestTelemetry.brickPool = { mode: 'dense', resident: 71, capacity: 1024, overflow: 3 };
  assert.match(f.runtimeStatus(), /dense fallback \(atlas capacity, brick coverage limit\)/);
  assert.doesNotMatch(f.runtimeStatus(), /71\/1024/);
  f.solver.latestTelemetry = {}; // reset invalidates the earlier allocator sample
  assert.match(f.runtimeStatus(), /telemetry pending/);
  f.solver.latestTelemetry.brickPool = { mode: 'sparse', resident: 2, capacity: 1024 };
  f.solver.poolTelemetryAvailable = false;
  assert.match(f.runtimeStatus(), /status unavailable/);
  assert.doesNotMatch(f.runtimeStatus(), /active bricks/);
});

test('fallback reason bits and normal Volume status remain truthful', () => {
  const f = statusFixture();
  for (const [overflow, reason] of [[1, 'atlas capacity'], [2, 'brick coverage limit'],
    [4, 'atlas memory policy'], [8, 'slot generation limit']]) {
    f.solver.latestTelemetry = { brickPool: { mode: 'dense', overflow } };
    assert.match(f.runtimeStatus(), new RegExp(reason));
  }
  f.solver.latestTelemetry.brickPool.overflow = 0;
  assert.match(f.runtimeStatus(), /dense fallback ·/);
  const normal = statusFixture('volume', false);
  assert.equal(normal.runtimeStatus(), '');
  normal.solver.adaptive = true;
  assert.equal(normal.runtimeStatus(), 'Experimental solver · ');
});

test('actual snapshot and look preserve mode, camera and valid interaction tools', () => {
  const start = app.indexOf('snapshot: () => ({');
  assert.ok(start >= 0);
  const snapshot = block(start + 'snapshot: '.length, app.indexOf('{', start)) + ')';
  const lookStart = app.indexOf('    look(item) {');
  assert.ok(lookStart >= 0);
  const look = block(lookStart, app.indexOf('{', lookStart)).replace('look(item)', 'function look(item)');
  const elements = new Map();
  const $ = (id) => {
    if (!elements.has(id)) elements.set(id, { value: 'wood', checked: false,
      setAttribute(key, value) { this[key] = value; }, dispatchEvent() {} });
    return elements.get(id);
  };
  const deps = { $, view: { dataset: {} }, Event, FIRE_COLORS: [{ id: 'natural' }],
    normalizePowerSettings,
    configureFire() {}, sync() {}, setFireLight() {},setWoodTime(){} };
  const create = new Function(...Object.keys(deps), `
    let simulation='sparse',activeTool='pan',gesture=null,activeFire={id:'sigil-cybr'},
      flameColor='natural',embers=true,smoke=false,fireLight=24,woodTimeScale=12,powers=normalizePowerSettings({}),zoom=1.8,angle=45,
      pan=[.2,-.1],testScenario=null,testStopped=false,solver={seed:1};
    ${functionSource('tool')}
    ${look}
    return { snapshot: ${snapshot}, look };
  `);
  const runtime = create(...Object.values(deps));
  const state = runtime.snapshot();
  assert.equal(state.simulation, 'sparse');
  assert.equal(state.tool, 'pan');
  assert.deepEqual(state.camera, { zoom: 1.8, angle: 45, pan: [.2, -.1] });
  assert.deepEqual(state.powers, { strength: 1, heading: 0, elevation: 9 });
  runtime.look({ tool: 'fuel', room: false, camera: { zoom: 2, angle: 30, pan: [.3, 0] } });
  assert.equal(runtime.snapshot().tool, 'fuel');
  assert.equal($('#room').checked, true, 'restoring Fuel uses the existing floor visibility policy');
  assert.equal($('#fuel-tool')['aria-pressed'], true);
  assert.deepEqual(runtime.snapshot().camera, { zoom: 2, angle: 30, pan: [.3, 0] });
  runtime.look({ tool: 'unknown' });
  assert.equal(runtime.snapshot().tool, 'fuel', 'invalid saved tools cannot break pointer routing');
  state.camera.pan[0] = 100;
  assert.equal(runtime.snapshot().camera.pan[0], .3, 'snapshots own their camera arrays');
  runtime.look({ powers: { strength: 1.8, heading: 70 } });
  assert.deepEqual(runtime.snapshot().powers, { strength: 1.8, heading: 70, elevation: 9 });
  const detached = runtime.snapshot();detached.powers.heading = -180;
  assert.equal(runtime.snapshot().powers.heading, 70, 'snapshots own their power settings');
});

test('normal metrics and benchmark results retain runtime status and snapshot identity', () => {
  const runtimeCalls = app.match(/\$\{runtimeStatus\(\)\}/g) || [];
  assert.equal(runtimeCalls.length, 2, 'both periodic metrics and benchmark label the real storage mode');
  assert.match(app, /settings: \{\s*simulation,/);
  assert.match(app, /await gpuSessionTimeout\(solver\.drain\(\), 'first presentation', 8000\);\s*presentationStatus\(\);/);
  assert.match(app, /await gpuSessionTimeout\(solver\.drain\(\), 'source presentation', 8000\);\s*presentationStatus\(\);/);
});
