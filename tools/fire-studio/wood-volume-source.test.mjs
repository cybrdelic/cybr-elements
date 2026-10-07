import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load=file=>import(pathToFileURL(resolve(root,file)).href);
const {WOOD_FLUX,woodFluxDeliveredMass,woodFluxVolumeSource,woodFluxWorkBricks,woodFluxWGSL}=await load('pyro-gpu/wood-flux.js');
const {simulationShaders}=await load('pyro-gpu/shaders.js');
const {adaptiveFlowShaders}=await load('pyro-gpu/adaptive-flow.js');
const close=(a,b)=>assert.ok(Math.abs(a-b)<=1e-11*Math.max(1,Math.abs(a),Math.abs(b)),`${a} != ${b}`);
function packet(integer,{blocked=false,normalization=1,energy=0n}={}){
  return new Uint32Array([Number(integer&0xffffffffn),Number(integer>>32n),
    Number(energy&0xffffffffn),Number(energy>>32n),normalization,Number(blocked)]);
}
test('wood gas volume uses raw finite coarse mass and physical1/s source units',()=>{
  for(const integer of [0n,1n,123456789n,(1n<<42n)+7919n])for(const N of [64,128]){
    const words=packet(integer),mass=Number(integer)/WOOD_FLUX.massUnitsPerKg;
    close(woodFluxDeliveredMass(words),mass);
    for(const dt of [1/60,1/180,1/720]){
      close(woodFluxVolumeSource(words,dt,N)*dt*(6/N)**3,mass/WOOD_FLUX.gasFuelDensityKgM3);
    }
  }
  assert.throws(()=>woodFluxVolumeSource(packet(1n),0),/Invalid wood source volume/);
});
test('fine fluid normalization and sensible enthalpy never duplicate pressure volume',()=>{
  const integer=(1n<<40n)+291n,reference=woodFluxVolumeSource(packet(integer),1/60);
  for(const normalization of [0,1,2,512,0xffffffff])for(const energy of [0n,1n,1n<<45n])
    close(woodFluxVolumeSource(packet(integer,{normalization,energy}),1/60),reference);
  assert.equal(woodFluxVolumeSource(packet(0n,{energy:1n<<44n}),1/60),0);
});
test('blocked retained mass enters neither pressure nor active scalar support until it opens',()=>{
  const integer=(1n<<33n)+500n;
  assert.equal(woodFluxVolumeSource(packet(integer,{blocked:true}),1/60),0);
  assert.deepEqual(woodFluxWorkBricks([63,64,15],0,true),[]);
  const opened=woodFluxVolumeSource(packet(integer),1/60);
  close(opened*(6/128)**3/60,Number(integer)/1e8);
  assert.equal(woodFluxVolumeSource(packet(0n),1/60),0,'producer clears delivered generation once');
});
test('exact2³ aggregation preserves global source volume at64 and128 without interpolation',()=>{
  const entries=[];let released=0n;
  for(let i=0;i<256;i++){
    const integer=BigInt(i*7919+3),blocked=i%7===0;
    entries.push({cell:[i%16,Math.floor(i/16),i%4],words:packet(integer,{blocked,normalization:512})});
    if(!blocked)released+=integer;
  }
  for(const N of [64,128])for(const dt of [1/60,1/180]){
    const groups=new Map();
    for(const {cell,words} of entries){
      const at=cell.map(value=>Math.floor(value/(128/N))),key=at.join(',');
      const mass=words[5]===0?BigInt(words[0])+(BigInt(words[1])<<32n):0n;
      groups.set(key,(groups.get(key)||0n)+mass);
    }
    const integral=[...groups.values()].reduce((sum,mass)=>sum+woodFluxVolumeSource(packet(mass),dt,N)*(6/N)**3*dt,0);
    close(integral,Number(released)/(1e8*WOOD_FLUX.gasFuelDensityKgM3));
  }
});
test('real-time CFL subdivisions preserve total injected volume',()=>{
  const total=1200000n;
  for(const partitions of [1,3,12]){
    const dt=.6/partitions;let volume=0;
    for(let step=0;step<partitions;step++)volume+=woodFluxVolumeSource(packet(total/BigInt(partitions)),dt)*(6/128)**3*dt;
    close(volume,Number(total)/1e8);
  }
});
test('existing full scalar footprint conservatively covers the source pressure cell and adjacent basis',()=>{
  for(const cell of [[0,0,0],[127,127,127],[7,8,15],[63,64,95]]){
    const bricks=new Set(woodFluxWorkBricks(cell,1,true));
    for(let z=-1;z<=2;z++)for(let y=-1;y<=2;y++)for(let x=-1;x<=2;x++){
      const fine=cell.map((value,axis)=>2*value+[x,y,z][axis]);
      if(fine.some(value=>value<0||value>=256))continue;
      const index=Math.floor(fine[0]/8)+32*(Math.floor(fine[1]/8)+32*Math.floor(fine[2]/8));
      assert.ok(bricks.has(index));
    }
  }
});
test('dense and adaptive pressure consume the completed fine wood release',()=>{
 const adaptive=adaptiveFlowShaders(128,256);
 for(const code of [simulationShaders(128,256).correctVelocity,adaptive.coarseCorrect,adaptive.fineCorrect]){
  assert.match(code,/completedVolumeSourceAt\(x,N\)/);
  assert.doesNotMatch(code,/expansion\+=woodFluxVolumeSource/,'no second count of the same wood dose');
  assert.match(code,/textureStore\(dst,vec3i\(i\),vec4f\(out,expansion\)\)/);
 }
 const scalar=simulationShaders(128,256).correctScalar;
 assert.match(scalar,/let vapor=woodFluxFineDensity/);
 assert.ok(scalar.indexOf('c.z+=vapor.x')<scalar.indexOf('let fuelAfterSources=c.z'));
 assert.match(scalar,/thermalVolumeChange\(temperatureBeforeReaction,c.y,fuelBeforeSources,fuelAfterSources/);
});
