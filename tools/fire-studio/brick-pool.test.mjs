import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = process.env.FIRE_STUDIO_ROOT ? path.resolve(process.env.FIRE_STUDIO_ROOT)
  : fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/', import.meta.url));
const { planBrickPool, brickPoolWGSL, brickPoolFieldWGSL, brickPoolScalarShaders,
  brickPoolKernels, createBrickPool, POOL_INDIRECT } = await import(pathToFileURL(path.join(root, 'pyro-gpu/brick-pool.js')).href);
const { simulationShaders } = await import(pathToFileURL(path.join(root, 'pyro-gpu/shaders.js')).href);

test('fixed interior atlases preserve 256Â³ spacing and reject oversized policies', () => {
  const plan = planBrickPool();
  assert.equal(plan.atlasBytes, 48 * 1024 ** 2);
  assert.equal(plan.denseBytes, 384 * 1024 ** 2);
  assert.equal(plan.voxelSize, 6 / 256);
  assert.equal(plan.requestHalo, 1);
  assert.equal(plan.halo, 0);
  assert.equal(plan.tiles.reduce((a, b) => a * b), 512);
  assert.ok(plan.atlasSize.every((n) => n <= 256));
  assert.equal(planBrickPool({ brick: 32, capacity: 64 }).atlasBytes, plan.atlasBytes);
  assert.deepEqual(planBrickPool({ capacity: 1024 }).tiles, [8, 8, 16]);
  assert.equal(planBrickPool({ capacity: 4096 }).viable, false);
  for (const options of [{ D: 128 }, { brick: 8 }, { capacity: 0 }, { capacity: 1.5 },
    { capacity: 4097 }, { requestHalo: 3 }, { maxTextureDimension3D: 16, capacity: 2 }])
    assert.throws(() => planBrickPool(options));
});

// Deterministic CPU oracle for the GPU prefix allocator, not the runtime
// allocation path. Fields deliberately include non-optical fuel/oxygen.
function allocator(plan) {
  const pages = Array.from({ length: plan.pageCount }, () => [0, 0]);
  const generation = new Uint32Array(plan.capacity), owner = new Uint32Array(plan.capacity);
  const fields = Array.from({ length: 3 }, () => Array.from({ length: plan.capacity }, () => [0, 0, 0, 0]));
  let dense = false, migration = false;
  const valid = (p) => pages[p][0] > 0 && owner[pages[p][0] - 1] === p + 1 && generation[pages[p][0] - 1] === pages[p][1];
  return { pages, generation, owner, fields, valid,
    get dense() { return dense; }, get migration() { return migration; },
    reset() { pages.forEach((p) => p.fill(0));owner.fill(0);dense = false;migration = false; },
    request(wanted) {
      if (dense) return false;
      const wantedSet = new Set(wanted), need = wanted.filter((p) => !valid(p));
      const free = Array.from(owner.keys()).filter((s) => !owner[s] || !wantedSet.has(owner[s] - 1));
      if (wanted.length > plan.fallbackPages || wanted.length > plan.capacity || need.length > free.length ||
        (need.length && free.some((s) => generation[s] === 0xffffffff))) { dense = true;migration = true;return false; }
      free.forEach((s) => { owner[s] = 0; });
      pages.forEach((p, i) => { if (!wantedSet.has(i)) p.fill(0); });
      need.forEach((p, i) => { const s = free[i];generation[s]++;owner[s] = p + 1;pages[p] = [s + 1, generation[s]];
        fields.forEach((f) => { f[s] = [0, 0, 0, 0]; }); });
      return true;
    },
    migrate() { const result = new Map();pages.forEach((page, p) => { if (valid(p)) result.set(p, [...fields[0][page[0] - 1]]); });migration = false;return result; }
  };
}

