/** Versioned, resumable primary-solver checkpoints. Renderer/diffuse state is
 * deliberately separate: this is not a promise to checkpoint a whole DCC app.
 * The next primary step is byte-reproducible in the tested JavaScript runtime.
 */
import {FlipSolver} from './flip.js';
const MAGIC=0x43464332;
const SCALARS=['count','time','steps','randomState','spawned','deleted','capacityRejected','emitCarry','flip','initialCount','initialEmitterParticles','maxProjectionIterations'];
export function encodeCheckpoint(sim){
 if(!(sim instanceof FlipSolver))throw new TypeError('Expected a FlipSolver.');
 const metadata={schema:'cybr-flip-primary-checkpoint/2',config:sim.config,state:Object.fromEntries(SCALARS.map(k=>[k,sim[k]])),metrics:sim.metrics,motionBase:sim.motionBase};
 const header=new TextEncoder().encode(JSON.stringify(metadata)),aligned=(header.length+3)&~3,n=sim.count;
 const buffer=new ArrayBuffer(16+aligned+n*15*4),view=new DataView(buffer);view.setUint32(0,MAGIC,true);view.setUint32(4,header.length,true);view.setUint32(8,n,true);view.setUint32(12,2,true);
 new Uint8Array(buffer,16,header.length).set(header);let offset=16+aligned;
 for(const [array,size] of [[sim.p,n*3],[sim.v,n*3],[sim.affine,n*9]]){new Float32Array(buffer,offset,size).set(array.subarray(0,size));offset+=size*4;}
 return buffer;
}
export function decodeCheckpoint(input){
 const buffer=input instanceof ArrayBuffer?input:input?.buffer?.slice(input.byteOffset,input.byteOffset+input.byteLength);
 if(!(buffer instanceof ArrayBuffer)||buffer.byteLength<16)throw new Error('Checkpoint is truncated.');
 const view=new DataView(buffer);if(view.getUint32(0,true)!==MAGIC||view.getUint32(12,true)!==2)throw new Error('Unsupported checkpoint format.');
 const headerLength=view.getUint32(4,true),n=view.getUint32(8,true),aligned=(headerLength+3)&~3;
 if(headerLength>2e6||n>2e6||buffer.byteLength!==16+aligned+n*60)throw new Error('Invalid checkpoint size.');
 const metadata=JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,16,headerLength))),c=metadata.config;
 if(metadata.schema!=='cybr-flip-primary-checkpoint/2'||!c||!Number.isFinite(c.h)||c.h<=0)throw new Error('Invalid checkpoint configuration.');
 if(!['nx','ny','nz'].every(k=>Number.isInteger(c[k])&&c[k]>=3&&c[k]<=256)||(c.nx+1)*(c.ny+1)*(c.nz+1)>4e6)throw new Error('Checkpoint grid exceeds safety limits.');
 if(!Number.isInteger(c.maxParticles)||c.maxParticles<n||c.maxParticles>2e6||metadata.state.count!==n)throw new Error('Invalid particle capacity.');
 const sim=new FlipSolver(c);sim.p.fill(0);sim.v.fill(0);sim.affine.fill(0);let offset=16+aligned;
 for(const [target,size] of [[sim.p,n*3],[sim.v,n*3],[sim.affine,n*9]]){const a=new Float32Array(buffer,offset,size);for(const v of a)if(!Number.isFinite(v))throw new Error('Checkpoint has non-finite state.');target.set(a);offset+=size*4;}
 for(const k of SCALARS){const value=metadata.state[k];if(!Number.isFinite(value))throw new Error('Invalid checkpoint scalar '+k);sim[k]=value;}
 sim.motionBase=metadata.motionBase;sim.metrics=metadata.metrics;sim.updateObstacles(sim.time);
 const report=sim.inspect(0);if(!report.finite||report.solidViolations)throw new Error('Invalid checkpoint particle positions.');return sim;
}
