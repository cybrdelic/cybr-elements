import test from "node:test";
import assert from "node:assert/strict";
import {
  cleanLook,
  lookStore,
} from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/look-storage.js";
import {
  DEMO_PRESETS,
  isExperimental,
} from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/demo-presets.js";
import { ALL_FIRE_PRESETS, FIRE_PRESETS, LEGACY_PRESETS } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/presets.js";
import { matchingPreset } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/preset-pairs.js";
import { sourceGroups, sourceSelection } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/source-picker.js";
import { createFireDomain } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-domain.js";
import { emitterKindFor } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-source-profile.js";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { runtimeScope } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/runtime-scope.js";
import { outputSize } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/output-size.js";
import { gpuSessionTimeout } from "../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/gpu-session.js";
const records = () => {
  const data = new Map();
  return { getItem: (k) => data.get(k), setItem: (k, v) => data.set(k, v) };
};

test("volume output follows physical display size while keeping 16:9 and the QA ceiling", () => {
  assert.deepEqual(outputSize(711, 1), [768, 432]);
  assert.deepEqual(outputSize(390, 2), [896, 504]);
  assert.deepEqual(outputSize(1280, 2), [1280, 720]);
  assert.deepEqual(outputSize(390, 2, true), [1280, 720]);
  assert.deepEqual(outputSize(0, 2), [1280, 720]);
});

test("a stalled WebGPU startup gives a recoverable error", async () => {
  await assert.rejects(
    gpuSessionTimeout(new Promise(() => {}), "adapter request", 1),
    /adapter request did not finish.*Hard reload/s,
  );
});

test("saved libraries preserve looks, sanitize invalid values, and reject unknown presets", () => {
  const storage = records(),
    store = lookStore(storage, ALL_FIRE_PRESETS);
  store.add({
    name: "My fire",
    fire: "bonfire",
    fireLight: 0,
    camera: { zoom: Infinity, angle: 300, pan: [NaN, 20] },
  });
  const reloaded = lookStore(storage, ALL_FIRE_PRESETS);
  assert.equal(reloaded.items[0].fireLight, 0);
  assert.deepEqual(reloaded.items[0].camera, {
    zoom: 1.25,
    angle: 75,
    pan: [0, 5],
  });
  assert.equal(
    cleanLook({ name: "Bad", fire: "missing" }, ALL_FIRE_PRESETS),
    null,
  );
  const imported = lookStore(records(), ALL_FIRE_PRESETS);
  assert.equal(imported.import(store.export()), 1);
  assert.deepEqual(imported.items, store.items);
});

test("a failed storage write does not mutate the saved library", () => {
  const storage = records(),
    store = lookStore(storage, ALL_FIRE_PRESETS);
  store.add({ name: "Keep me", fire: "legacy:sigil" });
  storage.setItem = () => {
    throw Error("Quota exceeded");
  };
  assert.throws(() => store.remove(0), /storage/);
  assert.equal(store.items.length, 1);
  assert.throws(() => store.import({ version: 2, looks: [] }), /CYBR/);
});

test("demo scenes resolve to distinct supported sources and exclude experiments", () => {
  assert.equal(
    new Set(DEMO_PRESETS.map((p) => p.id)).size,
    DEMO_PRESETS.length,
  );
  for (const scene of DEMO_PRESETS) {
    const source = ALL_FIRE_PRESETS.find((p) => p.id === scene.fire);
    assert.ok(source, scene.id);
    assert.equal(isExperimental(source), false, scene.id);
  }
});

test("switching simulations preserves supported source counterparts", () => {
  for (const [original, volume] of [
    ["legacy:bonfire", "bonfire"],
    ["legacy:hearth", "hearth"],
    ["legacy:torch", "torch"],
    ["legacy:ring", "ring"],
    ["legacy:sphere", "sphere"],
    ["legacy:curtain", "curtain"],
    ["legacy:explosion", "explosion"],
    ["legacy:sigil-cybr", "sigil-cybr"],
  ]) {
    assert.ok(LEGACY_PRESETS.some((p) => p.id === original));
    assert.ok(FIRE_PRESETS.some((p) => p.id === volume));
    assert.equal(matchingPreset("volume", original), volume);
    assert.equal(matchingPreset("legacy", volume), original);
  }
  assert.equal(matchingPreset("legacy", "burning-house"), "legacy:burning-house");
  assert.equal(matchingPreset("volume", "legacy:wall"), "curtain");
  assert.equal(matchingPreset("volume", "legacy:sigil"), "sigil-cybr");
  assert.equal(matchingPreset("volume", "legacy:free"), null);
});

test("the Original source menu exposes native versions of every 3D preset", () => {
  const groups = sourceGroups("legacy", true);
  const options = groups.flatMap((group) => group.options);
  assert.equal(LEGACY_PRESETS.length, FIRE_PRESETS.length + 4);
  for (const preset of FIRE_PRESETS) {
    const option = options.find((item) => item.value === preset.id);
    assert.equal(option?.name, preset.name);
    assert.deepEqual(sourceSelection("legacy", option.value), { kind: "legacy", key: preset.id });
    assert.ok(LEGACY_PRESETS.some((item) => item.id === 'legacy:' + preset.id));
  }
  assert.equal(options.length, LEGACY_PRESETS.length);
  assert.deepEqual(sourceSelection("legacy", "bonfire"), { kind: "legacy", key: "bonfire" });
});

