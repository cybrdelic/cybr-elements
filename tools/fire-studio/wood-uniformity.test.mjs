import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load = file => import(pathToFileURL(resolve(root, file)).href);
const { woodMaterialWGSL, woodMaterialGLSL } = await load('wood-material.js');
const { forestMeshWGSL, forestShadowWGSL } = await load('pyro-gpu/forest-mesh.js');
const { rendererShaders } = await load('pyro-gpu/renderer.js');

const quadCalls = /\b(?:dpdx(?:Coarse|Fine)?|dpdy(?:Coarse|Fine)?|fwidth(?:Coarse|Fine)?|textureSample|textureSampleBias|textureSampleCompare)\s*\(/g;
const stripComments = code => code.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, '');
function functions(code) {
  const clean = stripComments(code), result = [];
  for (const match of clean.matchAll(/\bfn\s+(\w+)\s*\(/g)) {
    const start = clean.indexOf('{', match.index);
    let depth = 1, end = start + 1;
    for (; end < clean.length && depth; end++) {
      if (clean[end] === '{') depth++;
      else if (clean[end] === '}') depth--;
    }
    assert.equal(depth, 0, 'balanced function ' + match[1]);
    result.push({ name: match[1], body: clean.slice(start + 1, end - 1) });
  }
  return result;
}

// This is a narrow architectural gate, not a replacement for Tint validation.
// Quad-dependent operations are legal only in the straight-line prefix of the
// fragment entry point. Helpers and conditional hits must stay derivative-free.
function uniformEntryGate(code, label) {
  assert.doesNotMatch(code, /diagnostic\s*\(\s*(?:off|warning|info)\s*,\s*derivative_uniformity/);
  for (const fn of functions(code)) {
    const calls = [...fn.body.matchAll(quadCalls)];
    if (!calls.length) continue;
    assert.equal(fn.name, 'fragment', label + ': hidden quad operation in ' + fn.name);
    const control = fn.body.search(/\b(?:if|for|while|loop|switch|discard|return)\b/);
    for (const call of calls)
      assert.ok(control < 0 || call.index < control, label + ': quad operation after control flow');
  }
}

test('shared WGSL wood helpers do not hide derivatives or implicit texture samples', () => {
  assert.equal([...stripComments(woodMaterialWGSL).matchAll(quadCalls)].length, 0);
  assert.match(woodMaterialWGSL, /fn woodFeaturesFiltered/);
  assert.match(woodMaterialWGSL, /fn woodSurfaceNormal/);
  assert.match(woodMaterialGLSL, /vec4 woodMaterial\(/);
  assert.match(woodMaterialGLSL, /vec3 woodNormal\(/);
  assert.match(woodMaterialGLSL, /dFdx\(phases\)/);
  assert.doesNotMatch(woodMaterialGLSL, /float (?:q|phases|r1|r2)=/);
});

test('mesh samples and wood/photo derivatives precede cap and leaf discard', () => {
  uniformEntryGate(forestMeshWGSL, 'forest mesh');
  uniformEntryGate(forestShadowWGSL, 'forest shadow');
  const fragment = functions(forestMeshWGSL).find(fn => fn.name === 'fragment').body;
  assert.ok(fragment.indexOf('woodDy=dpdy(woodHeight)') < fragment.indexOf('discard'));
  assert.match(fragment, /woodSurfaceNormal\(normal,px,py,woodDx,woodDy\)/);
});

test('all dense and sparse renderer families use entry ray differentials for conditional wood hits', () => {
  for (const tree of [false, true]) for (const sparse of [false, true]) for (const seams of [false, true]) {
    const shaders = rendererShaders(tree, sparse, seams);
    for (const [name, shader] of Object.entries(shaders))
      uniformEntryGate(shader, `${name}/${tree}/${sparse}/${seams}`);
    const fragment = functions(shaders.render).find(fn => fn.name === 'fragment').body;
    assert.match(fragment, /let rayDx=dpdx\(ray\);let rayDy=dpdy\(ray\)/);
    assert.match(fragment, /woodRayMaterial\(at.xzy,roomDx.xzy,roomDy.xzy/);
    assert.match(fragment, /woodRayPixel\(local,localDx,localDy\)/);
    assert.doesNotMatch(fragment, /\bwood(?:Material|Normal|WorldNormal)\(/);
  }
});

test('tangent-plane ray footprints match the perspective hit derivative', () => {
  const dot = (a, b) => a.reduce((sum, value, i) => sum + value * b[i], 0);
  const norm = a => { const len = Math.hypot(...a); return a.map(v => v / len); };
  const eye = [0, 2, -4], eps = 1e-5;
  for (const [rawRay, normal, plane] of [
    [[.2, -.4, 1], [0, 1, 0], [0, 0, 0]],
    [[.3, .1, 1], [0, 0, -1], [0, 0, 0]],
    [[.2, -.3, 1], norm([.3, .7, -.5]), [0, 0, 0]],
  ]) {
    const ray = norm(rawRay), tangent = [1, 0, 0].map((v, i) => v - ray[i] * ray[0]);
    const offset = plane.map((v, i) => v - eye[i]);
    const distance = dot(offset, normal) / dot(ray, normal);
    const analytic = ray.map((v, i) => distance * (tangent[i] - v * dot(normal, tangent) / dot(normal, ray)));
    const hit = sign => {
      const r = norm(ray.map((v, i) => v + sign * eps * tangent[i]));
      const t = dot(offset, normal) / dot(r, normal);
      return r.map((v, i) => eye[i] + v * t);
    };
    const plus = hit(1), minus = hit(-1);
    for (let i = 0; i < 3; i++)
      assert.ok(Math.abs((plus[i] - minus[i]) / (2 * eps) - analytic[i]) < 1e-6);
    assert.ok(Math.abs(dot(analytic, normal)) < 1e-9);
  }
});
