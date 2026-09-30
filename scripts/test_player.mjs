import assert from 'node:assert/strict';
import { before, after, test } from 'node:test';
import { spawn } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const root = new URL('../', import.meta.url);
const catalogue = JSON.parse(await readFile(new URL('outputs/cybrdelic-type/elements/motion/bending/sigils/02/films.json', root)));
const results = new URL('test-results/', root);
let server, browser, base;

before(async () => {
  await mkdir(results, { recursive: true });
  server = spawn(process.env.PYTHON || 'python', ['scripts/serve.py', '--port', '0'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'] });
  base = await new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Showcase server did not start')), 10000);
    server.once('error', reject);
    server.once('exit', code => reject(new Error(`Showcase server exited ${code}`)));
    server.stdout.on('data', chunk => {
      const match = chunk.toString().match(/http:\/\/127\.0\.0\.1:\d+/);
      if (match) { clearTimeout(timeout); resolve(match[0]); }
    });
  });
  browser = await chromium.launch({
    ...(process.env.CHROME_EXECUTABLE_PATH ? { executablePath: process.env.CHROME_EXECUTABLE_PATH } : {}),
    args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'], headless: true
  });
});

after(async () => {
  await browser?.close();
  if (server && server.exitCode === null) {
    const exited = new Promise(resolve => server.once('exit', resolve));
    server.kill();
    await exited;
  }
});

async function loaded(page, asset) {
  await page.waitForFunction(file => {
    const video = document.getElementById('film');
    return video.readyState >= 2 && video.currentSrc.endsWith('/' + file) && !video.error;
  }, asset.file, { timeout: 20000 });
}

async function open(options = {}) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce', ...options });
  const page = await context.newPage();
  return { context, page };
}

test('all seven current films and three previous versions decode, seek and play', { timeout: 120000 }, async () => {
  const { context, page } = await open();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    for (const [element, item] of Object.entries(catalogue.elements)) {
      for (const version of ['current', 'previous']) {
        if (!item[version]) continue;
        const asset = item[version];
        await page.goto(`${base}/?element=${element}&version=${version}`);
        await loaded(page, asset);
        const info = await page.locator('#film').evaluate(video => ({ width: video.videoWidth, height: video.videoHeight, duration: video.duration, paused: video.paused }));
        assert.equal(info.width, asset.width);
        assert.equal(info.height, asset.height);
        assert.ok(Math.abs(info.duration - asset.duration) < .05);
        assert.equal(info.paused, true, 'Reduced motion must suppress autoplay');
        assert.ok((await page.locator('#download').getAttribute('href')).endsWith(asset.file));
        await page.locator('#film').evaluate(async video => { video.currentTime = 4; await video.play(); });
        await page.waitForFunction(() => document.getElementById('film').currentTime > 4.05);
        await page.locator('#film').evaluate(video => video.pause());
      }
    }
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
});

test('selection, revisions, comparison and back navigation preserve URL state', async () => {
  const { context, page } = await open();
  try {
    await page.goto(`${base}/?element=water`);
    await loaded(page, catalogue.elements.water.current);
    await page.locator('#previous').click();
    await loaded(page, catalogue.elements.water.previous);
    assert.match(page.url(), /version=previous/);
    await page.locator('#reference').click();
    assert.equal(await page.locator('#artwork').isVisible(), true);
    assert.match(page.url(), /compare=1/);
    await page.locator('[data-element="ice"]').click();
    await loaded(page, catalogue.elements.ice.current);
    assert.equal(await page.locator('#previous').isVisible(), false);
    await page.goBack();
    await loaded(page, catalogue.elements.water.previous);
    assert.equal(await page.locator('#artwork').isVisible(), true);
    assert.equal(await page.locator('#previous').getAttribute('aria-pressed'), 'true');
    await page.reload();
    await loaded(page, catalogue.elements.water.previous);
    assert.equal(await page.locator('#artwork').isVisible(), true);
  } finally { await context.close(); }
});

test('rapid switching ends on the requested film without stale metadata', async () => {
  const { context, page } = await open();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base);
    await loaded(page, catalogue.elements.fire.current);
    await page.evaluate(() => {
      for (const name of ['water', 'ice', 'earth', 'lava', 'lightning']) document.querySelector(`[data-element="${name}"]`).click();
    });
    await loaded(page, catalogue.elements.lightning.current);
    assert.equal(await page.locator('[data-element="lightning"]').getAttribute('aria-current'), 'true');
    assert.match(await page.locator('#element-title').textContent(), /Lightning/);
    assert.match(await page.locator('#media-meta').textContent(), /10\.0 s/);
    assert.deepEqual(errors, []);
  } finally { await context.close(); }
});

