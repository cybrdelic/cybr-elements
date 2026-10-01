import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const root = resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load = file => import(pathToFileURL(resolve(root, file)).href);
const { PowerCastPool } = await load('fire-abilities.js');
const { POWER_DEFINITIONS } = await load('fire-power-definitions.js');
const { FIRE_PRESETS } = await load('pyro-gpu/presets.js');
const { powerDirection, powerSourceWGSL } = await load('fire-powers.js');
const domains = {
  volume: { min: [-2.84, .14, -2.84], max: [2.84, 5.76, 2.84] },
  original: { min: [-3.84, .14, -1.92], max: [3.84, 6.63, 1.92] },
};
const margin = d => (d.impactMargin || 0) +
  (['meteor-barrage', 'cinder-scatter', 'ember-orbit'].includes(d.id) ? .8 : 0);
const distance = actor => Math.hypot(...actor.target.map((v, i) => v - actor.origin[i]));
function hardLimits(actor, bounds, label) {
  assert.ok(actor, label + ' accepted');
  assert.ok(distance(actor) <= actor.definition.range * actor.scale + 1e-9, label + ' range');
  for (let i = 0; i < 3; i++) {
    assert.ok(Number.isFinite(actor.target[i]), label + ' finite');
    assert.ok(actor.target[i] >= bounds.min[i] - 1e-10 && actor.target[i] <= bounds.max[i] + 1e-10,
      label + ' domain axis ' + i);
  }
  if (actor.definition.floor) assert.equal(actor.target[1], .14, label + ' floor');
}

test('all authored defaults keep their full feasible impact inset and hard travel bounds in both domains', () => {
  for (const [engine, bounds] of Object.entries(domains)) {
    for (const preset of FIRE_PRESETS.filter(p => p.power)) {
      const definition = POWER_DEFINITIONS.find(d => d.id === preset.id);
      const actor = new PowerCastPool({ bounds }).cast(preset.id, {
        origin: preset.source, direction: powerDirection({ heading: definition.defaultHeading, elevation: 9 }),
      });
      const label = engine + ' ' + preset.id;
      hardLimits(actor, bounds, label);
      const reserve = margin(definition);
      for (const i of [0, 2]) {
        const mid = (bounds.min[i] + bounds.max[i]) * .5;
        assert.ok(actor.target[i] >= Math.min(mid, bounds.min[i] + reserve) - 1e-10, label + ' inset low');
        assert.ok(actor.target[i] <= Math.max(mid, bounds.max[i] - reserve) + 1e-10, label + ' inset high');
      }
      const topReserve = reserve + (definition.id === 'flame-serpent' ? .35 : 0);
      if (!definition.floor) assert.ok(actor.target[1] <= Math.max(bounds.min[1], bounds.max[1] - topReserve) + 1e-10,
        label + ' impact ceiling');
    }
  }
});

test('corner and steep pointer aims retain range and domain even when the desired impact inset is infeasible', () => {
  for (const [engine, bounds] of Object.entries(domains)) for (const definition of POWER_DEFINITIONS) {
    for (const scale of [.5, 1, 1.25, 2]) for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
      const origin = [sx < 0 ? bounds.min[0] : bounds.max[0],
        definition.floor ? .18 : bounds.max[1] - .05,
        sz < 0 ? bounds.min[2] : bounds.max[2]];
      const actor = new PowerCastPool({ bounds }).cast(definition.id, {
        origin, target: [-sx * 999, 999, -sz * 999], direction: [-sx, .1, -sz], scale,
      });
      hardLimits(actor, bounds, engine + ' ' + definition.id + ' scale ' + scale);
    }
  }
  const actor = new PowerCastPool().cast('fireball', {
    origin: [-2.84, .35, -2.84], target: [2.84, 5.76, 2.84], direction: [1, 0, 0],
  });
  assert.ok(Math.abs(distance(actor) - 3.1) < 1e-8, 'the reported 3.56073-unit flight is now bounded');
  assert.ok(actor.target[0] + 2.84 > 2.19 && actor.target[2] + 2.84 > 2.19,
    'only the necessary fraction of the 2.2-unit impact reservation is relinquished');
});

