import assert from 'node:assert/strict';
import { PyroSolver } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/solver.js';
import { ForestMesh } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/forest-mesh.js';

globalThis.GPUTextureUsage = { RENDER_ATTACHMENT: 1, TEXTURE_BINDING: 2, COPY_SRC: 4 };
globalThis.GPUBufferUsage = { UNIFORM: 1, COPY_DST: 2 };
const allocations = [];
const device = {
  createTexture(descriptor) {
    const texture = { descriptor, destroyed: false, createView: () => ({ texture }), destroy() { this.destroyed = true; } };
    allocations.push(texture);
    return texture;
  },
  createBuffer: () => ({ destroy() { this.destroyed = true; } }),
  createSampler: () => ({}),
};
const solver = Object.assign(Object.create(PyroSolver.prototype), {
  device, canvas: { width: 768, height: 432 }, resources: [], cache: new Map([['old-binding', {}]]),
});
solver.output = device.createTexture({ size: [768,432] });
solver.resources.push(solver.output);
solver.forestMesh = new ForestMesh(solver);
const oldFrames = [...solver.forestMesh.outputResources];
const shadow = solver.forestMesh.shadow.view.texture;
const oldOutput = solver.output;
assert.equal(solver.resizeOutput(1024,576), true);
assert.equal(oldOutput.destroyed, true);
assert.ok(oldFrames.every((texture) => texture.destroyed));
assert.deepEqual(solver.forestMesh.outputResources.map((texture) => texture.descriptor.size), Array(4).fill([1024,576]));
assert.equal(shadow.destroyed, false, 'viewport resize must preserve source shadow resources');
assert.equal(solver.cache.size, 0, 'old G-buffer bind groups must be invalidated');
const count = allocations.length;
assert.equal(solver.resizeOutput(1024,576), false);
assert.equal(allocations.length, count, 'repeated output dimensions must not reallocate');
assert.equal(solver.forestMesh.resources.length, 7, 'retired targets must leave the owner resource list');
const nextFrames = [...solver.forestMesh.outputResources];
solver.resizeOutput(512,288);
assert.ok(nextFrames.every((texture) => texture.destroyed));
assert.deepEqual(solver.forestMesh.outputResources.map((texture) => texture.descriptor.size), Array(4).fill([512,288]));
assert.equal(solver.forestMesh.resources.length, 7);
solver.forestMesh.destroy();
assert.equal(shadow.destroyed, true);
assert.equal(solver.forestMesh.resources.length, 0);
console.log('PASS: output/G-buffer dimensions stay equal, retired buffers released, shadow resources retained, cache invalidated, stable-size reuse, repeated resize and disposal.');