test('missing film reports a recoverable error and retry succeeds', async () => {
  const { context, page } = await open();
  try {
    const route = '**/ice-02.mp4';
    await page.route(route, route => route.fulfill({ status: 404, body: 'Missing' }));
    await page.goto(`${base}/?element=ice`);
    await page.locator('#failure-panel').waitFor({ state: 'visible' });
    assert.match(await page.locator('#playback-state').textContent(), /unavailable/i);
    await page.unroute(route);
    await page.locator('#retry').click();
    await loaded(page, catalogue.elements.ice.current);
    assert.equal(await page.locator('#failure-panel').isVisible(), false);
  } finally { await context.close(); }
});

test('mobile layout, keyboard access and cold-load budget', async () => {
  const { context, page } = await open({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  const errors = [], failed = [], media = new Set();
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    if (response.status() >= 400) failed.push(response.url());
    if (response.url().endsWith('.mp4')) media.add(response.url());
  });
  try {
    await page.goto(base);
    await loaded(page, catalogue.elements.fire.current);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.locator('[data-element="fire"]').focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('[data-element="water"]').evaluate(element => element === document.activeElement), true);
    await page.keyboard.press('Enter');
    await loaded(page, catalogue.elements.water.current);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: new URL('mobile.png', results).pathname, fullPage: true });
    // Selecting Water may fetch Water; startup must not preload the remaining five films.
    assert.ok(media.size <= 2, `Unexpected media preload: ${[...media]}`);
    const metrics = await page.evaluate(() => ({
      domNodes: document.querySelectorAll('*').length,
      resources: performance.getEntriesByType('resource').map(r => ({ name: r.name, bytes: r.transferSize, duration: r.duration })),
      overflow: document.documentElement.scrollWidth - innerWidth
    }));
    assert.ok(metrics.domNodes < 250, 'Static player grew beyond a reasonable DOM budget');
    assert.deepEqual(errors, []);
    assert.deepEqual(failed, []);
    await writeFile(new URL('performance.json', results), JSON.stringify(metrics, null, 2));
  } finally { await context.close(); }
});

test('fonts and bundled font download work on a clean checkout', async () => {
  const { context, page } = await open();
  const failed = [];
  page.on('response', response => { if (response.status() >= 400) failed.push(response.url()); });
  try {
    await page.goto(`${base}/typefaces/`);
    await page.evaluate(() => document.fonts.ready);
    assert.equal(await page.evaluate(() => document.fonts.check('90px "Cybrdelic Cut"') && document.fonts.check('90px "Cybrdelic Sigil"')), true);
    const archive = await context.request.get(`${base}/typefaces/Cybrdelic-Fonts.zip`);
    assert.equal(archive.status(), 200);
    assert.ok((await archive.body()).length > 1000);
    assert.deepEqual(failed, []);
  } finally { await context.close(); }
});

test('capture a reproducible desktop frame for visual review', async () => {
  const { context, page } = await open();
  try {
    await page.goto(`${base}/?element=ice`);
    await loaded(page, catalogue.elements.ice.current);
    await page.locator('#film').evaluate(video => new Promise(resolve => {
      video.addEventListener('seeked', () => requestAnimationFrame(() => requestAnimationFrame(resolve)), { once: true });
      video.currentTime = 4.6;
    }));
    const geometry = await page.evaluate(() => {
      const bounds = selector => { const { x, y, width, height } = document.querySelector(selector).getBoundingClientRect(); return { x, y, width, height }; };
      return { stage: bounds('.stage'), rail: bounds('.elements'), details: bounds('.element-details'), viewport: innerWidth };
    });
    assert.ok(Math.abs(geometry.stage.width / geometry.stage.height - 16 / 9) < .01);
    assert.ok(geometry.stage.y + geometry.stage.height <= geometry.rail.y);
    assert.ok(geometry.rail.y + geometry.rail.height <= geometry.details.y);
    assert.ok(geometry.stage.x >= 0 && geometry.stage.x + geometry.stage.width <= geometry.viewport);
    await writeFile(new URL('layout.json', results), JSON.stringify(geometry, null, 2));
    await page.screenshot({ path: new URL('desktop.png', results).pathname, fullPage: true });
  } finally { await context.close(); }
});

