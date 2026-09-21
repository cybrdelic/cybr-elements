import fs from 'node:fs';
import path from 'node:path';
import { SurfaceBuilder } from '../flip-lettering/vendor/src/surface.js';

/**
 * Similarity-core visualizer for OpenAI's 2026 finite-time Navier-Stokes blowup result.
 *
 * This is intentionally NOT presented as a numerical reproduction of the complete proof.
 * It uses the paper's leading asymptotic length/velocity exponents and an axisymmetric,
 * divergence-free surrogate core, then feeds a visible tracer volume through CYBR ELEMENTS'
 * actual particle-kernel surface reconstruction.
 */

const DEFAULT_H = 1 / 128;
const DEFAULT_FRAMES = 9;

function parseArgs(argv) {
  const out = {
    out: 'rendered/navier-stokes-blowup',
    frames: DEFAULT_FRAMES,
    tauMax: 0.32,
    tauMin: 0.018,
    h: DEFAULT_H,
    seed: 260908,
  };
  for (let i = 2; i < argv.length; i++) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === '--out') { out.out = value; i++; }
    else if (key === '--frames') { out.frames = Number(value); i++; }
    else if (key === '--tau-max') { out.tauMax = Number(value); i++; }
    else if (key === '--tau-min') { out.tauMin = Number(value); i++; }
    else if (key === '--h') { out.h = Number(value); i++; }
    else if (key === '--seed') { out.seed = Number(value); i++; }
    else if (key === '--help') {
      console.log('node generate_surface.mjs [--out DIR] [--frames N] [--tau-max X] [--tau-min X] [--h X] [--seed N]');
      process.exit(0);
    } else {
      throw new Error('Unknown argument: ' + key);
    }
  }
  if (!(out.frames >= 2) || !(out.tauMax > out.tauMin && out.tauMin > 0)) {
    throw new Error('Require frames >= 2 and tauMax > tauMin > 0');
  }
  if (!(out.h > 0 && out.h < 0.01)) throw new Error('Require 0 < h < 0.01');
  return out;
}

function makeRng(seed) {
  let state = seed >>> 0;
  return () => {
    let x = state;
    x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
    state = x >>> 0;
    return state / 4294967296;
  };
}

function tauSequence(count, maxTau, minTau) {
  const a = Math.log(maxTau), b = Math.log(minTau);
  return Array.from({ length: count }, (_, i) => Math.exp(a + (b - a) * i / (count - 1)));
}

function scales(tau, h) {
  const A = 0.5 + h;
  const D = 0.5 - h;
  return {
    A,
    D,
    radial: Math.pow(tau, 0.5),
    axial: Math.pow(tau, D),
    tangentialVelocity: Math.pow(tau, -A),
    radialVelocity: Math.pow(tau, -0.5),
    energy: Math.pow(tau, 0.5 - 3 * h),
  };
}

/**
 * Axisymmetric divergence-free surrogate matching the leading core scaling.
 *
 * Poloidal flow comes from psi = alpha r^2 z exp(-(R^2+Z^2)/2):
 *   ur = -(1/r) dpsi/dz
 *   uz =  (1/r) dpsi/dr
 * so div(u_r e_r + u_z e_z) = 0 analytically.
 * Axisymmetric swirl adds no divergence and vanishes linearly on-axis.
 */
function velocity(x, y, z, tau, h) {
  const s = scales(tau, h);
  const r = Math.hypot(x, y);
  const theta = Math.atan2(y, x);
  const R = r / s.radial;
  const Z = z / s.axial;
  const g = Math.exp(-0.5 * (R * R + Z * Z));

  const alpha = 0.56 / tau;
  const ur = -alpha * r * (1 - Z * Z) * g;
  const uz = alpha * z * (2 - R * R) * g;

  const swirlEnvelope = Math.exp(-0.5 * (R * R + 0.72 * Z * Z));
  const utheta = 1.12 * s.tangentialVelocity * R * swirlEnvelope * (1 + 0.055 * Math.tanh(Z));

  const c = Math.cos(theta), sn = Math.sin(theta);
  return [
    ur * c - utheta * sn,
    ur * sn + utheta * c,
    uz,
  ];
}

