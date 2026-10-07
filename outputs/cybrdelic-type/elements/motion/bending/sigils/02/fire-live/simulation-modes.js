// Presentation identity is independent of the shared Volume source IDs.
export function modeForFire(fire, preferred) {
  if (fire?.startsWith('legacy:')) return 'legacy';
  return preferred === 'sparse' ? 'sparse' : 'volume';
}

export function runtimeFamily(mode) {
  return mode === 'legacy' ? 'legacy' : 'volume';
}

export function readSimulation(params) {
  const mode = params.get('simulation');
  if (mode === 'sparse' || (mode === 'volume' && params.get('bricks') === '1')) return 'sparse';
  return mode === 'volume' ? 'volume' : 'legacy';
}

export function volumeOptions(params, mode) {
  const transport = params.get('transport') === 'conservative' ? 'flux' : 'maccormack';
  if (mode === 'sparse') return {
    ...(params.get('pressureCache')==='1'?{pressureCache:true}:{}),
    adaptive: false, pressureWork: false, brickPool: true,
    lightWork: false, lightReceivers: false, transport,
  };
  return {
    pressureCache:params.get('pressureCache')!=='0',
    ...(params.get('woodCadence')==='frame'?{multirateWood:true}:{}),
    adaptive: params.get('solver') === 'adaptive',
    pressureWork: params.get('pressureWork') === '1',
    brickPool: false,
    lightWork: params.get('lightWork') === '1',
    lightReceivers: params.get('receivers') === '1',
    transport,
  };
}
