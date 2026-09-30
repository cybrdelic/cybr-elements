/* Checked mesh-cache playback shared by the archived water viewers. */
(function (global) {
  'use strict';

  const MAX_FRAME_BYTES = 256 * 1024 * 1024;
  const MAGICS = [0x43465231, 0x43465232, 0x43465233, 0x43465234];

  function validateConfig(config) {
    if (!config || !Array.isArray(config.extent) || config.extent.length !== 3 ||
        !config.extent.every(value => Number.isFinite(value) && value > 0 && value <= 3.4028234663852886e38)) {
      throw new Error('Water manifest requires three positive finite domain extents.');
    }
    if (!Number.isFinite(config.h) || config.h <= 0) {
      throw new Error('Water manifest requires a positive finite grid spacing.');
    }
  }

  function validateManifest(manifest) {
    validateConfig(manifest?.config);
    if (!Array.isArray(manifest.frames) || !manifest.frames.length ||
        !manifest.frames.every(frame => frame && typeof frame === 'object')) {
      throw new Error('Water manifest contains no usable frame records.');
    }
    if (manifest.playbackFps !== undefined &&
        (!Number.isFinite(manifest.playbackFps) || manifest.playbackFps <= 0)) {
      throw new Error('Water manifest has an invalid playback frame rate.');
    }
    return manifest;
  }

  function frameNumber(value, count) {
    const number = Number(value);
    if (!Number.isFinite(number)) throw new Error('Frame must be a finite number.');
    return Math.max(0, Math.min(count - 1, Math.floor(number)));
  }

  function parseMesh(buffer, config) {
    validateConfig(config);
    if (!(buffer instanceof ArrayBuffer) || buffer.byteLength < 24 || buffer.byteLength > MAX_FRAME_BYTES) {
      throw new Error('Mesh cache has an invalid or truncated header.');
    }
    const view = new DataView(buffer);
    const version = MAGICS.indexOf(view.getUint32(0, true)) + 1;
    if (!version) throw new Error('Mesh cache has an unsupported format signature.');
    const headerBytes = version >= 3 ? 32 : 24;
    if (buffer.byteLength < headerBytes) throw new Error('Mesh cache has a truncated caustic header.');
    const nv = view.getUint32(4, true), nf = view.getUint32(8, true);
    const nd = view.getUint32(12, true), nw = view.getUint32(16, true), np = view.getUint32(20, true);
    const cw = version >= 3 ? view.getUint32(24, true) : 0;
    const ch = version >= 3 ? view.getUint32(28, true) : 0;
    if ((cw === 0) !== (ch === 0)) throw new Error('Mesh cache has inconsistent caustic dimensions.');
    const expectedBytes = headerBytes + nv * (version >= 2 ? 13 : 12) + nf * 12 +
      nd * (version === 4 ? 10 : 6) + nw * 24 + np * 6 + cw * ch * 2;
    // Check the complete payload before allocating arrays from untrusted counts.
    if (!Number.isSafeInteger(expectedBytes) || expectedBytes > MAX_FRAME_BYTES || expectedBytes !== buffer.byteLength) {
      throw new Error('Mesh cache byte length does not match its declared geometry.');
    }
    let offset = headerBytes;
    function positions(count) {
      const values = new Float32Array(count * 3);
      for (let i = 0; i < values.length; i++) {
        values[i] = view.getUint16(offset + i * 2, true) / 65535 * config.extent[i % 3];
      }
      offset += count * 6;
      return values;
    }
    const vertices = positions(nv), normals = new Float32Array(nv * 3);
    for (let i = 0; i < normals.length; i++) normals[i] = Math.max(-1, view.getInt16(offset + i * 2, true) / 32767);
    offset += nv * 6;
    const foam = new Float32Array(nv);
    if (version >= 2) {
      for (let i = 0; i < nv; i++) foam[i] = view.getUint8(offset + i) / 255;
      offset += nv;
    }
    const indices = new Uint32Array(nf * 3);
    for (let i = 0; i < indices.length; i++) {
      indices[i] = view.getUint32(offset + i * 4, true);
      if (indices[i] >= nv) throw new Error('Mesh cache contains an out-of-range triangle index.');
    }
    offset += nf * 12;
    const drops = positions(nd), dropRadii = new Float32Array(nd);
    if (version === 4) {
      for (let i = 0; i < nd; i++) {
        const radius = view.getFloat32(offset + i * 4, true);
        if (!Number.isFinite(radius) || radius < 0) throw new Error('Mesh cache contains an invalid droplet radius.');
        dropRadii[i] = radius;
      }
      offset += nd * 4;
    } else {
      dropRadii.fill(config.h * Math.cbrt(3 / (32 * Math.PI)));
    }
    const white = new Float32Array(nw * 6);
    for (let i = 0; i < white.length; i++) {
      const value = view.getFloat32(offset + i * 4, true);
      if (!Number.isFinite(value)) throw new Error('Mesh cache contains a non-finite whitewater value.');
      if (i % 6 === 3 && value < 0) throw new Error('Mesh cache contains a negative whitewater radius.');
      white[i] = value;
    }
    offset += nw * 24;
    const diagnostic = positions(np);
    const caustic = cw ? new Uint8Array(buffer, offset, cw * ch * 2) : null;
    return { positions: vertices, normals, foam, indices, drops, dropRadii, white,
      diagnostic, caustic, causticWidth: cw, causticHeight: ch };
  }

  async function decompressMesh(response, config) {
    if (!response.ok) {
      const error = new Error(`Water geometry is unavailable (HTTP ${response.status}).`);
      error.missingAssets = response.status === 404;
      throw error;
    }
    if (!response.body) throw new Error('Water geometry response has no body.');
    // Fetch already removes Content-Encoding:gzip. A server may therefore
    // return a decoded CFR payload even though the URL still ends in .gz.
    // Probe a clone so both raw and compressed bodies stay streamed and bounded.
    const probe = response.clone().body.getReader();
    const prefix = new Uint8Array(4);
    let prefixBytes = 0;
    try {
      while (prefixBytes < prefix.length) {
        const { value, done } = await probe.read();
        if (done) break;
        const count = Math.min(value.byteLength, prefix.length - prefixBytes);
        prefix.set(value.subarray(0, count), prefixBytes);
        prefixBytes += count;
      }
    } finally {
      // A tee's cancel promise waits for its other branch; do not await it
      // before consuming the original body.
      void probe.cancel().catch(() => {});
      probe.releaseLock();
    }
    const decoded = prefixBytes === 4 && MAGICS.includes(new DataView(prefix.buffer).getUint32(0, true));
    if (!decoded && (prefix[0] !== 0x1f || prefix[1] !== 0x8b)) {
      throw new Error('Water geometry is neither a gzip archive nor a supported mesh cache. Check the archive and server paths.');
    }
    if (!decoded && typeof DecompressionStream !== 'function') {
      throw new Error('This browser cannot decompress water caches. Open the current rendered films or use a recent browser.');
    }
    // Cap decompressed size as well as the packed header, so corrupt gzip data
    // cannot grow without bound before it reaches the geometry parser.
    const reader = (decoded ? response.body : response.body.pipeThrough(new DecompressionStream('gzip'))).getReader();
    const chunks = [];
    let bytes = 0;
    try {
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        bytes += value.byteLength;
        if (bytes > MAX_FRAME_BYTES) throw new Error('Water geometry exceeds the frame memory limit.');
        chunks.push(value);
      }
    } catch (error) {
      await reader.cancel().catch(() => {});
      throw error;
    } finally {
      reader.releaseLock();
    }
    const buffer = new Uint8Array(bytes);
    let offset = 0;
    for (const chunk of chunks) { buffer.set(chunk, offset); offset += chunk.byteLength; }
    return parseMesh(buffer.buffer, config);
  }

  class CachePlayer {
    constructor({ manifest, renderer, loadMesh, onFrame = () => {} }) {
      this.manifest = validateManifest(manifest);
      this.renderer = renderer;
      this.loadMesh = loadMesh;
      this.onFrame = onFrame;
      this.current = 0;
      this.sequence = 0;
      this.pending = null;
      this.memo = new Map();
      this.disposed = false;
    }

    get busy() { return this.pending !== null; }
    get progress() { return this.manifest.frames.length > 1 ? this.current / (this.manifest.frames.length - 1) : 0; }

    async loadFrame(value) {
      if (this.disposed) throw new Error('Water cache player has been disposed.');
      const frame = frameNumber(value, this.manifest.frames.length);
      const sequence = ++this.sequence;
      this.pending?.abort();
      const controller = new AbortController();
      this.pending = controller;
      try {
        const data = this.memo.get(frame) ?? await this.loadMesh(frame, controller.signal);
        // Some fetch adapters finish even after abort. A generation check also
        // protects both the rendered geometry and UI from stale completions.
        if (sequence !== this.sequence || this.disposed) return { stale: true };
        this.memo.delete(frame);
        this.memo.set(frame, data);
        while (this.memo.size > 2) this.memo.delete(this.memo.keys().next().value);
        this.renderer.setFrame(data);
        this.renderer.setMetrics(this.manifest.frames[frame]);
        this.current = frame;
        this.renderer.draw(this.progress);
        const info = this.renderer.info();
        if (info.glError) throw new Error(`Water renderer reported WebGL error ${info.glError}.`);
        this.onFrame(frame, info);
        return { frame, ...info };
      } catch (error) {
        if (sequence !== this.sequence || this.disposed) return { stale: true };
        throw error;
      } finally {
        if (this.pending === controller) this.pending = null;
      }
    }

    dispose() {
      this.disposed = true;
      this.sequence++;
      this.pending?.abort();
      this.pending = null;
      this.memo.clear();
    }
  }

  function orbitCamera(renderer, authoredCamera) {
    renderer.updateCamera = function (progress) {
      if (!this.orbit) { authoredCamera.call(this, progress); return; }
      const orbit = this.orbit;
      this.camera.position.set(this.target.x + orbit.r * Math.cos(orbit.el) * Math.sin(orbit.az),
        this.target.y + orbit.r * Math.sin(orbit.el),
        this.target.z + orbit.r * Math.cos(orbit.el) * Math.cos(orbit.az));
      this.camera.lookAt(this.target);
    };
  }

  async function startViewer(options) {
    const params = new URLSearchParams(location.search);
    const capture = params.has('capture');
    if (capture) document.body.classList.add('capture');
    const $ = id => document.getElementById(id);
    const play = $('play'), timeline = $('timeline'), status = $('status');
    play.disabled = timeline.disabled = true;
    play.setAttribute('aria-pressed', 'false');
    let player, playing = false, animation = 0, last = 0;
    const errors = [];
    const api = global.WATER = { ready: false, errors };
    function setPlaying(value) {
      playing = value;
      play.textContent = playing ? 'Pause' : 'Play';
      play.setAttribute('aria-pressed', String(playing));
      last = performance.now();
    }
    function fail(error) {
      setPlaying(false);
      const message = error.message || String(error);
      errors.push(message);
      global.WATER_ERROR = message;
      status.textContent = message;
      if ($('cache-error')) $('cache-error').hidden = false;
      if ($('error-detail')) $('error-detail').textContent = error.missingAssets
        ? 'This archive requires optional mesh caches. Restore them from the project checkout, then reload this page.' : message;
    }
    async function requestFrame(frame) {
      try { return await player.loadFrame(frame); }
      catch (error) { fail(error); return null; }
    }
    try {
      if (location.protocol === 'file:') throw new Error('Serve the project over HTTP to open the archived water viewer.');
      const response = await fetch(`cache/${options.variant}/manifest.json`);
      if (!response.ok) throw new Error(`Water manifest is unavailable (HTTP ${response.status}).`);
      const manifest = validateManifest(await response.json());
      const renderer = new LiquidRenderer($('view'));
      renderer.setup(manifest.config);
      renderer.setRasterProfile(manifest.config.rasterProfile || 'repair');
      renderer.setMode('water');
      const available = options.availableFrames ?? null;
      if (available && (!available.length || !available.every((f, i) => Number.isInteger(f) && f >= 0 &&
          f < manifest.frames.length && (i === 0 || f > available[i - 1])))) {
        throw new Error('Snapshot list is inconsistent with the water manifest.');
      }
      const fps = manifest.playbackFps ?? 24;
      player = new CachePlayer({ manifest, renderer,
        loadMesh: async (frame, signal) => decompressMesh(await fetch(
          `cache/${options.variant}/${String(frame).padStart(4, '0')}.mesh.gz`, { signal }), manifest.config),
        onFrame: frame => {
          global.WATER_ERROR = null;
          if ($('cache-error')) $('cache-error').hidden = true;
          timeline.value = available ? available.indexOf(frame) : frame;
          const duration = (manifest.frames.length - 1) / fps;
          status.textContent = `${(frame / fps).toFixed(2)} / ${duration.toFixed(2)} s · ${frame + 1}/${manifest.frames.length}` +
            (available ? ' · review snapshot' : '');
          timeline.setAttribute('aria-valuetext', `Frame ${frame + 1}, ${(frame / fps).toFixed(2)} seconds`);
        }
      });
      options.setup?.(renderer, () => player.current);
      // Pointer cancellation must release orbit state on touch browsers.
      $('view').addEventListener('pointercancel', () => { renderer.drag = null; });
      $('view').addEventListener('lostpointercapture', () => { renderer.drag = null; });
      api.renderer = renderer;
      api.manifest = manifest;
      api.availableFrames = available;
      api.loadFrame = frame => player.loadFrame(frame);
      Object.defineProperty(api, 'current', { get: () => player.current });
      timeline.max = available ? available.length - 1 : manifest.frames.length - 1;
      const requested = params.get('frame');
      const initial = requested !== null ? frameNumber(requested, manifest.frames.length)
        : available ? available[0] : capture ? 0 : Math.min(48, manifest.frames.length - 1);
      if (available && !available.includes(initial)) throw new Error(`Frame ${initial} was not retained. Select one of the supplied review snapshots.`);
      await player.loadFrame(initial);
      api.ready = true;
      timeline.disabled = false;
      play.disabled = Boolean(available) || manifest.frames.length < 2;
      if (available) play.title = 'Only review snapshots were retained for this variant.';
      if ($('archive-note')) $('archive-note').textContent = available
        ? `Archived simulation · ${available.length} retained review snapshots · drag to inspect`
        : `Archived simulation · ${fps} fps cache playback · drag to orbit / scroll to zoom`;
      timeline.oninput = event => {
        setPlaying(false);
        const selected = Number(event.target.value);
        void requestFrame(available ? available[selected] : selected);
      };
      play.onclick = () => setPlaying(!playing);
      if ($('speed')) $('speed').onchange = () => { last = performance.now(); };
      if ($('mode')) $('mode').onchange = event => {
        try { renderer.setMode(event.target.value); renderer.draw(player.progress); }
        catch (error) { fail(error); }
      };
      if ($('reset-camera')) $('reset-camera').onclick = () => {
        renderer.orbit = null;
        try { renderer.draw(player.progress); } catch (error) { fail(error); }
      };
      global.addEventListener('resize', () => {
        try { renderer.resize(Math.max(1, innerWidth), Math.max(1, innerHeight)); renderer.draw(player.progress); }
        catch (error) { fail(error); }
      });
      document.addEventListener('visibilitychange', () => { if (document.hidden) setPlaying(false); });
      document.addEventListener('keydown', event => {
        if (event.target && /^(INPUT|SELECT|TEXTAREA|BUTTON|A)$/.test(event.target.tagName)) return;
        if (event.code === 'Space' && !play.disabled) { event.preventDefault(); setPlaying(!playing); }
        if (event.code === 'ArrowLeft' || event.code === 'ArrowRight') {
          event.preventDefault(); setPlaying(false);
          const direction = event.code === 'ArrowLeft' ? -1 : 1;
          const index = available ? available.indexOf(player.current) : player.current;
          const next = Math.max(0, Math.min(Number(timeline.max), index + direction));
          void requestFrame(available ? available[next] : next);
        }
      });
      function tick(now) {
        if (playing && !player.busy && !document.hidden) {
          const speed = Number($('speed')?.value || 1);
          if (now - last >= 1000 / (fps * speed)) {
            last = now;
            void requestFrame((player.current + 1) % manifest.frames.length);
          }
        }
        animation = requestAnimationFrame(tick);
      }
      animation = requestAnimationFrame(tick);
      global.addEventListener('pagehide', event => {
        setPlaying(false);
        if (!event.persisted) { player.dispose(); cancelAnimationFrame(animation); }
      });
      return api;
    } catch (error) {
      player?.dispose();
      fail(error);
      return api;
    }
  }

  global.WaterCache = { parseMesh, decompressMesh, validateManifest, frameNumber, CachePlayer, orbitCamera, startViewer };
})(typeof window === 'undefined' ? globalThis : window);
