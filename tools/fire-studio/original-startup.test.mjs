/**
 * Execute the production Original runtime and its actual helper scripts through
 * startup, its first frame, visibility changes, and disposal. The DOM and WebGL
 * fixtures record calls; they do not compile shaders or validate rendered pixels.
 * Native shader/render checks remain separate. No browser automation is used.
 *
 * node tools/fire-studio/original-startup.test.mjs
 * FIRE_STUDIO_ROOT may point at a packaged runtime directory to check that build.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readFileSync } from 'node:fs';
import { resolve, relative, isAbsolute } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const sourceRoot = fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/', import.meta.url));
const root = resolve(process.env.FIRE_STUDIO_ROOT || sourceRoot);
const moduleURL = file => pathToFileURL(resolve(root, file)).href;

// Keep signal handling faithful without attaching one native AbortSignal listener
// for every fixture element. One handler removes all listeners owned by a scope.
const abortRegistrations = new WeakMap();
class FixtureTarget {
  listeners = new Map();
  addEventListener(type, callback, { signal } = {}) {
    if (signal?.aborted) return;
    if (!this.listeners.has(type)) this.listeners.set(type, new Set());
    this.listeners.get(type).add(callback);
    if (signal) {
      if (!abortRegistrations.has(signal)) {
        const cleanups = [];
        abortRegistrations.set(signal, cleanups);
        signal.addEventListener('abort', () => cleanups.forEach(cleanup => cleanup()), { once: true });
      }
      abortRegistrations.get(signal).push(() => this.listeners.get(type)?.delete(callback));
    }
  }
  dispatchEvent(event) {
    for (const callback of this.listeners.get(event.type) || []) callback(event);
    this['on' + event.type]?.(event);
    return !event.defaultPrevented;
  }
  get listenerCount() { return [...this.listeners.values()].reduce((sum, listeners) => sum + listeners.size, 0); }
}
class FixtureElement extends FixtureTarget {
  constructor(id = '') {
    super();
    this.id = id;
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.style = {};
    this.dataset = {};
    this.attributes = new Map();
    const classes = new Set();
    this.classList = { add: name => classes.add(name), remove: name => classes.delete(name), toggle: (name, force) => force ? classes.add(name) : classes.delete(name) };
    this.children = [];
    this.clientWidth = 1280;
    this.clientHeight = 720;
  }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getBoundingClientRect() { return { x: 0, y: 0, left: 0, top: 0, width: this.clientWidth, height: this.clientHeight }; }
  get selectedOptions() { return this.children.filter(option => option.value === this.value); }
  matches() { return false; }
  click() { this.dispatchEvent(new Event('click')); }
}

function recordingGL() {
  const gl = {};
  const constants = 'CLAMP_TO_EDGE COLOR COLOR_ATTACHMENT0 COLOR_ATTACHMENT1 COMPILE_STATUS FLOAT FRAGMENT_SHADER FRAMEBUFFER FRAMEBUFFER_COMPLETE HALF_FLOAT LINEAR LINEAR_MIPMAP_LINEAR LINK_STATUS MAX_TEXTURE_SIZE NEAREST R16F R32F R8 RED REPEAT RGBA RGBA16F RGBA8 TEXTURE_2D TEXTURE_3D TEXTURE_MAG_FILTER TEXTURE_MIN_FILTER TEXTURE_WRAP_R TEXTURE_WRAP_S TEXTURE_WRAP_T TEXTURE0 TEXTURE1 TEXTURE2 TEXTURE3 TEXTURE5 TEXTURE7 TEXTURE8 TEXTURE14 TEXTURE15 TRIANGLES UNPACK_ALIGNMENT UNSIGNED_BYTE VERTEX_SHADER';
  constants.split(' ').forEach((name, index) => gl[name] = index + 1);
  let serial = 0;
  const textures = [], shaders = [];
  const bound = new Map();
  const calls = { draws: 0, lost: 0, extensions: [] };
  for (const name of ['createFramebuffer', 'createProgram', 'createVertexArray']) gl[name] = () => ({ kind: name, id: ++serial });
  gl.createShader = type => { const shader = { type, id: ++serial }; shaders.push(shader); return shader; };
  gl.shaderSource = (shader, source) => shader.source = source;
  gl.createTexture = () => { const texture = { id: ++serial, parameters: new Map() }; textures.push(texture); return texture; };
  gl.bindTexture = (type, texture) => bound.set(type, texture);
  gl.texParameteri = (type, parameter, value) => bound.get(type)?.parameters.set(parameter, value);
  gl.texImage2D = (type, level, internal, width, height, border, format, dataType, data) => Object.assign(bound.get(type), { internal, width, height, bytes: data?.byteLength });
  gl.texImage3D = (type, level, internal, width, height, depth, border, format, dataType, data) => Object.assign(bound.get(type), { internal, width, height, depth, bytes: data?.byteLength });
  gl.getExtension = name => {
    calls.extensions.push(name);
    if (name === 'WEBGL_lose_context') return { loseContext() { calls.lost++; } };
    if (name === 'EXT_color_buffer_float' || name === 'OES_texture_float_linear') return {};
    return null;
  };
  gl.getParameter = parameter => parameter === gl.MAX_TEXTURE_SIZE ? 16384 : 0;
  gl.checkFramebufferStatus = () => gl.FRAMEBUFFER_COMPLETE;
  gl.getShaderParameter = gl.getProgramParameter = () => true;
  gl.getShaderInfoLog = gl.getProgramInfoLog = () => '';
  gl.getUniformLocation = (program, name) => ({ program, name });
  gl.drawArrays = () => calls.draws++;
  for (const name of 'activeTexture attachShader bindFramebuffer bindVertexArray clearBufferfv compileShader deleteFramebuffer deleteProgram deleteShader deleteTexture deleteVertexArray drawBuffers framebufferTexture2D generateMipmap linkProgram pixelStorei uniform1f uniform1i uniform2f uniform3f uniform3fv uniform4i useProgram viewport'.split(' ')) gl[name] = () => {};
  return { gl, calls, textures, shaders };
}

function fixture(preset, fuel = 'wood') {
  const { gl, calls, textures, shaders } = recordingGL();
  const ids = [...readFileSync(resolve(root, 'index.html'), 'utf8').matchAll(/\bid="([^"]+)"/g)].map(match => match[1]);
  // Fire illumination is inserted by studio.js before runtime mounting.
  ids.push('fire-light', 'fire-light-value');
  const elements = new Map(ids.map(id => ['#' + id, new FixtureElement(id)]));
  for (const selector of ['main', '.stamp strong', '.fire-light-control small']) elements.set(selector, new FixtureElement(selector));
  const document = new FixtureTarget();
  document.hidden = false;
  document.querySelector = selector => {
    assert.ok(elements.has(selector), 'Startup references a fixture element missing from the studio markup: ' + selector);
    return elements.get(selector);
  };
  document.querySelector('#fire').getContext = type => type === 'webgl2' ? gl : null;
  document.querySelector('#fuel').value = fuel;
  const loadedScripts = [];
  document.createElement = tag => { assert.equal(tag, 'script'); return new FixtureElement(); };
  document.head = { append(script) {
    const filename = fileURLToPath(new URL(script.src));
    const child = relative(root, filename);
    assert.ok(!child.startsWith('..') && !isAbsolute(child), 'Runtime loader keeps helper scripts inside its artifact');
    loadedScripts.push(child.replaceAll('\\', '/'));
    import(script.src).then(() => script.onload(), () => script.onerror());
  } };
  const windowEvents = new FixtureTarget();
  const frames = new Map();
  let frameId = 0;
  const requested = [];
  const failures = [];
  Object.assign(globalThis, {
    document,
    location: { href: 'https://fixture.invalid/firesim/?room=1&fuel=' + fuel },
    HTMLElement: FixtureElement,
    Option: class extends FixtureElement { constructor(name, value) { super(); this.textContent = name; this.value = value; } },
    requestAnimationFrame: callback => { const id = ++frameId; frames.set(id, callback); return id; },
    cancelAnimationFrame: id => frames.delete(id),
    addEventListener: (...args) => windowEvents.addEventListener(...args),
    fetch: async value => {
      const filename = resolve(root, String(value).split('?')[0]);
      const child = relative(root, filename);
      assert.ok(!child.startsWith('..') && !isAbsolute(child), 'Startup fetch stays inside its runtime artifact');
      const bytes = await new Promise((resolveBytes, reject) => readFile(filename, (error, data) => error ? reject(error) : resolveBytes(data)));
      requested.push(child.replaceAll('\\', '/'));
      return { ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
    },
    SceneLights: { active: false, revision: 0, bind() {} },
  });
  return {
    gl, calls, textures, shaders, elements, frames, requested, loadedScripts, failures, document,
    listeners: () => document.listenerCount + windowEvents.listenerCount + [...elements.values()].reduce((sum, element) => sum + element.listenerCount, 0),
    async frame(now) {
      assert.equal(frames.size, 1, 'The runtime owns exactly one pending animation frame');
      const [id, callback] = frames.entries().next().value;
      frames.delete(id);
      callback(now);
      await new Promise(resolveFrame => setImmediate(resolveFrame));
      assert.deepEqual(failures, [], 'First-frame JavaScript completed without errors');
    },
  };
}

test('Original production startup and failure regression', async t => {
  const keys = ['window', 'document', 'location', 'HTMLElement', 'Option', 'requestAnimationFrame', 'cancelAnimationFrame', 'addEventListener', 'fetch', 'SceneLights', 'FireDomain', 'FireOptics', 'createFireOptics', 'createFireRoom', 'FireRoom', 'CoarsePressure', 'MacCormackAdvection', 'FireVorticity', 'SmokeLight', 'FireEmitters', 'FireProps'];
  const previous = new Map(keys.map(key => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  t.after(() => { for (const [key, descriptor] of previous) descriptor ? Object.defineProperty(globalThis, key, descriptor) : delete globalThis[key]; });
  globalThis.window = globalThis;
  const { createFireDomain } = await import(moduleURL('fire-domain.js'));
  const { FIRE_PRESETS } = await import(moduleURL('pyro-gpu/presets.js'));
  const { loadRuntime } = await import(moduleURL('runtime-loader.js'));
  async function prepare(preset, fuel) {
    const env = fixture(preset, fuel);
    env.mountLegacy = await loadRuntime('legacy');
    env.elements.get('#preset').replaceChildren(...FIRE_PRESETS.map(preset => new Option(preset.name, preset.id)), new Option('Cybrdelic sigil', 'sigil'));
    window.FireDomain = createFireDomain(preset);
    window.FireOptics = window.createFireOptics();
    window.createFireRoom();
    return env;
  }

  for (const preset of ['sigil', 'bonfire', 'explosion', 'burning-house']) await t.test(preset + ' executes startup, first frame and disposal', async () => {
    const env = await prepare(preset, preset === 'explosion' ? 'oil' : 'wood');
    const runtime = await env.mountLegacy({ initialPreset: preset, onRemount: key => assert.fail('Unexpected remount: ' + key), onFailure: error => env.failures.push(String(error)) });
    if (preset === 'sigil') assert.equal(env.loadedScripts.length, 8, 'Actual runtime loader loaded all eight production helper scripts');
    assert.equal(runtime.snapshot().fire, 'legacy:' + preset);
    assert.ok(env.requested.includes('source/source-native.rgba8.bin'));
    assert.ok(env.requested.includes('source/halfwidth-native.r8.bin'));
    if (preset === 'burning-house') assert.ok(env.requested.includes('pyro-gpu/objects/house.rgba16.bin'));
    assert.ok(env.shaders.length >= 20, 'Actual helper and runtime constructors assembled their shaders');
    const domain = window.FireDomain;
    const simulationTargets = env.textures.filter(texture => texture.internal === env.gl.RGBA16F && texture.width === domain.nx * 8 && texture.height === domain.ny * domain.depth / 8);
    assert.ok(simulationTargets.length >= 4, 'Simulation texture pairs were allocated');
    for (const texture of simulationTargets) assert.equal(texture.parameters.get(env.gl.TEXTURE_MIN_FILTER), env.gl.LINEAR, 'Float capability selects linear filtering for simulation targets');
    await env.frame(performance.now() + 40);
    assert.ok(env.calls.draws > 0, 'Actual first-frame simulation and rendering submitted draw calls');
    assert.equal(env.frames.size, 1);
    runtime.look({ fuel: 'oil', smoke: true, fireLight: 32, camera: { zoom: 1.4, angle: 12, pan: [.1, .2] } });
    assert.equal(runtime.snapshot().smoke, true);
    assert.equal(runtime.snapshot().fireLight, 32);
    runtime.setVisible(false);
    assert.equal(env.frames.size, 0, 'Hidden runtime cancels animation');
    runtime.setVisible(true);
    assert.equal(env.frames.size, 1, 'Visible runtime restarts one animation');
    await runtime.dispose();
    assert.equal(env.frames.size, 0, 'Disposed runtime cancels animation');
    assert.equal(env.listeners(), 0, 'Disposed runtime aborts scope listeners');
    assert.equal(env.calls.lost, 1, 'Disposed runtime releases the WebGL context');
  });

  await t.test('Removing the texture capability declaration reproduces the reported ReferenceError', async () => {
    const original = readFileSync(resolve(root, 'fire.js'), 'utf8');
    const declaration = /const\s+halfFloatLinear\s*=\s*!!gl\.getExtension\(['"]OES_texture_float_linear['"]\);/;
    assert.match(original, declaration);
    const broken = original.replace(declaration, "gl.getExtension('OES_texture_float_linear');").replace(/from\s*(['"])(\.[^'"]+)\1/g, (match, quote, specifier) => 'from ' + quote + new URL(specifier, moduleURL('fire.js')).href + quote);
    const env = await prepare('sigil', 'wood');
    const { mountLegacy: brokenMount } = await import('data:text/javascript;base64,' + Buffer.from(broken).toString('base64'));
    await assert.rejects(() => brokenMount({ initialPreset: 'sigil' }), error => error instanceof ReferenceError && error.message === 'halfFloatLinear is not defined');
    assert.equal(env.frames.size, 0, 'Failed startup schedules no frames');
    assert.equal(env.listeners(), 0, 'Failed startup aborts its listeners');
    assert.equal(env.calls.lost, 1, 'Failed startup releases the context');
  });
});