test('stable slots, stale generations, all-channel clears and atomic dense fallback', () => {
  const plan = planBrickPool({ capacity: 4 }), pool = allocator(plan);
  assert.equal(pool.request([1, 2]), true);
  const retained = [...pool.pages[2]], stale = [...pool.pages[1]];
  pool.fields.forEach((f) => { f[0] = [1, 2, 3, .8];f[1] = [.5, 1, 4, .7]; });
  assert.equal(pool.request([2, 3]), true);
  assert.deepEqual(pool.pages[2], retained);
  assert.deepEqual(pool.fields[0][1], [.5, 1, 4, .7]);
  assert.notEqual(pool.pages[3][1], stale[1]);
  assert.equal(pool.owner[stale[0] - 1], 4);
  pool.fields.forEach((f) => assert.deepEqual(f[0], [0, 0, 0, 0]));
  pool.fields[0][0] = [0, 0, 7, .95];
  const before = structuredClone(pool.pages), owners = [...pool.owner];
  assert.equal(pool.request([1, 2, 3, 4, 5]), false);
  assert.deepEqual(pool.pages, before);
  assert.deepEqual([...pool.owner], owners);
  assert.equal(pool.migration, true);
  assert.deepEqual(pool.migrate().get(3), [0, 0, 7, .95]);
  assert.equal(pool.migration, false);
  assert.equal(pool.request([3]), false, 'fallback is sticky');
  const previousGeneration = pool.generation[0];pool.reset();pool.request([3]);
  assert.ok(pool.generation[0] > previousGeneration);
  pool.reset();pool.generation.fill(0xffffffff);
  const empty = structuredClone(pool.pages);assert.equal(pool.request([0]), false);
  assert.deepEqual(pool.pages, empty, 'generation overflow cannot publish stale mappings');
});

const clamp = (v, a, b) => Math.min(Math.max(v, a), b);
const index = (x, y, z, axis) => x + axis * (y + axis * z);
const color = (x, y, z) => [x / 256, y / 512, z / 768, (x + y + z) / 1024];
function sample(logical, position) {
  if (position.some((p) => p < 0 || p > 256)) return [0, 0, 0, 0];
  const q = position.map((p) => p - .5), lo = q.map(Math.floor), f = q.map((v) => v - Math.floor(v));
  const output = [0, 0, 0, 0];
  for (let z = 0; z < 2; z++) for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++) {
    const value = logical(clamp(lo[0] + x, 0, 255), clamp(lo[1] + y, 0, 255), clamp(lo[2] + z, 0, 255));
    const weight = (x ? f[0] : 1 - f[0]) * (y ? f[1] : 1 - f[1]) * (z ? f[2] : 1 - f[2]);
    value.forEach((v, k) => { output[k] += v * weight; });
  }
  return output;
}

test('logical trilinear support crosses page faces, edges/corners and clamps domain faces', () => {
  const plan = planBrickPool({ capacity: 16 }), pages = new Map();
  for (let z = 0; z < 2; z++) for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++)
    pages.set(index(x, y, z, plan.pagesAxis), true);
  const sparse = (x, y, z) => pages.has(index(Math.floor(x / 16), Math.floor(y / 16), Math.floor(z / 16), plan.pagesAxis)) ? color(x, y, z) : [0, 0, 0, 0];
  for (const p of [[8.125, 9.7, 10.1], [16, 8, 8], [16, 16, 8], [16, 16, 16], [0, 0, 0], [0, 16, 16], [32, 20, 20]]) {
    const actual = sample(sparse, p), expected = sample((x, y, z) => x < 32 && y < 32 && z < 32 ? color(x, y, z) : [0, 0, 0, 0], p);
    actual.forEach((v, k) => assert.ok(Math.abs(v - expected[k]) < 1e-12));
  }
  assert.deepEqual(sample(sparse, [-.001, 8, 8]), [0, 0, 0, 0]);
  const field = brickPoolFieldWGSL(plan);
  assert.match(field, /if\(any\(first!=last\)\)/);
  assert.equal((field.match(/PoolClampedCell\(lo/g) ?? []).length, 7);
  assert.match(field, /clamp\(q,vec3f\(0\),vec3f\(255\)\)/, 'domain clamp precedes atlas translation');
  assert.ok(brickPoolWGSL(plan).includes(`page.generation==bpMeta[${plan.offsets.generation}u+slot]`));
});

test('coarse chemistry interpolation donors remain in one fine page for every supported ratio',()=>{
  for(const ratio of [2,4,8,16])for(let i=0;i<256/ratio;i++){
    const center=(i+.5)*ratio,lo=Math.floor(center-.5),hi=lo+1;
    assert.equal(Math.floor(lo/16),Math.floor(hi/16));
    assert.equal(Math.floor(lo/16),Math.floor(i*ratio/16));
    assert.equal((lo+hi)/2,center-.5);
  }
});

