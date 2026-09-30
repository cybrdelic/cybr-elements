import {FlipSolver,makeProductionPreset} from '../flip-lettering/vendor/src/main.js';
import fs from 'node:fs';import zlib from 'node:zlib';
import path from 'node:path';import {fileURLToPath,pathToFileURL} from 'node:url';
const argument=name=>{const i=process.argv.indexOf(name);if(i<0)return null;if(!process.argv[i+1]||process.argv[i+1].startsWith('--'))throw Error('Missing value for '+name);return process.argv[i+1]};
const full=process.argv.includes('--full'),offline=process.argv.includes('--offline'),outputPath=argument('--output'),root=outputPath?pathToFileURL(path.resolve(outputPath)+path.sep):new URL(`sigil-02-active-elements/water-${full?'full':'cpu'}/`,import.meta.url),out=new URL('particles/',root);
if(fs.existsSync(new URL('manifest.json',out)))throw Error('Simulation already exists. Choose a fresh --output directory.');
const cfg=JSON.parse(fs.readFileSync(new URL('config.json',root)));
for(const key of ['h','spaceScale','timeScale'])if(!Number.isFinite(cfg[key])||cfg[key]<=0)throw Error('Water config '+key+' must be positive and finite');
for(const key of ['nx','ny','nz','frames'])if(!Number.isInteger(cfg[key])||cfg[key]<=0)throw Error('Water config '+key+' must be a positive integer');
for(const key of ['origin','extent'])if(!Array.isArray(cfg[key])||cfg[key].length!==3||cfg[key].some(x=>!Number.isFinite(x)))throw Error('Water config '+key+' must contain three finite coordinates');
for(const [axis,key] of ['nx','ny','nz'].entries())if(Math.abs(cfg.extent[axis]-cfg[key]*cfg.h)>1e-6*Math.max(1,cfg.extent[axis])||cfg.origin[axis]<0||cfg.origin[axis]>=cfg.extent[axis])throw Error('Water config extent/origin does not match the solver grid');
const fallback=fileURLToPath(new URL(`sigil-02-bending-ground/${full?'full':'cpu'}/`,import.meta.url));
const forceOverride=argument('--force-root'),configured=forceOverride??cfg.forceRoot,relative=configured?path.resolve(fileURLToPath(root),configured):fallback;
const forceRoot=forceOverride?relative:fs.existsSync(relative)?relative:fallback;
const load=p=>{let b;try{b=fs.readFileSync(p)}catch{throw Error('Missing simulation input '+p+'. Restore inputs with python scripts/fetch_assets.py --all')};if(b.byteLength%4)throw Error('Float32 input has a truncated payload: '+p);const data=new Float32Array(b.buffer,b.byteOffset,b.byteLength/4);for(const x of data)if(!Number.isFinite(x))throw Error('Nonfinite simulation input: '+p);return data};
const source=load(new URL('parcels.f32',root)),forces=[0,1,2].map(c=>load(path.join(forceRoot,`guide-${c}.f32`))),count=source.length/9;
if(!Number.isInteger(count)||count===0)throw Error('Initial parcel input must contain nonempty 9-float records');
const fieldValues=(cfg.nx+1)*(cfg.ny+1)*(cfg.nz+1)*2;
if(forces.some(a=>a.length!==fieldValues))throw Error('Guide force dimensions do not match the configured solver grid');
fs.mkdirSync(out,{recursive:true});
const c=makeProductionPreset('jets');Object.assign(c,cfg,{nameKey:'02-active-containment',obstacles:[{kind:'box',center:[cfg.extent[0]/2,cfg.origin[1]/2,cfg.extent[2]/2],half:[cfg.extent[0],cfg.origin[1]/2,cfg.extent[2]]}],maxParticles:count+10,seed:91351,gravity:[0,0,0],flip:.90,separation:true,surfaceTension:.072});
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
class Flow extends FlipSolver{
 constructor(c){super(c);this.ids=new Uint32Array(this.maxParticles);this.phase=new Float32Array(this.len);this.reach=new Float32Array(this.len);
  for(let i=0;i<=this.nx;i++)for(let j=0;j<=this.ny;j++)for(let k=0;k<=this.nz;k++){
   const q=this.index(i,j,k),x=(i*this.h-cfg.origin[0])/cfg.spaceScale,z=(j*this.h-cfg.origin[1])/cfg.spaceScale;
   this.phase[q]=x*1.37+z*.81;const magnitude=Math.hypot(...forces.map(a=>a[q*2]));
   // Containment has a finite capture zone. Detached drops outside it are
   // allowed to fall; they are not teleported, deleted, or multiplied.
   this.reach[q]=1-smooth((magnitude-38)/22);
  }
 }
 emit(){if(this.count)return;for(let i=0;i<count;i++){const k=i*9,x=source[k+3],y=source[k+4],z=source[k+5];if(!this.add(x,y,z,.07*Math.sin(y*15),0,.12*Math.sin(x*11)))throw Error('Initial material intersects collider');this.ids[i]=i;this.spawned++;}}
 step(dt){
  const t=this.time/cfg.timeScale,hold=1-smooth((t-cfg.releaseAt)/.60);
  if(hold&&this.count)for(let i=0;i<this.count;i++){
   const k=i*9,q=i*3,phase=source[k+3]*5.1;
   // Gravity otherwise drains every upper stroke into the lower boundary.
   // A vertical-only bending lift waits for measurable sag, then restores
   // height. Horizontal/depth transport remains free and pressure coupled.
   const slack=.015+.012*(1+Math.sin(t*2.3-phase));
   const sag=source[k+4]-this.p[q+1]-slack;
   const shed=((Math.imul(i+1,2654435761)>>>0)%193===0)&&t>1.0;
   const lift=shed?-9:Math.max(0,Math.min(18,260*Math.max(0,sag)-5*Math.min(0,this.v[q+1])));
   this.v[q+1]+=lift*dt*hold*smooth(t/.55);
  }
  return super.step(dt);
 }
 applyForces(dt){
  const t=this.time/cfg.timeScale,release=smooth((t-cfg.releaseAt)/.60),hold=1-release;
  this.gravity[1]=-(2.3+7.51*release)*smooth(t/.45);super.applyForces(dt);
  for(let i=1;i<this.nx;i++)for(let j=1;j<this.ny;j++){
   const height=(j+.5)*this.h-cfg.origin[1];if(height<0||height>.055)continue;
   const retention=Math.exp(-45*Math.exp(-height/.025)*dt);
   for(let k=1;k<this.nz;k++){const q=this.index(i,j,k);this.u[0][q]*=retention;this.u[2][q]*=retention;}
  }
  if(!hold)return;
  for(let axis=0;axis<3;axis++){
   const a=forces[axis],u=this.u[axis],valid=this.valid[axis];
   for(let q=0;q<this.len;q++)if(valid[q]){
    const phase=this.phase[q],pulse=1.1+.60*Math.sin(t*2.7-phase)+.15*Math.sin(t*4.3+phase*.63);
    const strength=Math.max(.38,pulse),reach=this.reach[q];
    // Spatially travelling relaxation and recovery, with real inertia and
    // pressure projection. No per-particle target servo in this hold.
    u[q]+=(a[q*2]*strength-(a[q*2+1]*.30+.20)*u[q])*dt*hold*reach;
    if(reach>.9&&this.kind[q]===1)u[q]+=(axis===2?.65*Math.sin(t*1.9+phase):axis===0?.22*Math.cos(t*2.3-phase):0)*dt*hold;
   }
  }
 }
}
const sim=new Flow(c),manifest={config:c,origin:cfg.origin,spaceScale:cfg.spaceScale,timeScale:cfg.timeScale,frameDt:cfg.timeScale/30,playbackFps:30,frames:[],source:'Fresh native FLIP initialized in the approved 02 volume. Gravity stays on during the hold. A travelling soft finite-range bending force restores stretched liquid; detached primary water falls. Pressure, surface tension and floor collisions are solved. No position overwrite or synthetic spray.',cacheFormat:'position-u16-velocity-i16-id-u32',cacheVelocityRange:16};
const started=performance.now();
for(let f=0;f<cfg.frames;f++){
 while(full&&!offline&&fs.readdirSync(out).filter(n=>n.endsWith('.gz')).length>=10)await new Promise(r=>setTimeout(r,400));
 const info=sim.advance(manifest.frameDt);if(!info.finite||!info.pressure.converged||info.capacityRejected||Math.abs(info.sourceVolumeBalance)>1e-8)throw Error(JSON.stringify(info));
 let floorContacts=0,minHeight=Infinity;for(let i=0;i<sim.count;i++){minHeight=Math.min(minHeight,sim.p[i*3+1]);if(sim.p[i*3+1]<cfg.origin[1]+cfg.h*1.5)floorContacts++;}
 manifest.frames.push({frame:f,...info,floorContacts,minHeightWorld:(minHeight-cfg.origin[1])/cfg.spaceScale});
 if(full||f%6===0||f===cfg.frames-1){
  const n=sim.count,pp=new Uint16Array(n*3),pv=new Int16Array(n*3);
  for(let j=0;j<n*3;j++){if(Math.abs(sim.v[j])>16)throw Error('Cache velocity range exceeded');pp[j]=Math.round(Math.max(0,Math.min(1,sim.p[j]/cfg.extent[j%3]))*65535);pv[j]=Math.round(sim.v[j]/16*32767);}
  fs.writeFileSync(new URL(`${String(f).padStart(4,'0')}.gz`,out),zlib.gzipSync(Buffer.concat([Buffer.from(pp.buffer),Buffer.from(pv.buffer),Buffer.from(sim.ids.buffer,0,n*4)]),{level:4}));
 }
 fs.writeFileSync(new URL('manifest.tmp',out),JSON.stringify(manifest));fs.renameSync(new URL('manifest.tmp',out),new URL('manifest.json',out));
 if(f%30===0)console.log(JSON.stringify({frame:f,particles:sim.count,contacts:floorContacts,seconds:Math.round((performance.now()-started)/1000)}));
}
manifest.complete=true;fs.writeFileSync(new URL('manifest.tmp',out),JSON.stringify(manifest));fs.renameSync(new URL('manifest.tmp',out),new URL('manifest.json',out));console.log('SIM COMPLETE');