test('eight launch headings and low, level and steep elevation keep every ability inside its travel budget', () => {
  for (const [engine, bounds] of Object.entries(domains)) {
    for (const preset of FIRE_PRESETS.filter(p => p.power)) {
      for (const heading of [-180, -135, -90, -45, 0, 45, 90, 135]) for (const elevation of [-30, 0, 80]) {
        const actor = new PowerCastPool({ bounds }).cast(preset.id, {
          origin: preset.source, direction: powerDirection({ heading, elevation }),
        });
        hardLimits(actor, bounds, engine + ' ' + preset.id + ' heading ' + heading + ' elevation ' + elevation);
      }
    }
  }
});

test('high held aims reserve ceiling clearance and finite cast targets remain immutable through later casts', () => {
  const pool = new PowerCastPool({ bounds: domains.volume });
  const scratch = pool.slots.map(s => [s.clampLo, s.clampHi, s.clampClosest]);
  const actor = pool.cast('fireball', { origin: [0, 5.6, 0], direction: [0, 1, 0], held: true });
  assert.equal(pool.aim([0, 999, 0], [0, 1, 0]), true);
  assert.ok(actor.target[1] <= 5.76 - 2.2 + 1e-10, 'ceiling reserved on the held aim path');
  pool.release();
  const captured = [...actor.target];
  pool.cast('cinder-scatter', { origin: [-1.8, 1.1, 0], direction: [1, .1, 0] });
  assert.deepEqual([...actor.target], captured, 'new cast cannot redirect the already released fireball');
  const uniform = new Float32Array(96).fill(77);
  pool.write(uniform, 32);
  assert.ok(uniform.slice(0, 32).every(v => v === 77));
  for (let i = 0; i < 3; i++) assert.equal(uniform[44 + i], Math.fround(captured[i]));
  assert.equal(uniform.length, 96, 'four existing 16-float slots retain the upload layout');
  const serpent = pool.cast('flame-serpent', {
    origin: [0, 5.6, 0], direction: [0, 1, 0], target: [0, 999, 0],
  });
  hardLimits(serpent, domains.volume, 'high serpent aim');
  assert.ok(serpent.target[1] + .35 <= 5.76 - 2.2 + 1e-10,
    'the serpent burst center, rather than the lower target alone, keeps ceiling clearance');
  const defaultSerpent = pool.cast('flame-serpent', {
    origin: [-1.8, 1.1, 0], direction: powerDirection({ heading: 0, elevation: 9 }),
  });
  assert.ok(Math.abs(defaultSerpent.target[0] - .64) < 1e-10);
  assert.ok(Math.abs(defaultSerpent.target[1] - (1.1 + 3.4 * Math.sin(9 * Math.PI / 180))) < 1e-10,
    'the added ceiling offset does not change the existing default cast');
  assert.equal(defaultSerpent.target[2], 0);
  for (let i = 0; i < pool.slots.length; i++) {
    for (const [axis, key] of ['clampLo', 'clampHi', 'clampClosest'].entries()) {
      assert.equal(pool.slots[i][key], scratch[i][axis], 'clamping reuses its constructor-owned scratch');
      assert.equal(pool.slots[i][key].length, 3);
    }
  }
});

test('continuous aim updates reserve impacts and impossible launch locations are rejected atomically', () => {
  const pool = new PowerCastPool({ bounds: domains.volume });
  const actor = pool.cast('dragon-breath', { origin: [-1.8, 1.05, 0], direction: [1, 0, 0] });
  assert.equal(pool.updateContinuous({ direction: [0, 1, 0], strength: 1.7 }), true);
  hardLimits(actor, domains.volume, 'continuous vertical aim');
  assert.ok(actor.target[1] <= 5.76 - 2.2 + 1e-10);
  const before = pool.snapshot();
  assert.equal(pool.cast('fireball', { origin: [50, 1, 0], direction: [-1, 0, 0] }), null);
  assert.deepEqual(pool.snapshot(), before);
  assert.equal(pool.move([50, 1, 0], [0, 1, 0], { direction: [-1, 0, 0], strength: .5 }), false);
  assert.deepEqual(pool.snapshot(), before);
  assert.equal(pool.updateContinuous({ scale: .25 }), true);
  hardLimits(actor, domains.volume, 'scale-only continuous update');
  const edge = pool.cast('dragon-breath', { origin: [3.1, 1, 0], direction: [-1, 0, 0] });
  assert.ok(edge, 'ordinary near-edge clicks outside the target inset can still reach the domain');
  const edgeBefore = pool.snapshot();
  assert.equal(pool.updateContinuous({ scale: .05, strength: .25 }), false);
  assert.deepEqual(pool.snapshot(), edgeBefore, 'an impossible scale change cannot partially edit the source');
});