test("the 3D source menu stays within the 3D engine", () => {
  const options = sourceGroups("volume", true).flatMap((group) => group.options);
  assert.equal(options.length, FIRE_PRESETS.length);
  assert.deepEqual(sourceSelection("volume", "bonfire"), { kind: "volume", key: "bonfire" });
});

test("every authored 3D source retains its ID when switching to Original and back", () => {
  for (const preset of FIRE_PRESETS) {
    const original = matchingPreset("legacy", preset.id);
    assert.equal(original, "legacy:" + preset.id);
    assert.equal(matchingPreset("volume", original), preset.id);
    assert.ok(Number.isInteger(emitterKindFor(preset)), preset.id);
    if (preset.object) {
      const asset = new URL("../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/objects/" + preset.object + ".rgba16.bin", import.meta.url);
      assert.ok(existsSync(fileURLToPath(asset)), preset.id + " geometry missing");
    }
  }
});

test("Original selects deeper domains only for burst and object sources", () => {
  const prior = globalThis.location;
  globalThis.location = { href: "https://example.com/fire-live/" };
  try {
    assert.deepEqual([createFireDomain("bonfire").blast, createFireDomain("bonfire").extent[2]], [false, 1.8]);
    assert.deepEqual([createFireDomain("oil-burst").blast, createFireDomain("oil-burst").extent[2]], [true, 4]);
    assert.deepEqual([createFireDomain("burning-house").object, createFireDomain("burning-house").extent[2]], [true, 3]);
  } finally {
    globalThis.location = prior;
  }
});

test("hidden and disposed runtimes stop scheduling; frame failures reach recovery once", async () => {
  const prior = {
    document: globalThis.document,
    requestAnimationFrame: globalThis.requestAnimationFrame,
    cancelAnimationFrame: globalThis.cancelAnimationFrame,
  };
  const queued = new Map();
  let serial = 0,
    failures = 0;
  globalThis.document = Object.assign(new EventTarget(), { hidden: false });
  globalThis.requestAnimationFrame = (fn) => {
    queued.set(++serial, fn);
    return serial;
  };
  globalThis.cancelAnimationFrame = (id) => queued.delete(id);
  const scope = runtimeScope(() => failures++);
  try {
    const callback = () => {
      throw Error("Device lost");
    };
    scope.schedule(callback);
    scope.setVisible(false);
    assert.equal(queued.size, 0);
    scope.setVisible(true);
    assert.equal(queued.size, 1);
    const [id, fn] = queued.entries().next().value;
    queued.delete(id);
    fn(1);
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(failures, 1);
    scope.setVisible(true);
    assert.equal(queued.size, 0);
    await scope.stop();
    scope.schedule(callback);
    assert.equal(queued.size, 0);
  } finally {
    Object.assign(globalThis, prior);
  }
});
import { readLook, writeLook } from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/studio-location.js';

test('shared links retain explicit fuel, room, smoke and zero-valued camera settings', () => {
  const state = {fire:'bonfire', fuel:'oil', room:false, smoke:true, color:'cobalt', embers:false, fireLight:0, camera:{zoom:2,angle:0,pan:[-1,2]}};
  const url = writeLook(new URL('https://example.com/firesim/?preset=old&qa=kept'), state);
  assert.equal(url.searchParams.has('preset'), false);
  assert.equal(url.searchParams.get('qa'), 'kept');
  const {fire, ...expected} = state;
  assert.deepEqual(readLook(url.searchParams), expected);
});

test('malformed camera links cannot pass NaN or unbounded values to a GPU camera', () => {
  const look = readLook(new URLSearchParams('angle=oops&zoom=999&panX=Infinity&panY=-999&fuel=invalid&room=oops'));
  assert.deepEqual(look, {camera:{zoom:3,angle:16,pan:[0,-5]}});
  assert.deepEqual(readLook(new URLSearchParams('fuel=gas')), {fuel:'gas'});
});

test('Original links retain shared appearance controls and remove volume-only settings', () => {
  const url = writeLook(new URL('https://example.com/firesim/?firePreset=bonfire&smoke=1&color=cobalt&embers=0&fireLight=70'), {fire:'legacy:torch', fuel:'gas',room:true, smoke:false, color:'natural', fireLight:0});
  for (const key of ['firePreset','embers']) assert.equal(url.searchParams.has(key),false,key);
  assert.equal(url.searchParams.get('preset'),'torch');
  assert.equal(url.searchParams.get('simulation'),'legacy');
  assert.equal(url.searchParams.get('smoke'),'0');
  assert.equal(url.searchParams.get('color'),'natural');
  assert.equal(url.searchParams.get('fireLight'),'0');
});

test('angle-only links preserve the source camera framing', () => {
  assert.deepEqual(readLook(new URLSearchParams('angle=0')), {camera:{angle:0}});
  assert.deepEqual(readLook(new URLSearchParams('angle=0'), {zoom:2,angle:16,pan:[1,0]}), {camera:{zoom:2,angle:0,pan:[1,0]}});
});
