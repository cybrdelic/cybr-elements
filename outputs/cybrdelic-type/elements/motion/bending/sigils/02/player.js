/* The manifest names checked-in films explicitly; URL input never becomes an asset path. */
(async () => {
  'use strict';

  const response = await fetch('films.json');
  if (!response.ok) throw new Error('Film manifest unavailable');
  const manifest = await response.json();
  if (manifest.schemaVersion !== 1 || !manifest.elements) throw new Error('Film manifest unsupported');
  const elements = manifest.elements;

  const byId = (id) => document.getElementById(id);
  const film = byId('film');
  const elementLinks = [...document.querySelectorAll('[data-element]')];
  const reference = byId('reference');
  const previous = byId('previous');
  const artwork = byId('artwork');
  const download = byId('download');
  const openFilm = byId('open-film');
  const status = byId('playback-state');
  const startPlayback = byId('start-playback');
  const failure = byId('failure-panel');
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  let state;
  let generation = 0;
  let expectedSource = '';
  let loadingTimer;
  let pendingPlayback = false;
  let resumeAfterVisibility = false;
  let hasFailed = false;

  const normalize = (candidate) => {
    const name = Object.prototype.hasOwnProperty.call(elements, candidate.element) ? candidate.element : 'fire';
    return {
      element: name,
      version: candidate.version === 'previous' && elements[name].previous ? 'previous' : 'current',
      compare: candidate.compare === true
    };
  };

  const stateFromUrl = () => {
    const params = new URL(window.location.href).searchParams;
    return normalize({ element: params.get('element'), version: params.get('version'), compare: params.get('compare') === '1' });
  };

  function writeUrl(mode) {
    const url = new URL(window.location.href);
    url.searchParams.set('element', state.element);
    if (state.version === 'previous') url.searchParams.set('version', 'previous');
    else url.searchParams.delete('version');
    if (state.compare) url.searchParams.set('compare', '1');
    else url.searchParams.delete('compare');
    if (url.href !== window.location.href) window.history[mode === 'push' ? 'pushState' : 'replaceState'](null, '', url);
  }

  function assetIsCurrent() {
    return film.currentSrc === expectedSource;
  }

  function versionLabel(asset) {
    const label = state.version === 'previous' ? 'Previous film' : 'Current film';
    return asset.revision ? `${label} / revision ${asset.revision}` : label;
  }

  function updateMetadata() {
    const asset = elements[state.element][state.version];
    // Video dimensions and duration come from decoded media when available, with
    // checked asset values as a fallback. All bundled films were encoded at 30 fps.
    const decoded = assetIsCurrent() && film.readyState >= 1;
    const width = decoded && film.videoWidth ? film.videoWidth : asset.width;
    const height = decoded && film.videoHeight ? film.videoHeight : asset.height;
    const duration = decoded && Number.isFinite(film.duration) ? film.duration : asset.duration;
    byId('media-meta').textContent = `${width} × ${height} / ${asset.fps} fps / ${duration.toFixed(1)} s`;
  }

  function updatePresentation() {
    const item = elements[state.element];
    const asset = item[state.version];
    const label = versionLabel(asset);
    document.documentElement.style.setProperty('--accent', item.accent);
    document.title = `CYBR Elements — ${item.title} / 02${state.version === 'previous' ? ' / previous' : ''}`;
    byId('element-index').textContent = item.index;
    byId('material-family').textContent = item.family;
    byId('element-title').replaceChildren(document.createTextNode(item.title));
    const period = document.createElement('span');
    period.textContent = '.';
    period.setAttribute('aria-hidden', 'true');
    byId('element-title').append(period);
    byId('element-description').textContent = item.description;
    byId('version-note').textContent = label;
    film.setAttribute('aria-label', `${item.title} material film${state.version === 'previous' ? ', previous version' : ''}`);
    elementLinks.forEach((link) => {
      if (link.dataset.element === state.element) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
    previous.hidden = !item.previous;
    previous.setAttribute('aria-pressed', String(state.version === 'previous'));
    previous.textContent = state.version === 'previous' ? 'Current version' : 'Previous version';
    reference.setAttribute('aria-expanded', String(state.compare));
    reference.replaceChildren(document.createTextNode(state.compare ? 'Hide artwork' : 'Compare artwork'));
    const comparisonSymbol = document.createElement('span');
    comparisonSymbol.textContent = state.compare ? '−' : '+';
    comparisonSymbol.setAttribute('aria-hidden', 'true');
    reference.append(comparisonSymbol);
    artwork.hidden = !state.compare;
    byId('material-still').src = asset.poster;
    byId('material-still').alt = `${item.title} forming the Cybrdelic 02 sigil, ${label.toLowerCase()}`;
    byId('still-caption').textContent = `02 / ${item.title} still`;
    byId('still-version').textContent = label;
    download.href = asset.file;
    download.download = `cybrdelic-02-${state.element}${asset.revision ? `-r${asset.revision}` : ''}.mp4`;
    download.setAttribute('aria-label', `Download ${item.title.toLowerCase()} film${state.version === 'previous' ? ', previous version' : ''}`);
    openFilm.href = asset.file;
    byId('share-state').textContent = '';
    updateMetadata();
  }

  function showFailure() {
    if (!assetIsCurrent() || !film.error) return;
    clearTimeout(loadingTimer);
    pendingPlayback = false;
    hasFailed = true;
    startPlayback.hidden = true;
    const messages = {
      1: 'Loading was interrupted. Try again or open the MP4 directly.',
      2: 'The film could not be downloaded. Check your connection, then try again.',
      3: 'This browser could not decode the film. Try opening the MP4 directly.',
      4: 'The film is missing or its format is unsupported. Try opening the MP4 directly.'
    };
    byId('failure-detail').textContent = messages[film.error.code] || 'The film could not be loaded. Try again or open the MP4 directly.';
    failure.hidden = false;
    status.textContent = 'Playback unavailable';
  }

  function requestPlayback() {
    if (document.hidden || hasFailed) return;
    const requestedGeneration = generation;
    pendingPlayback = true;
    const attempt = film.play();
    if (!attempt || typeof attempt.catch !== 'function') return;
    attempt.catch((error) => {
      if (generation !== requestedGeneration || document.hidden || error.name === 'AbortError') return;
      pendingPlayback = false;
      if (film.error) {
        showFailure();
        return;
      }
      startPlayback.hidden = false;
      status.textContent = error.name === 'NotAllowedError' ? 'Press play to watch' : 'Playback paused — press play to retry';
    });
  }

  function select(candidate, options = {}) {
    const next = normalize(candidate);
    const compareOpened = next.compare && (!state || !state.compare);
    const mediaChanged = !state || next.element !== state.element || next.version !== state.version || options.reload;
    const keepPlaying = !compareOpened && (options.play !== undefined ? options.play : !film.paused || pendingPlayback);
    state = next;
    if (mediaChanged) {
      generation += 1;
      clearTimeout(loadingTimer);
      pendingPlayback = false;
      resumeAfterVisibility = false;
      hasFailed = false;
      film.pause();
      const asset = elements[state.element][state.version];
      expectedSource = new URL(asset.file, document.baseURI).href;
      film.poster = asset.poster;
      film.src = asset.file;
      film.preload = connection && connection.saveData ? 'none' : 'metadata';
      failure.hidden = true;
      startPlayback.hidden = true;
      status.textContent = 'Loading film…';
      film.load();
      const loadGeneration = generation;
      loadingTimer = window.setTimeout(() => {
        if (generation === loadGeneration && !hasFailed && film.readyState < 2) {
          status.textContent = 'Still loading — you can open or download the MP4 below';
        }
      }, 15000);
      if (keepPlaying && !document.hidden) requestPlayback();
      else status.textContent = 'Press play to watch';
    }
    if (compareOpened && !mediaChanged) {
      pendingPlayback = false;
      resumeAfterVisibility = false;
      film.pause();
    }
    updatePresentation();
    if (options.history) writeUrl(options.history);
  }

  elementLinks.forEach((link) => {
    link.addEventListener('click', (event) => {
      // Preserve native open-in-new-tab gestures for the directly linked media.
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      select({ element: link.dataset.element, version: 'current', compare: state.compare }, { history: 'push' });
    });
    link.addEventListener('keydown', (event) => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const index = elementLinks.indexOf(link);
      const targetIndex = event.key === 'Home' ? 0 : event.key === 'End' ? elementLinks.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + elementLinks.length) % elementLinks.length;
      elementLinks[targetIndex].focus();
    });
  });

  previous.addEventListener('click', () => {
    select({ ...state, version: state.version === 'previous' ? 'current' : 'previous' }, { history: 'push' });
  });

  reference.addEventListener('click', () => {
    const show = !state.compare;
    select({ ...state, compare: show }, { history: 'push' });
    if (show) {
      film.pause();
      pendingPlayback = false;
      resumeAfterVisibility = false;
      artwork.scrollIntoView({ behavior: reducedMotion.matches ? 'auto' : 'smooth', block: 'nearest' });
    }
  });

  byId('retry').addEventListener('click', () => select(state, { reload: true, play: true }));
  startPlayback.addEventListener('click', requestPlayback);
  window.addEventListener('popstate', () => select(stateFromUrl()));

  film.addEventListener('loadedmetadata', () => {
    if (assetIsCurrent()) updateMetadata();
  });
  film.addEventListener('canplay', () => {
    if (!assetIsCurrent() || hasFailed) return;
    clearTimeout(loadingTimer);
    if (film.paused && !pendingPlayback) status.textContent = 'Press play to watch';
  });
  film.addEventListener('playing', () => {
    if (!assetIsCurrent()) return;
    clearTimeout(loadingTimer);
    pendingPlayback = false;
    startPlayback.hidden = true;
    status.textContent = 'Playing / loop';
  });
  film.addEventListener('pause', () => {
    if (!hasFailed && assetIsCurrent() && !pendingPlayback) status.textContent = 'Paused';
  });
  film.addEventListener('waiting', () => {
    if (!hasFailed && assetIsCurrent() && !film.paused) status.textContent = 'Buffering…';
  });
  film.addEventListener('error', showFailure);

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      resumeAfterVisibility = !film.paused || pendingPlayback;
      pendingPlayback = false;
      film.pause();
    } else if (resumeAfterVisibility) {
      resumeAfterVisibility = false;
      requestPlayback();
    }
  });

  const motionPreferenceChanged = (event) => {
    if (event.matches) {
      pendingPlayback = false;
      resumeAfterVisibility = false;
      film.pause();
      status.textContent = 'Reduced motion / press play to watch';
    }
  };
  if (reducedMotion.addEventListener) reducedMotion.addEventListener('change', motionPreferenceChanged);
  else if (reducedMotion.addListener) reducedMotion.addListener(motionPreferenceChanged);

  const share = byId('share');
  share.hidden = false;
  share.addEventListener('click', async () => {
    const message = byId('share-state');
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(window.location.href);
        message.textContent = 'Link copied';
      } else {
        message.textContent = `Share this link: ${window.location.href}`;
      }
    } catch (_) {
      message.textContent = `Share this link: ${window.location.href}`;
    }
  });

  const initial = stateFromUrl();
  const allowAutoplay = !reducedMotion.matches && !(connection && connection.saveData) && !initial.compare;
  select(initial, { history: 'replace', play: allowAutoplay });
  if (reducedMotion.matches) status.textContent = 'Reduced motion / press play to watch';
})().catch(() => {
  // Direct film links and native controls remain useful if the manifest cannot load.
  document.getElementById('playback-state').textContent = 'Collection controls unavailable — element links open each film directly';
  document.getElementById('reference').hidden = true;
  document.getElementById('previous').hidden = true;
});
