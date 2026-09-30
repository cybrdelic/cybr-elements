import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { gzipSync } from 'node:zlib';
import vm from 'node:vm';
import test from 'node:test';

const source = await readFile(new URL('../outputs/cybrdelic-type/elements/water/src/cache-player.js', import.meta.url), 'utf8');
const context = vm.createContext({ ArrayBuffer, DataView, Float32Array, Uint32Array, Uint8Array, AbortController,
  DecompressionStream, Number, Map, Response, console });
vm.runInContext(source, context);
const { parseMesh, decompressMesh, validateManifest, frameNumber, CachePlayer } = context.WaterCache;
const config = { extent: [4.2, 2.4, 1.8], h: 0.024, obstacles: [] };
const manifest = { config, playbackFps: 30, frames: [{ frame: 0 }, { frame: 1 }, { frame: 2 }] };

function mesh(version = 4, change = () => {}) {
  const headerBytes = version >= 3 ? 32 : 24;
  // One vertex, one degenerate (valid) triangle, one drop, one whitewater
  // sample, one diagnostic particle, and a two-channel 1 x 1 caustic.
  const bytes = headerBytes + (version >= 2 ? 13 : 12) + 12 +
    (version === 4 ? 10 : 6) + 24 + 6 + (version >= 3 ? 2 : 0);
  const buffer = new ArrayBuffer(bytes), view = new DataView(buffer);
  const magic = [0x43465231, 0x43465232, 0x43465233, 0x43465234][version - 1];
  view.setUint32(0, magic, true);
  for (let offset = 4; offset <= 20; offset += 4) view.setUint32(offset, 1, true);
  if (version >= 3) { view.setUint32(24, 1, true); view.setUint32(28, 1, true); }
  let offset = headerBytes;
  const positions = offset;
  view.setUint16(offset, 65535, true); offset += 6;
  view.setInt16(offset, 32767, true); offset += 6;
  if (version >= 2) view.setUint8(offset++, 128);
  const indices = offset; offset += 12;
  const drops = offset; offset += 6;
  const radii = offset;
  if (version === 4) { view.setFloat32(offset, 0.02, true); offset += 4; }
  const white = offset;
  [1, 2, 3, 0.01, 2, 0.5].forEach((value, i) => view.setFloat32(offset + i * 4, value, true));
  offset += 24;
  const diagnostic = offset; offset += 6;
  if (version >= 3) { view.setUint8(offset, 123); view.setUint8(offset + 1, 234); }
  change(view, { positions, indices, drops, radii, white, diagnostic });
  return buffer;
}

for (let version = 1; version <= 4; version++) {
  test(`decode mesh format v${version} without reading beyond its payload`, () => {
    const data = parseMesh(mesh(version), config);
    assert.ok(Math.abs(data.positions[0] - config.extent[0]) < 1e-6);
    assert.equal(data.indices[0], 0);
    assert.equal(data.normals[0], 1);
    assert.equal(data.white[4], 2);
    assert.ok(data.dropRadii[0] > 0);
    assert.equal(data.causticWidth, version >= 3 ? 1 : 0);
    if (version >= 3) assert.deepEqual([...data.caustic], [123, 234]);
    else assert.equal(data.caustic, null);
  });
}

test('reject truncated or unknown headers before typed-array allocation', () => {
  assert.throws(() => parseMesh(new ArrayBuffer(12), config), /header/);
  assert.throws(() => parseMesh(mesh(4, view => view.setUint32(0, 0, true)), config), /signature/);
  const header = mesh().slice(0, 24);
  assert.throws(() => parseMesh(header, config), /caustic header/);
  assert.throws(() => parseMesh(mesh(4, view => view.setUint32(4, 0xffffffff, true)), config), /byte length/);
});

test('reject truncated and trailing payload bytes', () => {
  const buffer = mesh();
  assert.throws(() => parseMesh(buffer.slice(0, -1), config), /byte length/);
  const extra = new Uint8Array(buffer.byteLength + 1); extra.set(new Uint8Array(buffer));
  assert.throws(() => parseMesh(extra.buffer, config), /byte length/);
});

