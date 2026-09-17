/** Regression-locked scene profiles. Pixel resolution is NOT physics resolution.
 * The original III factory remains available in flip.js for numerical ablation.
 * All live CPU entry points and the repaired capture plan use this wrapper.
 */
import {makePreset as legacyPreset,PRESETS as LEGACY_PRESETS} from './flip.js';
export const PRESETS=LEGACY_PRESETS;
export const PRODUCTION_QUALITY={breach:'ultra',impact:'ultra',jets:'ultra',slosh:'ultra',hero:'ultra',
 cascade:'high',vortex:'high',paddle:'high',buoy:'high',capillary:'high',viscous:'high'};
export function makePreset(name,quality='high'){
 const c=legacyPreset(name,quality);
 if(!['capillary','viscous'].includes(name)) { c.flip=.93; c.separation=true; }
 c.surfaceOptions={spacingFactor:.43,kernelRadiusFactor:.99,fieldSigma:.34,meshSmoothingPasses:2,
  temporalBlend:0,shapeHistoryWeight:0,geometricVolumeRecovery:false};
 c.rasterProfile='repair';c.repairVersion='3.1.0';
 return c;
}
export function makeProductionPreset(name){
 if(!PRODUCTION_QUALITY[name])throw Error('No reviewed production quality for '+name);
 return makePreset(name,PRODUCTION_QUALITY[name]);
}
