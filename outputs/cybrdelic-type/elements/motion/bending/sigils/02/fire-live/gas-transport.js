// World-unit subgrid mixing, shared by both physical domains. The old
// coefficient was calibrated at ~0.023 m cells, not an arbitrary grid index.
export const GAS_DIFFUSIVITY=.0004;
export const PRODUCT_DIFFUSIVITY=.0002;
export function diffusionWeights(spacing,dt,diffusivity=GAS_DIFFUSIVITY){
 if(spacing.length!==3||spacing.some(h=>!Number.isFinite(h)||h<=0)||!Number.isFinite(dt)||dt<0)throw Error('Invalid diffusion spacing');
 const a=spacing.map(h=>diffusivity*dt/(h*h));
 if(2*a.reduce((s,v)=>s+v,0)>1+1e-10)throw Error('Diffusion timestep exceeds positivity limit');
 return a;
}
export function diffusionStepLimit(spacing){return 1/(2*GAS_DIFFUSIVITY*spacing.reduce((s,h)=>s+1/(h*h),0));}