test('reject corrupt triangle indices and inconsistent caustics', () => {
  assert.throws(() => parseMesh(mesh(4, (view, fields) => view.setUint32(fields.indices, 1, true)), config), /triangle index/);
  assert.throws(() => parseMesh(mesh(4, view => view.setUint32(28, 0, true)), config), /caustic dimensions/);
});

test('reject non-finite and negative particle radii', () => {
  assert.throws(() => parseMesh(mesh(4, (view, fields) => view.setFloat32(fields.radii, NaN, true)), config), /droplet radius/);
  assert.throws(() => parseMesh(mesh(4, (view, fields) => view.setFloat32(fields.radii, -1, true)), config), /droplet radius/);
  assert.throws(() => parseMesh(mesh(4, (view, fields) => view.setFloat32(fields.white, Infinity, true)), config), /whitewater/);
  assert.throws(() => parseMesh(mesh(4, (view, fields) => view.setFloat32(fields.white + 12, -1, true)), config), /whitewater radius/);
});

test('clamp packed minimum normal into the valid range', () => {
  assert.equal(parseMesh(mesh(4, view => view.setInt16(38, -32768, true)), config).normals[0], -1);
});

test('validate domain, nonempty frame records and declared frame rate', () => {
  assert.equal(validateManifest(manifest), manifest);
  assert.throws(() => validateManifest({ ...manifest, frames: [] }), /frame records/);
  assert.throws(() => validateManifest({ ...manifest, frames: [null] }), /frame records/);
  assert.throws(() => validateManifest({ ...manifest, config: { ...config, extent: [1, 2, NaN] } }), /extents/);
  assert.throws(() => validateManifest({ ...manifest, config: { ...config, h: -1 } }), /grid spacing/);
  for (const playbackFps of [0, -1, NaN, Infinity, '30']) {
    assert.throws(() => validateManifest({ ...manifest, playbackFps }), /frame rate/);
  }
  assert.doesNotThrow(() => validateManifest({ config, frames: [{ frame: 0 }] }));
});

test('scrub indices are finite integers and clamped to the actual frame count', () => {
  assert.equal(frameNumber(1.9, 3), 1);
  assert.equal(frameNumber(-30, 3), 0);
  assert.equal(frameNumber(30, 3), 2);
  assert.throws(() => frameNumber(NaN, 3), /finite/);
  assert.throws(() => frameNumber('no', 3), /finite/);
});

test('decode gzip and report missing assets explicitly', async () => {
  const compressed = gzipSync(new Uint8Array(mesh()));
  const decoded = await decompressMesh(new Response(compressed), config);
  assert.equal(decoded.indices.length, 3);
  await assert.rejects(decompressMesh(new Response('', { status: 404 }), config),
    error => error.missingAssets && /404/.test(error.message));
  await assert.rejects(decompressMesh(new Response('not gzip'), config));
});

function renderer() {
  return { frames: [], progress: [], setFrame(data) { this.frames.push(data.id); },
    setMetrics() {}, draw(progress) { this.progress.push(progress); }, info() { return { glError: 0 }; } };
}
function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test('newest scrub wins even when aborted older fetch completes last', async () => {
  const requests = [], target = renderer(), displayed = [];
  const player = new CachePlayer({ manifest, renderer: target, onFrame: f => displayed.push(f),
    loadMesh(frame, signal) { const request = { ...deferred(), frame, signal }; requests.push(request); return request.promise; } });
  const old = player.loadFrame(0), latest = player.loadFrame(2);
  assert.equal(requests[0].signal.aborted, true);
  requests[1].resolve({ id: 2 }); await latest;
  requests[0].resolve({ id: 0 }); await old;
  assert.equal(player.current, 2);
  assert.deepEqual(target.frames, [2]);
  assert.deepEqual(displayed, [2]);
  assert.equal(player.busy, false);
});

