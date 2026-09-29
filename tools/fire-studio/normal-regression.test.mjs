import test from "node:test";
import assert from "node:assert/strict";
import { inspectionState } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/inspection-state.js";
import { PyroSolver } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/solver.js";
import { FIRE_PRESETS } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/presets.js";
import fs from "node:fs";

test("inspection navigation restores the original look, including after reload", () => {
  const records = new Map(),
    storage = {
      getItem: (k) => records.get(k),
      setItem: (k, v) => records.set(k, v),
      removeItem: (k) => records.delete(k),
    };
  const original = {
    lights: { key: 31 },
    fireLight: 18,
    room: false,
    camera: { zoom: 1.7, angle: 22, pan: [0, 0] },
  };
  const state = inspectionState(storage);
  state.enter(original, "volume");
  state.enter({ lights: { key: 240 } }, "volume");
  const reloaded = inspectionState(storage);
  reloaded.enter({ lights: { key: 240 } }, "volume");
  assert.deepEqual(reloaded.leave("volume"), {
    version: 1,
    engine: "volume",
    ...original,
  });
  assert.equal(records.size, 0);
  state.enter(original, "volume");
  assert.equal(state.leave("volume", true), null);
  state.enter(original, "volume");
  assert.equal(state.leave("legacy").camera, undefined);
  const denied = inspectionState({
    getItem() {
      throw Error("denied");
    },
    setItem() {
      throw Error("denied");
    },
    removeItem() {
      throw Error("denied");
    },
  });
  denied.enter(original, "volume");
  assert.equal(denied.leave("volume").fireLight, 18);
});

test("normal fire presets remain object-free and only the bonfire's tuned rise changes", () => {
  const reference = JSON.parse(
    fs.readFileSync(
      new URL("./fixtures/original-fire-presets.json", import.meta.url),
    ),
  );
  for (const id of ["hearth", "bonfire", "torch", "sigil-cybr"]) {
    const current = FIRE_PRESETS.find((p) => p.id === id),
      old = reference.presets.find((p) => p.id === id);
    assert.equal(current.object, undefined);
    for (const key of id === "bonfire" ? ["effect"] : ["effect", "dynamics", "chemistry"])
      assert.deepEqual(current[key], old[key], id + " " + key);
    if (id === "bonfire") {
      assert.ok(current.dynamics[0] < old.dynamics[0], "source jet is lower");
      assert.ok(current.dynamics[3] < old.dynamics[3], "heat lift is lower");
      assert.ok(current.chemistry[1] > 1, "fuel feed retains a full flame");
    }
  }
  assert.equal(
    FIRE_PRESETS.find((p) => p.id === "burning-logs").object,
    "logs",
  );
});

test("tree allocations are lazy and released when returning to normal fire", async () => {
  globalThis.GPUTextureUsage = {
    TEXTURE_BINDING: 1,
    STORAGE_BINDING: 2,
    COPY_DST: 4,
    RENDER_ATTACHMENT: 8,
    COPY_SRC: 16,
  };
  globalThis.GPUBufferUsage = {
    UNIFORM: 1,
    COPY_DST: 2,
    STORAGE: 4,
    COPY_SRC: 8,
    MAP_READ: 16,
    INDIRECT: 32,
    VERTEX: 64,
    INDEX: 128,
  };
  const owned = [],
    requested = [];
  let serial = 0;
  const resource = (spec) => {
    const r = {
      spec,
      id: ++serial,
      destroyed: false,
      destroy() {
        this.destroyed = true;
      },
      createView() {
        return { resource: this };
      },
    };
    owned.push(r);
    return r;
  };
  const pass = () => ({
    setPipeline() {},
    setBindGroup() {},
    dispatchWorkgroups() {},
    end() {},
  });
  const pipeline = (spec) => ({
    label: spec.label,
    getBindGroupLayout() {
      return {};
    },
  });
  const device = {
    features: new Set(),
    lost: new Promise(() => {}),
    addEventListener() {},
    destroy() {},
    createTexture: resource,
    createBuffer: resource,
    createSampler: () => ({}),
    createShaderModule: () => ({
      async getCompilationInfo() {
        return { messages: [] };
      },
    }),
    async createComputePipelineAsync(spec) {
      return pipeline(spec);
    },
    async createRenderPipelineAsync(spec) {
      return pipeline(spec);
    },
    createBindGroup: () => ({}),
    createCommandEncoder: () => ({
      beginComputePass: pass,
      finish: () => ({}),
    }),
    queue: {
      writeTexture() {},
      writeBuffer() {},
      submit() {},
      copyExternalImageToTexture() {},
    },
  };
  const priorFetch = globalThis.fetch,
    priorBitmap = globalThis.createImageBitmap;
  globalThis.fetch = async (url) => {
    const name = new URL(url).pathname.split("/").at(-1);
    requested.push(name);
    const bytes =
      name === "source-native.rgba8.bin"
        ? 896 * 504 * 4
        : name.endsWith(".rgba16.bin")
          ? 64 ** 3 * 8
          : name === "vertices.bin"
            ? 36
            : 12;
    return {
      ok: true,
      arrayBuffer: async () => new ArrayBuffer(bytes),
      json: async () => ({
        files: { "vertices.bin": { bytes: 36 }, "indices.bin": { bytes: 12 } },
        triangles: 1,
      }),
      blob: async () => ({}),
    };
  };
  globalThis.createImageBitmap = async () => ({
    width: 16,
    height: 16,
    close() {},
  });
  const solver = new PyroSolver(
    device,
    { width: 1280, height: 720 },
    { context: { configure() {} }, format: "rgba8unorm" },
  );
  try {
    await solver.init();
    assert.deepEqual(requested, ["source-native.rgba8.bin"]);
    assert.equal(solver.forestMesh, null);
    assert.equal(solver.damage, null);
    assert.equal(
      owned.filter((r) => r.spec.format?.startsWith("depth")).length,
      0,
    );
    solver.objectId = "cybr-tree";
    await solver.prepareSource();
    assert.equal(solver.usingTree, true);
    assert.equal(solver.forestMesh.ready, true);
    const treeOwned = [
      ...solver.forestMesh.resources,
      ...solver.damage.map((d) => d.t),
    ];
    assert.ok(treeOwned.length > 10);
    solver.objectId = null;
    await solver.prepareSource();
    assert.equal(solver.usingTree, false);
    assert.equal(solver.forestMesh, null);
    assert.equal(solver.damage, null);
    assert.ok(treeOwned.every((r) => r.destroyed));
    assert.deepEqual(solver.meshBindings(), []);
    assert.deepEqual(solver.meshShadowBindings(), []);
    solver.objectId = "logs";
    await solver.prepareSource();
    await solver.prepareSource();
    assert.equal(requested.filter((n) => n === "logs.rgba16.bin").length, 1);
    assert.equal(solver.forestMesh, null);
  } finally {
    solver.destroy();
    globalThis.fetch = priorFetch;
    globalThis.createImageBitmap = priorBitmap;
  }
});