test('archived water reports missing optional assets and fits a 320px mobile viewport', async () => {
  const { context, page } = await open({ viewport: { width: 320, height: 740 }, isMobile: true, hasTouch: true });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.route('**/elements/water/cache/01/**', route => route.fulfill({ status: 404, body: 'Missing optional archive' }));
    await page.goto(`${base}/elements/water/?variant=01`);
    await page.locator('#cache-error').waitFor({ state: 'visible' });
    assert.equal(await page.locator('#play').isDisabled(), true);
    assert.equal(await page.locator('#timeline').isDisabled(), true);
    assert.match(await page.locator('#cache-error').textContent(), /python scripts\/fetch_assets\.py --site/);
    assert.equal(await page.evaluate(() => window.WATER.ready), false);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: new URL('archive-mobile.png', results).pathname, fullPage: true });
  } finally { await context.close(); }
});

function syntheticTriangle(extent) {
  // Actual CFR4: three vertices, one face, no particles, a 1x1 RG8 caustic.
  const bytes = Buffer.alloc(32 + 3 * 13 + 12 + 2);
  const header = [0x43465234, 3, 1, 0, 0, 0, 1, 1];
  header.forEach((value, index) => bytes.writeUInt32LE(value, index * 4));
  const points = [[1.3, .3, .9], [2.6, .3, .9], [1.95, 1.2, .9]];
  let offset = 32;
  points.flat().forEach((value, index) => bytes.writeUInt16LE(Math.round(value / extent[index % 3] * 65535), offset + index * 2));
  offset += 18;
  [0, 0, 32767, 0, 0, 32767, 0, 0, 32767].forEach((value, index) => bytes.writeInt16LE(value, offset + index * 2));
  offset += 18 + 3;
  [0, 1, 2].forEach((value, index) => bytes.writeUInt32LE(value, offset + index * 4));
  return bytes;
}

test('raw CFR4 snapshots render in the archive and support scrubbing, view modes and orbit without false playback', async () => {
  const { context, page } = await open();
  const errors = [], requested = [];
  page.on('pageerror', error => errors.push(error.message));
  const config = { extent: [4.2, 1.8, 1.8], h: .024, obstacles: [], nameKey: 'sigil', rasterProfile: 'repair' };
  const manifest = { config, playbackFps: 24, frames: Array.from({ length: 96 }, (_, frame) => ({ frame, colliders: [] })) };
  const mesh = syntheticTriangle(config.extent);
  try {
    await page.route('**/elements/motion/water/cache/01/**', route => {
      const url = new URL(route.request().url());
      if (url.pathname.endsWith('/manifest.json')) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(manifest) });
      const frame = Number(url.pathname.match(/\/(\d+)\.mesh\.gz$/)?.[1]);
      requested.push(frame);
      // Emulate a host that already decoded Content-Encoding:gzip.
      return route.fulfill({ status: 200, contentType: 'application/octet-stream', body: mesh });
    });
    await page.goto(`${base}/elements/motion/water/?variant=01`);
    await page.waitForFunction(() => window.WATER?.ready === true);
    assert.equal(await page.evaluate(() => window.WATER.current), 8);
    assert.equal(await page.locator('#play').isDisabled(), true);
    assert.equal(await page.locator('#timeline').getAttribute('max'), '6');
    assert.match(await page.locator('#archive-note').textContent(), /7 retained review snapshots/);
    assert.equal(await page.locator('#cache-error').isVisible(), false);
    const initial = await page.evaluate(() => window.WATER.renderer.info());
    assert.equal(initial.vertices, 3);
    assert.equal(initial.triangles, 1);
    assert.equal(initial.glError, 0);
    await page.locator('#timeline').evaluate(input => { input.value = '1'; input.dispatchEvent(new Event('input', { bubbles: true })); });
    await page.waitForFunction(() => window.WATER.current === 20);
    await page.evaluate(() => document.activeElement.blur());
    await page.keyboard.press('ArrowRight');
    await page.waitForFunction(() => window.WATER.current === 32);
    await page.locator('#mode').selectOption('wire');
    assert.equal(await page.evaluate(() => window.WATER.renderer.info().mode), 'wire');
    await page.mouse.move(800, 400);
    await page.mouse.down();
    await page.mouse.move(850, 425, { steps: 3 });
    await page.mouse.up();
    assert.equal(await page.evaluate(() => Boolean(window.WATER.renderer.orbit)), true);
    await page.locator('#reset-camera').click();
    assert.equal(await page.evaluate(() => window.WATER.renderer.orbit), null);
    assert.equal(await page.evaluate(() => window.WATER.renderer.info().glError), 0);
    assert.deepEqual(requested, [8, 20, 32]);
    assert.deepEqual(errors, []);
    await page.screenshot({ path: new URL('archive-synthetic.png', results).pathname, fullPage: true });
  } finally { await context.close(); }
});
