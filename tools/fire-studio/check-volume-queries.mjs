import assert from 'node:assert/strict';
import { PyroSolver } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/solver.js';

globalThis.GPUMapMode = { READ: 1 };
const mapped = (bytes) => ({
  mapState: 'unmapped',
  async mapAsync() { this.mapState = 'mapped'; },
  getMappedRange() { return bytes.buffer; },
  unmap() { this.mapState = 'unmapped'; },
});

// Model a backend that refuses to resolve unwritten queries. Fill inactive
// readback bytes with old data, as happens when a ring slot is reused.
for (const substeps of [0, 1, 3, 12]) {
  const source = new BigUint64Array(80);
  const written = new Set();
  for (let i = 0; i < substeps * 6; i++) {
    written.add(i);
    source[i] = BigInt(i + 1) * 1_000_000n;
  }
  for (const i of [76, 77, 78, 79]) {
    written.add(i);
    source[i] = BigInt(i + 1) * 1_000_000n;
  }
  const resolved = { bytes: new Uint8Array(800) };
  const readback = { bytes: new Uint8Array(640) };
  new BigUint64Array(readback.bytes.buffer).fill(999_000_000n);
  const calls = [];
  const encoder = {
    resolveQuerySet(query, first, count, target, offset) {
      assert.equal(query, source);
      assert.equal(offset % 256, 0, 'WebGPU resolve offsets must be 256-byte aligned');
      assert.ok(offset + count * 8 <= target.bytes.length, 'resolve range must fit its staging buffer');
      for (let i = first; i < first + count; i++)
        assert.ok(written.has(i), `query ${i} was not written by this frame`);
      target.bytes.set(new Uint8Array(source.buffer, first * 8, count * 8), offset);
      calls.push(['resolve', first, count, offset]);
    },
    copyBufferToBuffer(from, fromOffset, to, toOffset, size) {
      assert.ok(fromOffset + size <= from.bytes.length);
      assert.ok(toOffset + size <= to.bytes.length);
      to.bytes.set(from.bytes.subarray(fromOffset, fromOffset + size), toOffset);
      calls.push(['copy', fromOffset, toOffset, size]);
    },
  };
  const solver = Object.assign(Object.create(PyroSolver.prototype), {
    query: source, queryResolve: resolved,
    latestTelemetry: { sampleFrame: 0, gpuSampleFrame: 0, gpu: null },
    stateEpoch: 1, destroyed: false, errors: [], maxSpeed: 1,
  });
  solver.resolveTimings(encoder, { query: readback }, substeps);
  assert.deepEqual(calls, [
    ...(substeps ? [['resolve', 0, substeps * 6, 0], ['copy', 0, 0, substeps * 48]] : []),
    ['resolve', 76, 4, 768], ['copy', 768, 608, 32],
  ]);
  const stamps = new BigUint64Array(readback.bytes.buffer);
  for (let i = 0; i < substeps * 6; i++) assert.equal(stamps[i], source[i]);
  for (let i = substeps * 6; i < 76; i++)
    assert.equal(stamps[i], 999_000_000n, 'inactive slots must not be copied or resolved');
  for (const i of [76, 77, 78, 79]) assert.equal(stamps[i], source[i]);
  const slot = {
    stats: mapped(new Float32Array([1, 0, 0, 1])),
    query: mapped(readback.bytes), pending: true, queryPending: true,
  };
  await solver.collectTelemetry(slot, substeps, 1, 1, substeps ? 1/60 : 0, true);
  assert.equal(solver.latestTelemetry.gpu.simulation, substeps * 3,
    'decoder must ignore stale inactive step timestamps, including paused frames');
  assert.equal(solver.latestTelemetry.gpu.lighting, 1);
  assert.equal(solver.latestTelemetry.gpu.render, 1);
  assert.equal(slot.pending, false);
  assert.equal(slot.queryPending, false);
  assert.equal(solver.errors.length, 0);
}

// A diagnostic map rejected by device loss must release its ring slot and
// disable timings without creating a new simulation error or retaining GPU data.
const solver = Object.assign(Object.create(PyroSolver.prototype), {
  latestTelemetry: { sampleFrame: 0, gpuSampleFrame: 0, gpu: { simulation: 5 } },
  stateEpoch: 1, destroyed: false, errors: [], maxSpeed: 1,
});
const slot = {
  stats: mapped(new Float32Array([1, 0, 0, 1])),
  query: { mapState: 'unmapped', async mapAsync() { throw Error('device lost'); } },
  pending: true, queryPending: true,
};
await solver.collectTelemetry(slot, 1, 1, 1, 1/60, true);
assert.equal(solver.queryTimingAvailable, false);
assert.equal(solver.latestTelemetry.gpu, null);
assert.equal(slot.pending, false);
assert.equal(slot.queryPending, false);
assert.equal(solver.errors.length, 0);
console.log('PASS: written queries only; zero/one/three/twelve steps; aligned 800-byte staging; stable readback; stale inactive slots ignored; failed diagnostic maps safely released.');
