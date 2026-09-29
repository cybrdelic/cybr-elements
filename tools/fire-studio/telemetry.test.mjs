import test from 'node:test';
import assert from 'node:assert/strict';
import { PyroSolver, cflSafeSpeed } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/solver.js';

globalThis.GPUMapMode = { READ: 1 };

function deferredBuffer(values) {
  let finish;
  const bytes = new Float32Array(values).buffer;
  const buffer = {
    mapState: 'unmapped',
    mapAsync() { return new Promise((resolve) => { finish = () => { buffer.mapState = 'mapped'; resolve(); }; }); },
    getMappedRange() { return bytes; },
    unmap() { buffer.mapState = 'unmapped'; },
  };
  return { buffer, finish: () => finish() };
}

function solverStub() {
  const solver = Object.create(PyroSolver.prototype);
  Object.assign(solver, {
    maxSpeed: 12, stateEpoch: 0, destroyed: false, lost: null, errors: [], time: 0,
    latestTelemetry: { maxSpeed: 12, preDivergence: 0, postDivergence: 0, gpu: null },
  });
  return solver;
}

test('a delayed readback does not hold frame submission and updates speed when ready', async () => {
  const solver = solverStub();
  const { buffer, finish } = deferredBuffer([4, 8, 2, 4]);
  const slot = { stats: buffer, pending: true };
  const reading = solver.collectTelemetry(slot, 1, 1, 0, 1 / 60);
  assert.equal(solver.maxSpeed, 12);
  assert.equal(slot.pending, true);
  finish();
  await reading;
  assert.equal(solver.maxSpeed, 4);
  assert.equal(solver.latestTelemetry.preDivergence, 2);
  assert.equal(solver.latestTelemetry.postDivergence, 0.5);
  assert.equal(slot.pending, false);
  assert.equal(buffer.mapState, 'unmapped');
});

test('a delayed timestamp map releases the statistics slot for the next frame', async () => {
  const solver = solverStub();
  const stats = deferredBuffer([4, 8, 2, 4]);
  const query = deferredBuffer(new Array(160).fill(0));
  const slot = { stats: stats.buffer, query: query.buffer, pending: true, queryPending: true };
  const first = solver.collectTelemetry(slot, 0, 1, 0, 1 / 60, true);
  stats.finish();
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(slot.pending, false);
  assert.equal(slot.queryPending, true);
  assert.equal(solver.maxSpeed, 4);
  slot.pending = true;
  const second = solver.collectTelemetry(slot, 0, 2, 0, 1 / 60, false);
  stats.finish();
  await second;
  assert.equal(slot.pending, false);
  assert.equal(slot.queryPending, true);
  query.finish();
  await first;
  assert.equal(slot.queryPending, false);
});

test('a failed timing map disables optional timings without stopping simulation', async () => {
  const solver = solverStub();
  const stats = deferredBuffer([5, 0, 0, 1]);
  const query = { mapState: 'unmapped', async mapAsync() { throw Error('timing unavailable'); } };
  const slot = { stats: stats.buffer, query, pending: true, queryPending: true };
  const reading = solver.collectTelemetry(slot, 0, 1, 0, 1 / 60, true);
  stats.finish();
  await reading;
  assert.equal(solver.maxSpeed, 5);
  assert.equal(solver.queryTimingAvailable, false);
  assert.equal(solver.errors.length, 0);
  assert.equal(slot.queryPending, false);
});

test('a late readback from before reset cannot overwrite the new CFL speed', async () => {
  const solver = solverStub();
  const { buffer, finish } = deferredBuffer([2, 0, 0, 1]);
  const slot = { stats: buffer, pending: true };
  const reading = solver.collectTelemetry(slot, 1, 1, 0, 1 / 60);
  solver.stateEpoch++;
  finish();
  await reading;
  assert.equal(solver.maxSpeed, 12);
  assert.equal(slot.pending, false);
});

test('paused-frame statistics do not lower the resumed CFL speed', async () => {
  const solver = solverStub();
  const { buffer, finish } = deferredBuffer([0, 0, 0, 1]);
  const reading = solver.collectTelemetry({ stats: buffer, pending: true }, 0, 1, 0, 0);
  finish();
  await reading;
  assert.equal(solver.maxSpeed, 12);
});

test('ordinary telemetry lag grows the CFL bound without forcing an explosion budget', () => {
  const cellStep = 1.5 * 6 / 128;
  const count = (speed) => Math.max(1, Math.ceil((1 / 60) * speed / cellStep));
  assert.equal(count(cflSafeSpeed(3.5, 0, 1)), 1);
  assert.equal(count(cflSafeSpeed(3.5, 2, 1)), 1);
  assert.equal(count(cflSafeSpeed(12, 0, 0)), 3);
  assert.equal(count(cflSafeSpeed(12, 2, 0)), 3);
  // The recorded Intel bonfire reaches roughly 6 units/s. A four-frame late
  // readback should keep its two-step budget instead of forcing three steps.
  assert.equal(count(cflSafeSpeed(6, 4, 1)), 2);
  assert.ok(cflSafeSpeed(6, 4, 1) > 6);
  assert.ok(cflSafeSpeed(6, 9, 1) >= 12);
});

test('frame presentation does not await mapping, while GPU submissions stay bounded', async () => {
  const solver = solverStub();
  const pendingMaps = [];
  const pendingFences = [];
  let submitted = 0;
  const statBuffer = {
    mapState: 'unmapped',
    mapAsync() { return new Promise((resolve) => pendingMaps.push(resolve)); },
    getMappedRange() { return new Float32Array([2, 0, 0, 1]).buffer; },
    unmap() { this.mapState = 'unmapped'; },
  };
  Object.assign(solver, {
    N: 128, burstAge: 1, time: 1, lightReady: true, frameNumber: 0,
    completedFrames: 0, inFlight: [], stats: {}, query: null,
    telemetrySlots: [{ stats: statBuffer, pending: false }],
    prepareSource: async () => {}, updateObject: () => {}, stamp: () => {}, render: () => {},
    device: {
      createCommandEncoder: () => ({
        clearBuffer() {}, copyBufferToBuffer() {}, finish() { return {}; },
      }),
      queue: {
        submit() { submitted++; },
        onSubmittedWorkDone() { return new Promise((resolve) => pendingFences.push(resolve)); },
      },
    },
  });
  await solver.frame(0);
  await solver.frame(0);
  assert.equal(submitted, 2);
  assert.equal(pendingMaps.length, 1);
  assert.equal(solver.canSubmit(), false);
  assert.equal(await solver.frame(0, { waitForCapacity: false }), null);
  assert.equal(submitted, 2);
  let thirdFinished = false;
  const third = solver.frame(0).then(() => { thirdFinished = true; });
  await Promise.resolve();
  assert.equal(thirdFinished, false);
  pendingFences[0]();
  await third;
  assert.equal(submitted, 3);
  for (const finish of pendingFences.slice(1)) finish();
  pendingMaps[0]();
});