function rk2Advect(p, tau, h, dt) {
  const v0 = velocity(p[0], p[1], p[2], tau, h);
  const mid = [
    p[0] + 0.5 * dt * v0[0],
    p[1] + 0.5 * dt * v0[1],
    p[2] + 0.5 * dt * v0[2],
  ];
  const vm = velocity(mid[0], mid[1], mid[2], tau, h);
  return [
    p[0] + dt * vm[0],
    p[1] + dt * vm[1],
    p[2] + dt * vm[2],
  ];
}

function buildTracerParticles(tau, h, seed) {
  const rng = makeRng(seed);
  const s = scales(tau, h);
  // The boundary is a tracer, not a resolved molecular/free-surface layer.
  // Keep enough samples for a continuous CYBR ELEMENTS isosurface without
  // turning each similarity snapshot into a multi-million-particle solve.
  const surfaceH = s.radial / 9;
  const spacing = surfaceH * 0.58;
  const zHalf = 3.40 * s.axial;
  const rMax = 1.25 * s.radial;
  const points = [];

  let energy = 0;
  let maxSpeed = 0;
  let speed2Sum = 0;
  let samples = 0;
  const dv = spacing ** 3;

  let layer = 0;
  for (let z = -zHalf + spacing; z <= zHalf - spacing; z += spacing, layer++) {
    const Z = z / zHalf;
    const cap = Math.pow(Math.max(0, 1 - Math.abs(Z)), 0.58);
    const localRadius = rMax * cap;
    const stagger = (layer & 1) ? 0.5 * spacing : 0;

    for (let y = -localRadius + stagger; y <= localRadius; y += spacing) {
      for (let x = -localRadius; x <= localRadius; x += spacing) {
        const r = Math.hypot(x, y);
        if (r > localRadius) continue;
        const theta = Math.atan2(y, x);

        // A small helical modulation makes the tracer boundary expose the swirl.
        // It is a visualization device, not a free-surface claim about the theorem.
        const ridge = 1
          + 0.10 * Math.sin(5 * theta + 2.9 * z / s.axial + 1.7 * Math.log(1 / tau))
          + 0.035 * Math.sin(2 * theta - 4.4 * z / s.axial);
        if (r > localRadius * ridge) continue;

        const jitter = 0.10 * spacing;
        const p = [
          x + (rng() - 0.5) * jitter,
          y + (rng() - 0.5) * jitter,
          z + (rng() - 0.5) * jitter,
        ];

        const v = velocity(p[0], p[1], p[2], tau, h);
        const speed2 = v[0] * v[0] + v[1] * v[1] + v[2] * v[2];
        const speed = Math.sqrt(speed2);
        maxSpeed = Math.max(maxSpeed, speed);
        speed2Sum += speed2;
        energy += 0.5 * speed2 * dv;
        samples++;

        // Similarity snapshot: advect for a fraction of the remaining time.
        const q = rk2Advect(p, tau, h, 0.055 * tau);
        points.push(q);
      }
    }
  }

  return {
    points,
    surfaceH,
    spacing,
    dv,
    energy,
    maxSpeed,
    rmsSpeed: Math.sqrt(speed2Sum / Math.max(1, samples)),
    scales: s,
  };
}

function bounds(points) {
  const lo = [Infinity, Infinity, Infinity];
  const hi = [-Infinity, -Infinity, -Infinity];
  for (const p of points) {
    for (let k = 0; k < 3; k++) {
      lo[k] = Math.min(lo[k], p[k]);
      hi[k] = Math.max(hi[k], p[k]);
    }
  }
  return { lo, hi };
}

function writeObj(file, mesh, offset) {
  const lines = ['# CYBR ELEMENTS particle-kernel isosurface'];
  const p = mesh.positions;
  const n = mesh.normals;
  for (let i = 0; i < p.length; i += 3) {
    lines.push('v ' + (p[i] - offset[0]).toPrecision(9) + ' ' +
      (p[i + 1] - offset[1]).toPrecision(9) + ' ' +
      (p[i + 2] - offset[2]).toPrecision(9));
  }
  for (let i = 0; i < n.length; i += 3) {
    lines.push('vn ' + n[i].toPrecision(9) + ' ' + n[i + 1].toPrecision(9) + ' ' + n[i + 2].toPrecision(9));
  }
  const idx = mesh.indices;
  for (let i = 0; i < idx.length; i += 3) {
    const a = idx[i] + 1, b = idx[i + 1] + 1, c = idx[i + 2] + 1;
    lines.push('f ' + a + '//' + a + ' ' + b + '//' + b + ' ' + c + '//' + c);
  }
  fs.writeFileSync(file, lines.join('\n') + '\n');
}