test('older failure cannot overwrite newer success or clear its busy state', async () => {
  const requests = [], target = renderer();
  const player = new CachePlayer({ manifest, renderer: target,
    loadMesh() { const request = deferred(); requests.push(request); return request.promise; } });
  const old = player.loadFrame(0), latest = player.loadFrame(1);
  requests[0].reject(new Error('stale request failed')); await old;
  assert.equal(player.busy, true);
  requests[1].resolve({ id: 1 }); await latest;
  assert.equal(player.current, 1);
  assert.equal(player.busy, false);
});

test('bounded two-frame cache reuses frames and releases evicted meshes', async () => {
  const loads = [], target = renderer();
  const player = new CachePlayer({ manifest, renderer: target,
    loadMesh: async id => { loads.push(id); return { id }; } });
  await player.loadFrame(0); await player.loadFrame(1); await player.loadFrame(0); await player.loadFrame(2);
  assert.equal(player.memo.size, 2);
  await player.loadFrame(1);
  assert.deepEqual(loads, [0, 1, 2, 1]);
});

test('single-frame caches render at finite progress', async () => {
  const target = renderer();
  const player = new CachePlayer({ manifest: { config, playbackFps: 24, frames: [{}] }, renderer: target,
    loadMesh: async id => ({ id }) });
  await player.loadFrame(0);
  assert.equal(target.progress[0], 0);
});

test('active render errors reject and release the pending request', async () => {
  const target = renderer(); target.info = () => ({ glError: 1282 });
  const player = new CachePlayer({ manifest, renderer: target, loadMesh: async id => ({ id }) });
  await assert.rejects(player.loadFrame(1), /WebGL error 1282/);
  assert.equal(player.busy, false);
});

test('disposing an in-flight player prevents all stale render/UI mutations', async () => {
  const request = deferred(), target = renderer();
  const player = new CachePlayer({ manifest, renderer: target, loadMesh: () => request.promise });
  const pending = player.loadFrame(2); player.dispose(); request.resolve({ id: 2 }); await pending;
  assert.deepEqual(target.frames, []);
  await assert.rejects(player.loadFrame(0), /disposed/);
  assert.equal(player.busy, false);
});

test('accept already decompressed HTTP cache bodies without requiring gzip support', async () => {
  const noGzip = vm.createContext({ ArrayBuffer, DataView, Float32Array, Uint32Array, Uint8Array, AbortController,
    Number, Map, Response, console });
  vm.runInContext(source, noGzip);
  for (let version = 1; version <= 4; version++) {
    const response = new Response(new Uint8Array(mesh(version)), { headers: { 'Content-Encoding': 'gzip' } });
    const data = await noGzip.WaterCache.decompressMesh(response, config);
    assert.equal(data.indices.length, 3);
  }
  await assert.rejects(noGzip.WaterCache.decompressMesh(new Response(gzipSync(new Uint8Array(mesh()))), config), /cannot decompress/);
});

function browserHarness({ frameRate = 10, missing = false, search = '?frame=0' } = {}) {
  const elements = new Map(), events = new Map(), requests = [], drawn = [], callbacks = [];
  const element = id => {
    if (!elements.has(id)) elements.set(id, { id, value: id === 'speed' ? '1' : '0', max: '0', textContent: '',
      hidden: true, disabled: false, attributes: {}, setAttribute(name, value) { this.attributes[name] = value; },
      addEventListener() {} });
    return elements.get(id);
  };
  const document = { hidden: false, body: { classList: { add() {} } }, getElementById: element,
    addEventListener(name, callback) { events.set(name, callback); } };
  const fakeManifest = { config, playbackFps: frameRate, frames: [{ frame: 0 }, { frame: 1 }, { frame: 2 }] };
  class FakeRenderer {
    constructor() { this.frames = []; this.width = 1280; this.height = 720; }
    setup() {} setRasterProfile() {} setMode() {} resize() {}
    setFrame(data) { this.frames.push(data); } setMetrics(data) { drawn.push(data.frame); }
    draw() {} info() { return { glError: 0 }; }
  }
  const fakeGlobal = { ArrayBuffer, DataView, Float32Array, Uint32Array, Uint8Array, AbortController,
    DecompressionStream, Number, Map, Response, URLSearchParams, console, document,
    performance: { now: () => 0 }, location: { protocol: 'http:', search },
    LiquidRenderer: FakeRenderer, innerWidth: 1280, innerHeight: 720,
    addEventListener(name, callback) { events.set(name, callback); },
    requestAnimationFrame(callback) { callbacks.push(callback); return callbacks.length; }, cancelAnimationFrame() {},
    fetch: async url => {
      requests.push(url);
      return url.endsWith('manifest.json') ? { ok: true, json: async () => fakeManifest }
        : missing ? new Response('', { status: 404 }) : new Response(gzipSync(new Uint8Array(mesh())));
    } };
  const browser = vm.createContext(fakeGlobal);
  vm.runInContext(source, browser);
  return { browser, elements, element, events, requests, drawn, callbacks };
}

