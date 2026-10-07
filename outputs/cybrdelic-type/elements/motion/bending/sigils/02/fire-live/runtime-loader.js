// Load only the selected engine. The studio shell and library need neither GPU runtime.
const scripts = new Map();
const legacyScripts = [
  'coarse-pressure.js',
  'original-fine-flow.js',
  'corrected-advection.js',
  'vorticity.js',
  'fire-optics.js',
  'smoke-light.js',
  'fire-room.js',
  'fire-emitters.js',
  'fire-props.js',
];
const previousScripts = [
  'coarse-pressure.js',
  'corrected-advection-v5.js',
  'vorticity.js',
  'fire-optics.js',
  'smoke-light.js',
  'fire-room.js',
  'fire-emitters.js',
  'fire-props.js',
];

function loadScript(file) {
  if (!scripts.has(file)) {
    scripts.set(
      file,
      new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = new URL(file + '?v=studio-rc-42-boundary-source-age', import.meta.url).href;
        script.onload = resolve;
        script.onerror = () => {
          scripts.delete(file);
          script.remove();
          reject(new Error('Could not load ' + file + '. Check the connection and try again.'));
        };
        document.head.append(script);
      }),
    );
  }
  return scripts.get(file);
}

export async function loadRuntime(kind) {
  if (kind === 'volume' || kind === 'sparse') return (await import('./pyro-gpu/app.js?v=studio-rc-37-repair')).mountVolume;
  const { woodMaterialGLSL } = await import('./wood-material.js?v=studio-rc-37-repair');
  window.WoodMaterialGLSL = woodMaterialGLSL;
  const previousVersion = typeof location !== 'undefined' && new URL(location.href).searchParams.get('runtime') === 'v5';
  const helpers = previousVersion ? previousScripts : legacyScripts;
  await Promise.all(helpers.map(loadScript));
  if (previousVersion) return (await import('./fire-v5.js?v=studio-v5-rollback')).mountLegacy;
  return (await import('./fire.js?v=studio-rc-42-boundary-source-age')).mountLegacy;
}