test('direct production chemistry keeps reaction/source/cleanup and fine mask indexing', () => {
  const plan = planBrickPool(), production = simulationShaders(128, 256), adapted = brickPoolScalarShaders(plan, { shaders: production });
  const reactionStart = production.correctScalar.indexOf(' let goal='), reactionEnd = production.correctScalar.indexOf(' textureStore(dst');
  assert.ok(reactionStart > 0 && reactionEnd > reactionStart);
  assert.ok(adapted.correctScalar.includes(production.correctScalar.slice(reactionStart, reactionEnd).replaceAll('scalar(old,','oldChemSample(')), 'all authored reaction/source equations remain byte-identical');
  assert.match(adapted.correctScalar, /let brick=brickCoordinate\(group.x\);let i=brick\*8u/);
  assert.match(adapted.correctScalar, /newChemStore\(vec3i\(i\),max\(c,vec4f\(0\)\)\)/);
  assert.match(adapted.correctScalar, /oldChemCell\(i\)/);
  assert.match(adapted.advectScalar, /oldChemSample\(trace\(v,x,p.step.x\)\)/);
  assert.match(adapted.advectScalar, /let i=bricks\[group.x\].xyz\*8u\+vec3u\(group.y,group.z%2u,group.z\/2u\)\*4u\+local;/);
  assert.doesNotMatch(adapted.advectScalar.slice(0,adapted.advectScalar.indexOf('struct bpPage')), /bpInvocationCell/);
  assert.throws(() => brickPoolScalarShaders(plan, { shaders: { ...production, advectScalar: production.advectScalar.replace('let i=bricks', 'let cell=bricks') } }));
});

test('requests are transport/source footprints and allocator preflights before mutation', () => {
  const kernels = brickPoolKernels(planBrickPool());
  assert.match(kernels.requestScatter, /legacyArgs\[0\]/);
  assert.match(kernels.requestExpand, /base\[p\]\|extra\[p\]/);
  assert.match(kernels.requestExpand, /for\(var z=-1;z<=1;z\+\+\)/);
  assert.doesNotMatch(kernels.requestScatter + kernels.requestExpand, /optical|temperature|soot/);
  assert.ok(kernels.topology.indexOf('let mutate=mode==0u&&failureFlags==0u;') < kernels.topology.indexOf('poolState[16u+s]=0u'));
  assert.match(kernels.clearNew, /textureStore\(a,i,vec4f\(0\)\);textureStore\(b,i,vec4f\(0\)\);textureStore\(c,i,vec4f\(0\)\)/);
  assert.match(kernels.migrate, /migrateChemPoolClampedCell\(vec3i\(i\)\)/);
  assert.match(kernels.routeScalar, /commands\[18u\+i\]=legacyArgs\[i\]/);
  assert.doesNotMatch(kernels.routeScalar, /poolState|meta|commands\[3u\+i\]/);
});

test('10,000 encoded steps retain fixed resources and bounded cached bind groups', async () => {
  const counts = { textures: 0, buffers: 0, groups: 0, destroyed: 0 }, records = [];
  const resource = () => ({ destroy() { counts.destroyed++; } });
  const device = { limits: { maxTextureDimension3D: 256 },
    createTexture() { counts.textures++;const t = resource();t.createView = () => ({});return t; },
    createBuffer() { counts.buffers++;return resource(); },
    createShaderModule: ({ code }) => ({ code, getCompilationInfo: async () => ({ messages: [] }) }),
    async createComputePipelineAsync({ label }) { return { label, getBindGroupLayout: () => ({}) }; },
    createBindGroup({ entries }) { counts.groups++;return { entries }; }
  };
  const encoder = { beginComputePass({ label }) { const record = { label };if (records.length < 24) records.push(record);
    return { setPipeline() {},setBindGroup() {},dispatchWorkgroups(...dims) { record.dims = dims; },
      dispatchWorkgroupsIndirect(buffer, offset) { record.indirect = offset; },end() {} }; }
  };
  const pool = await createBrickPool(device);pool.encodeReset(encoder);
  const frozen = { textures: counts.textures, buffers: counts.buffers }, bricks = {}, indirect = {}, dense = {};
  for (let step = 0; step < 10000; step++) {
    pool.encodeRequestsFromFineBricks(encoder, { bricks, indirect });pool.encodeTopology(encoder);
    pool.encodeMigrationToDense(encoder, step % 3, dense);pool.encodeRouteScalarDispatch(encoder, indirect);
  }
  assert.equal(counts.textures, 3);assert.equal(counts.buffers, frozen.buffers);
  assert.ok(counts.groups < 24, 'only page-table and field permutations are cached');
  assert.deepEqual(records.slice(1, 9).map((r) => r.label.split('-').at(-1)),
    ['requestClear', 'requestScatter', 'requestExpand', 'topology', 'clearNew', 'migrate', 'ackMigration', 'routeScalar']);
  assert.deepEqual(records[4].dims, [1], 'topology does not read its writable command buffer as indirect');
  assert.equal(records[5].indirect, POOL_INDIRECT.clearNew);
  assert.equal(records[6].indirect, POOL_INDIRECT.migrate);
  assert.equal(pool.statusSource.size, 64);
  pool.destroy();assert.equal(counts.destroyed, frozen.textures + frozen.buffers);
});