const flush = () => new Promise(resolve => setImmediate(resolve));
async function settle(predicate) {
  const deadline = Date.now() + 1000;
  while (!predicate() && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 2));
  assert.ok(predicate(), 'The expected asynchronous UI update did not complete.');
}

test('viewer playback and time label follow manifest FPS, not a hardcoded 24', async () => {
  const harness = browserHarness();
  const api = await harness.browser.WaterCache.startViewer({ variant: 'test' });
  assert.equal(api.ready, true);
  assert.equal(harness.element('play').disabled, false);
  harness.element('play').onclick();
  harness.callbacks.shift()(50); await flush();
  assert.deepEqual(harness.drawn, [0]);
  harness.callbacks.shift()(100); await settle(() => harness.drawn.length === 2);
  assert.deepEqual(harness.drawn, [0, 1]);
  assert.match(harness.element('status').textContent, /^0\.10 \/ 0\.20 s/);
});

test('missing optional geometry shows restoration guidance and disables playback', async () => {
  const harness = browserHarness({ missing: true });
  const api = await harness.browser.WaterCache.startViewer({ variant: 'test' });
  assert.equal(api.ready, false);
  assert.equal(harness.element('play').disabled, true);
  assert.equal(harness.element('timeline').disabled, true);
  assert.equal(harness.element('cache-error').hidden, false);
  assert.match(harness.element('error-detail').textContent, /optional mesh caches/);
  assert.match(harness.browser.WATER_ERROR, /404/);
});

test('partial historical caches inspect retained snapshots and never enable false full playback', async () => {
  const harness = browserHarness({ search: '' });
  const api = await harness.browser.WaterCache.startViewer({ variant: 'test', availableFrames: [1, 2] });
  assert.equal(api.ready, true);
  assert.equal(api.current, 1);
  assert.equal(harness.element('play').disabled, true);
  assert.equal(harness.element('timeline').max, 1);
  assert.match(harness.element('archive-note').textContent, /2 retained review snapshots/);
  harness.element('timeline').oninput({ target: { value: '1' } }); await settle(() => api.current === 2);
  assert.equal(api.current, 2);
  assert.deepEqual(harness.drawn, [1, 2]);
});

test('scrub failures are caught by the UI and return Play button to paused state', async () => {
  const harness = browserHarness();
  const api = await harness.browser.WaterCache.startViewer({ variant: 'test' });
  api.renderer.info = () => { throw new Error('context lost'); };
  harness.element('play').onclick();
  harness.element('timeline').oninput({ target: { value: '1' } }); await settle(() => Boolean(harness.browser.WATER_ERROR));
  assert.match(harness.browser.WATER_ERROR, /context lost/);
  assert.equal(harness.element('play').textContent, 'Play');
  assert.equal(harness.element('play').attributes['aria-pressed'], 'false');
});

test('back-forward page cache preserves a usable viewer while final navigation disposes it', async () => {
  const harness = browserHarness();
  const api = await harness.browser.WaterCache.startViewer({ variant: 'test' });
  harness.events.get('pagehide')({ persisted: true });
  await assert.doesNotReject(api.loadFrame(1));
  harness.events.get('pagehide')({ persisted: false });
  await assert.rejects(api.loadFrame(2), /disposed/);
});
