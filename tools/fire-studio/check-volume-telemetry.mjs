import assert from 'node:assert/strict';
import { PyroSolver } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/solver.js';

globalThis.GPUMapMode = { READ: 1 };
const deferred = () => {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
};
const mapped = (array, gate = null) => ({
  mapState: 'unmapped',
  async mapAsync() { if (gate) await gate.promise; this.mapState = 'mapped'; },
  getMappedRange() { return array.buffer; },
  unmap() { this.mapState = 'unmapped'; },
});
const slot = (speed, milliseconds, gate = null) => {
  const stamps = new BigUint64Array(80);
  stamps[1] = BigInt(milliseconds * 1e6);
  return { stats: mapped(new Float32Array([speed, 1, 0.01, 1])), query: mapped(stamps, gate), pending: true, queryPending: true };
};
const solver = Object.assign(Object.create(PyroSolver.prototype), {
  latestTelemetry: { sampleFrame: 0, gpuSampleFrame: 0, gpu: null },
  stateEpoch: 2, destroyed: false, errors: [], maxSpeed: 1,
});

const gate10 = deferred();
const pending10 = solver.collectTelemetry(slot(2, 4, gate10), 1, 10, 2, 1/60, true);
await new Promise((done) => setImmediate(done));
await solver.collectTelemetry(slot(3, 5), 1, 11, 2, 1/60, false);
assert.equal(solver.latestTelemetry.sampleFrame, 11);
gate10.resolve();
await pending10;
assert.equal(solver.latestTelemetry.sampleFrame, 11, 'late queries must not rewind stats/CFL telemetry');
assert.equal(solver.latestTelemetry.gpuSampleFrame, 10, 'query lag must not discard valid GPU timings');
assert.equal(solver.latestTelemetry.gpu.simulation, 4);
assert.equal(solver.maxSpeed, 3);

await solver.collectTelemetry(slot(1, 99), 1, 9, 2, 1/60, true);
assert.equal(solver.latestTelemetry.gpu.simulation, 4, 'older queries must not replace newer query results');
await solver.collectTelemetry(slot(8, 88), 1, 12, 1, 1/60, true);
assert.equal(solver.latestTelemetry.gpu.simulation, 4, 'prior reset/burst epoch must be ignored');
assert.equal(solver.latestTelemetry.sampleFrame, 11);

await solver.collectTelemetry(slot(3, 6), 1, 13, 2, 1/60, true);
assert.equal(solver.latestTelemetry.gpuSampleFrame, 13);
assert.equal(solver.latestTelemetry.gpu.simulation, 6);
assert.equal(solver.errors.length, 0);
console.log('PASS: late query acceptance, independent stats/query ordering, older-query rejection, stale-epoch rejection, fresh-query publication.');