test('invalid pool shaders report their first compiler errors before pipeline creation and release resources', async () => {
  const counts = { created: 0, destroyed: 0, pipelines: 0, modules: 0 };
  const resource = () => { counts.created++;return { destroy() { counts.destroyed++; } }; };
  const device = { limits: { maxTextureDimension3D: 256 },
    createTexture() { return { ...resource(), createView: () => ({}) }; },
    createBuffer: resource,
    createShaderModule({ label }) {
      counts.modules++;assert.equal(label, 'chemistry-pool-topology');
      return { getCompilationInfo: async () => ({ messages: [
        { type: 'warning', lineNum: 1, message: 'not a failure' },
        ...Array.from({ length: 7 }, (_, i) => ({ type: 'error', lineNum: 19 + i, linePos: 3 + i, message: 'compiler detail ' + i })),
      ] }) };
    },
    async createComputePipelineAsync() { counts.pipelines++;throw Error('must not build an invalid module'); },
  };
  await assert.rejects(createBrickPool(device), error => {
    assert.match(error.message, /^chemistry-pool-topology: line 19, column 3: compiler detail 0/);
    assert.match(error.message, /line 23, column 7: compiler detail 4/);
    assert.doesNotMatch(error.message, /compiler detail [56]|not a failure|Invalid ShaderModule/);
    return true;
  });
  assert.equal(counts.modules, 1);assert.equal(counts.pipelines, 0);
  assert.ok(counts.created > 0);assert.equal(counts.destroyed, counts.created);
});

test('module creation, compiler rejection and backend errors clean up and allow a fresh pool retry', async () => {
  let mode = 'creation', scopeDepth = 0, popped = 0, pipelines = 0;
  const resources = [];
  const resource = () => {
    const item = { destroyed: false, destroy() { assert.equal(this.destroyed, false);this.destroyed = true; } };
    resources.push(item);return item;
  };
  const device = { limits: { maxTextureDimension3D: 256 },
    createTexture() { const item = resource();item.createView = () => ({});return item; },
    createBuffer: resource,
    pushErrorScope(type) { assert.equal(type, 'validation');assert.equal(scopeDepth, 0);scopeDepth++; },
    async popErrorScope() { assert.equal(scopeDepth, 1);scopeDepth--;popped++;return mode === 'creation' ? Error('WGSL creation detail') : null; },
    createShaderModule() { return { async getCompilationInfo() {
      if (mode === 'compiler') throw Error('compiler read failed');
      return { messages: [] };
    } }; },
    async createComputePipelineAsync({ label }) {
      pipelines++;if (mode === 'backend') throw Error('backend translation detail');
      return { label, getBindGroupLayout: () => ({}) };
    },
  };
  for (const [stage, expected] of [['creation', 'WGSL creation detail'], ['compiler', 'compiler read failed'], ['backend', 'backend translation detail']]) {
    mode = stage;
    await assert.rejects(createBrickPool(device), { message: 'chemistry-pool-topology: ' + expected });
    assert.equal(scopeDepth, 0);assert.ok(resources.every(item => item.destroyed));
  }
  assert.equal(pipelines, 1, 'invalid modules never reach pipeline creation');
  assert.equal(popped, 3, 'compilation rejection still pops its validation scope');
  mode = 'valid';
  const pool = await createBrickPool(device, { capacity: 1024 });
  assert.equal(scopeDepth, 0);assert.equal(Object.keys(pool.pipelines).length, 10);
  assert.equal(popped, 13);assert.equal(pipelines, 11);
  pool.destroy();assert.ok(resources.every(item => item.destroyed));
});
