/** Version-3 primary + shape + rigid-body + pressure-warm-start checkpoint.
 * Explicit, bounded binary sections; never executable serialized state.
 * Browser secondary particles and rendering are separate optional app state.
 */
import {FlipSolver} from './flip.js';
const MAGIC=0x43464333;
const SCALARS=['count','time','steps','randomState','spawned','deleted','capacityRejected','emitCarry','flip','initialCount','initialEmitterParticles','maxProjectionIterations','shapeInitialized','shapeResets','pressureFailures','pressureSolveCount','totalPressureIterations'];
export function encodeCheckpoint(sim,appState=null) {
  if(!(sim instanceof FlipSolver))throw new TypeError('Expected a FlipSolver.');
  const sections=[['p',sim.count*3],['v',sim.count*3],['affine',sim.count*9],['shape',sim.count*6],['pressure',sim.len]];
  const previous=appState?.secondary?.previous;
  if(previous&&!(previous instanceof Float32Array))throw Error('Secondary history must be float32.');
  if(previous&&previous.length>sim.count*3)throw Error('Secondary history exceeds primary capacity.');
  const appCopy=appState?structuredClone(appState):null;if(previous){appCopy.secondary.previous=null;sections.push(['secondaryPrevious',previous.length]);}
  const meta={schema:'cybr-flip-checkpoint/3',config:sim.config,sections,
    scalars:Object.fromEntries(SCALARS.map(k=>[k,sim[k]??0])),motionBase:sim.motionBase,
    obstacles:sim.obstacles,metrics:sim.metrics,lastPressure:sim.lastPressure,appState:appCopy,secondaryPreviousCount:previous?.length??0};
  const header=new TextEncoder().encode(JSON.stringify(meta)),aligned=(header.length+3)&~3;
  const length=16+aligned+sections.reduce((v,[,n])=>v+n*4,0),buffer=new ArrayBuffer(length),view=new DataView(buffer);
  view.setUint32(0,MAGIC,true);view.setUint32(4,header.length,true);view.setUint32(8,sim.count,true);view.setUint32(12,3,true);
  new Uint8Array(buffer,16,header.length).set(header);let offset=16+aligned;
  for(const [name,n] of sections){new Float32Array(buffer,offset,n).set((name==='secondaryPrevious'?previous:sim[name]).subarray(0,n));offset+=n*4;}
  return buffer;
}
export function decodeCheckpoint(input) {
  const buffer=input instanceof ArrayBuffer?input:input?.buffer?.slice(input.byteOffset,input.byteOffset+input.byteLength);
  if(!(buffer instanceof ArrayBuffer)||buffer.byteLength<16)throw Error('Truncated checkpoint.');
  const view=new DataView(buffer),hlen=view.getUint32(4,true),count=view.getUint32(8,true);
  if(view.getUint32(0,true)!==MAGIC||view.getUint32(12,true)!==3||hlen>4e6||count>2e6||16+hlen>buffer.byteLength)throw Error('Invalid checkpoint header.');
  const meta=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,16,hlen))),c=meta.config;
  if(meta.schema!=='cybr-flip-checkpoint/3'||!c||!Number.isFinite(c.h)||c.h<=0||!['nx','ny','nz'].every(k=>Number.isInteger(c[k])&&c[k]>=3&&c[k]<=256))throw Error('Invalid checkpoint grid.');
  if((c.nx+1)*(c.ny+1)*(c.nz+1)>4e6||c.maxParticles<count||c.maxParticles>2e6||meta.scalars.count!==count)throw Error('Checkpoint allocation exceeds limits.');
  const expected=[['p',count*3],['v',count*3],['affine',count*9],['shape',count*6],['pressure',(c.nx+1)*(c.ny+1)*(c.nz+1)]];
  if(meta.secondaryPreviousCount){if(!Number.isInteger(meta.secondaryPreviousCount)||meta.secondaryPreviousCount<0||meta.secondaryPreviousCount>count*3)throw Error('Invalid secondary history count.');expected.push(['secondaryPrevious',meta.secondaryPreviousCount]);}
  if(JSON.stringify(meta.sections)!==JSON.stringify(expected))throw Error('Unexpected checkpoint sections.');
  let offset=16+((hlen+3)&~3);const size=offset+expected.reduce((v,[,n])=>v+n*4,0);if(size!==buffer.byteLength)throw Error('Checkpoint size does not match its sections.');
  const sim=new FlipSolver(c);
  for(const [name,n] of expected) {
    const source=new Float32Array(buffer,offset,n);for(const x of source)if(!Number.isFinite(x))throw Error('Nonfinite checkpoint '+name);
    if(name==='secondaryPrevious'){if(!meta.appState?.secondary)throw Error('Missing secondary metadata');meta.appState.secondary.previous=source.slice();}else{sim[name].fill(0);sim[name].set(source);}offset+=n*4;
  }
  for(const key of SCALARS){const value=meta.scalars[key];if(!Number.isFinite(value))throw Error('Invalid scalar '+key);sim[key]=value;}
  sim.motionBase=meta.motionBase;sim.obstacles=structuredClone(meta.obstacles);sim.config.obstacles=sim.obstacles;
  sim.dynamic=sim.obstacles.some(o=>o.dynamic);sim.moving=sim.dynamic||sim.obstacles.some(o=>o.motion);
  sim.metrics=meta.metrics;sim.lastPressure=meta.lastPressure;sim.markSolids();sim.appState=meta.appState;
  const metrics=sim.inspect();if(!metrics.finite||metrics.solidViolations)throw Error('Invalid particle domain in checkpoint.');
  return sim;
}
