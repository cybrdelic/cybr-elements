// The compressible stage chooses its timestep from current GPU state, including
// incoming source energy. Clock work is tiny and never maps on the frame path.
export const shockClockLayout=`
struct EulerClock{remaining:f32,dt:f32,elapsed:f32,flags:atomic<u32>,signal:f32,hold:f32,injected:atomic<u32>,pad:f32};
`;
export function shockClockShaders(n,cfl=.36){
 const base=`${shockClockLayout}
@group(0) @binding(0) var<uniform> control:vec4f;
@group(0) @binding(1) var<storage,read_write> clock:EulerClock;
@group(0) @binding(2) var<storage,read_write> signal:array<atomic<u32>>;
`;
 return {
  begin:base+`@compute @workgroup_size(1) fn main(){clock.remaining=control.x;clock.dt=0.;clock.elapsed=0.;clock.signal=0.;clock.hold=max(0.,clock.hold-control.x);atomicStore(&clock.injected,0u);atomicStore(&clock.flags,0u);}`,
  choose:base+`@compute @workgroup_size(1) fn main(){
   if(atomicLoad(&clock.injected)>0u){clock.hold=.42;}
   if(clock.hold<=0.){clock.remaining=0.;clock.dt=0.;return;}
   let speed=bitcast<f32>(atomicLoad(&signal[0]));clock.signal=max(clock.signal,speed);
   // A half-CFL margin covers changes during the three dimensional sweeps.
   clock.dt=min(clock.remaining,${cfl*.5}*(6./${n}.)/max(speed,.0001));
   clock.remaining=max(0.,clock.remaining-clock.dt);clock.elapsed+=clock.dt;
  }`,
  finish:base+`@compute @workgroup_size(1) fn main(){if(clock.remaining>.00000001){atomicOr(&clock.flags,1u);}}`,
 };
}