test('the shared tilted crescent retains fuel inside shallow side walls across every rotated default cast', () => {
  const axis = powerSourceWGSL.match(/fn abilityCrescentAxis\(side:vec3f\)->vec3f\{return side\*([.\d]+)\+vec3f\(0,([.\d]+),0\);\}/);
  assert.ok(axis, 'the shipped blade axis is an explicit shared transform');
  const lateral = Number(axis[1]), vertical = Number(axis[2]);
  assert.ok(Math.abs(Math.hypot(lateral, vertical) - 1) < 1e-7, 'tilting preserves blade length');
  for (const signature of ['blade*(.75*sin(u*6.2831853))+up*.55',
    'let width:f32=.45+.28*outbound', 'abilityRibbon(q,c-blade*width,middle,.15,v,1.3,clock)',
    'abilityCapsule(q,c-blade*width,c+f*.15,.49,pad)']) {
    assert.ok(powerSourceWGSL.includes(signature), 'update copied shape proof if source changes: ' + signature);
  }
  const preset = FIRE_PRESETS.find(p => p.id === 'flame-crescent');
  const physical = { volume: { min: [-3, 0, -3], max: [3, 6, 3] },
    original: { min: [-4, -1.05, -2], max: [4, 6.95, 2] } };
  const fuelRadius = .15 * 2.8;
  for (const [engine, bounds] of Object.entries(domains)) {
    for (let heading = -180; heading < 180; heading += 5) {
      const pool = new PowerCastPool({ bounds });
      const actor = pool.cast(preset.id, { origin: preset.source, direction: powerDirection({ heading, elevation: 9 }) });
      const aim = actor.target.map((v, i) => v - actor.origin[i]), horizontal = Math.hypot(aim[0], aim[2]);
      const forward = horizontal < .01 ? [1, 0, 0] : [aim[0] / horizontal, 0, aim[2] / horizontal];
      const blade = [-forward[2] * lateral, vertical, forward[0] * lateral];
      const reach = Math.max(.2, Math.min(2.8, horizontal - .3));
      for (let step = 0; step <= 300; step++) {
        const u = step / 300, outbound = Math.sin(u * 3.14159265), width = .45 + .28 * outbound;
        const center = actor.origin.map((v, i) => v + forward[i] * reach * outbound +
          blade[i] * .75 * Math.sin(u * 6.2831853) + (i === 1 ? .55 : 0));
        const points = [center.map((v, i) => v - blade[i] * width),
          center.map((v, i) => v + forward[i] * .15), center.map((v, i) => v + blade[i] * width)];
        for (const point of points) for (const i of [0, 2]) {
          assert.ok(point[i] - fuelRadius >= physical[engine].min[i] - 1e-8 &&
            point[i] + fuelRadius <= physical[engine].max[i] + 1e-8,
          engine + ' heading ' + heading + ' shape time ' + u + ' side wall ' + i);
        }
      }
      actor.age = 1;
      const sourceSpeedBound = Math.hypot(Math.hypot(2.8 * Math.PI / 1.4,
        Math.hypot(lateral, vertical) * .75 * 2 * Math.PI / 1.4), 12 * fuelRadius);
      assert.ok(sourceSpeedBound <= pool.speedFloor(), 'the near-unit tilt retains its pre-telemetry speed guard');
    }
  }
});