function main() {
  const args = parseArgs(process.argv);
  const out = path.resolve(args.out);
  const framesDir = path.join(out, 'surfaces');
  fs.mkdirSync(framesDir, { recursive: true });

  const taus = tauSequence(args.frames, args.tauMax, args.tauMin);
  const metrics = [];
  const config = {
    source: 'OpenAI 2026 finite-time Navier-Stokes blowup leading-core visualization',
    disclaimer: 'Uses the paper\'s leading core exponents (lr~tau^1/2, lz~tau^(1/2-h), |u_theta|,|u_z|~tau^(-1/2-h), |u_r|~tau^-1/2, energy~tau^(1/2-3h)) with a divergence-free surrogate similarity profile and a visible tracer boundary. It is not the paper\'s exact E/U/Pi profile, annular pulses, forcing, or a literal liquid free surface.',
    h: args.h,
    A: 0.5 + args.h,
    D: 0.5 - args.h,
    tauMax: args.tauMax,
    tauMin: args.tauMin,
    frames: args.frames,
    seed: args.seed,
    noImageGeneration: true,
    cybrElementsSurface: 'work/flip-lettering/vendor/src/surface.js::SurfaceBuilder',
  };
  fs.writeFileSync(path.join(out, 'config.json'), JSON.stringify(config, null, 2));

  for (let frame = 0; frame < taus.length; frame++) {
    const tau = taus[frame];
    const tracer = buildTracerParticles(tau, args.h, args.seed + frame * 7919);
    const b = bounds(tracer.points);
    const pad = tracer.surfaceH * 4;
    const extent = [0, 1, 2].map(k => (b.hi[k] - b.lo[k]) + 2 * pad);
    const offset = [0, 1, 2].map(k => -b.lo[k] + pad);
    const packed = new Float32Array(tracer.points.length * 3);
    for (let i = 0; i < tracer.points.length; i++) {
      packed[3 * i] = tracer.points[i][0] + offset[0];
      packed[3 * i + 1] = tracer.points[i][1] + offset[1];
      packed[3 * i + 2] = tracer.points[i][2] + offset[2];
    }

    const builder = new SurfaceBuilder({ h: tracer.surfaceH, extent });
    builder.density(packed, tracer.points.length);
    const mesh = builder.mesh(packed, tracer.points.length, null);
    const file = path.join(framesDir, String(frame).padStart(4, '0') + '.obj');
    writeObj(file, mesh, offset);

    const row = {
      frame,
      tau,
      t: 1 - tau,
      radialScale: tracer.scales.radial,
      axialScale: tracer.scales.axial,
      aspectRatio: tracer.scales.axial / tracer.scales.radial,
      characteristicTangentialVelocity: tracer.scales.tangentialVelocity,
      characteristicRadialVelocity: tracer.scales.radialVelocity,
      expectedEnergyScale: tracer.scales.energy,
      sampledMaxSpeed: tracer.maxSpeed,
      sampledRmsSpeed: tracer.rmsSpeed,
      kineticEnergyProxy: tracer.energy,
      particleCount: tracer.points.length,
      meshVertices: mesh.positions.length / 3,
      meshTriangles: mesh.indices.length / 3,
      detachedDrops: mesh.drops.length / 3,
      reconstruction: builder.lastMeshStats,
      surfaceH: tracer.surfaceH,
      particleSpacing: tracer.spacing,
      obj: path.relative(out, file).replaceAll('\\', '/'),
    };
    metrics.push(row);
    fs.writeFileSync(path.join(out, 'metrics.json'), JSON.stringify(metrics, null, 2));
    console.log(JSON.stringify(row));
  }

  fs.writeFileSync(path.join(out, 'manifest.json'), JSON.stringify({
    complete: true,
    frames: metrics.length,
    config: 'config.json',
    metrics: 'metrics.json',
    surfaces: 'surfaces/',
    noImageGeneration: true,
  }, null, 2));
}

main();
