import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const source=fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const root=resolve(process.env.FIRE_STUDIO_ROOT||source);
const {originalWoodSource,createWoodStateGL}=await import(pathToFileURL(resolve(root,'wood-state-gl.js')).href);
const {WOOD_THERMO}=await import(pathToFileURL(resolve(root,'wood-thermo.js')).href);
const {createWoodStructureGL,woodMechanicsGLSL}=await import(pathToFileURL(resolve(root,'wood-structure-gl.js')).href);
const {advanceFloorWood}=await import(pathToFileURL(resolve(root,'pyro-gpu/floor-fuel.js')).href);

function fixture(){
 const gl={},calls={allocations:[],draws:[],deletedTextures:[],deletedFBOs:[],deletedPrograms:[],bindings:[],uniforms:[]};let serial=0,texture,current;
 for(const [i,name]of 'TEXTURE_2D TEXTURE_3D TEXTURE_MIN_FILTER TEXTURE_MAG_FILTER TEXTURE_WRAP_S TEXTURE_WRAP_T NEAREST CLAMP_TO_EDGE RGBA32F RGBA FLOAT FRAMEBUFFER FRAMEBUFFER_COMPLETE TRIANGLES TEXTURE14'.split(' ').entries())gl[name]=i+1;
 gl.COLOR_ATTACHMENT0=100;gl.COLOR_ATTACHMENT1=101;
 gl.createTexture=()=>({id:++serial});gl.bindTexture=(type,t)=>{texture=t;};gl.texParameteri=()=>{};
 gl.texImage2D=(type,level,format,w,h)=>calls.allocations.push({texture,format,w,h});
 gl.createFramebuffer=()=>({id:++serial});gl.bindFramebuffer=gl.framebufferTexture2D=gl.drawBuffers=gl.viewport=gl.activeTexture=()=>{};
 gl.checkFramebufferStatus=()=>gl.FRAMEBUFFER_COMPLETE;gl.useProgram=p=>{current=p;};gl.drawArrays=()=>calls.draws.push(current);
 for(const method of ['uniform1f','uniform1i','uniform2f','uniform4fv'])gl[method]=(name,...value)=>calls.uniforms.push({name,value});
 gl.deleteTexture=t=>calls.deletedTextures.push(t);gl.deleteFramebuffer=t=>calls.deletedFBOs.push(t);gl.deleteProgram=p=>calls.deletedPrograms.push(p);
 const programs=[];
 const wood=createWoodStateGL(gl,{shared:'fixture shared',program:fragment=>{const p={fragment};programs.push(p);return p;},uniform:(p,name)=>name,bind:(t,unit,name)=>calls.bindings.push({t,unit,name})});
 const config={key:'bonfire:2',kind:2,bark:0,scale:1,centre:[0,.36],bounds:[-1.3,-.06,1.3,.65],sigma:.26,moisture:WOOD_THERMO.dryMoistureFraction,variation:0};
 return {gl,calls,wood,programs,config};
}

test('Original selects finite solid wood separately from a wood-colored gas emitter',()=>{
 for(const id of ['sigil','sigil-cybr','violet-sigil'])assert.equal(originalWoodSource(id).kind,1);
 for(const id of ['campfire','bonfire','hearth'])assert.equal(originalWoodSource(id).kind,2);
 for(const object of ['logs','house','cybr-tree'])assert.equal(originalWoodSource('fixture',{object}).kind,3);
 assert.equal(originalWoodSource('cybr-tree',{object:'cybr-tree'}).bark,1);
 for(const id of ['explosion','rolling','ring','sigil-star','torch','smoke-column','free'])assert.equal(originalWoodSource(id,{fuel:'wood'}).kind,0);
 for(const object of ['car','mannequin'])assert.equal(originalWoodSource('fixture',{object,fuel:'wood'}).kind,0);
});

test('Projected stock persists when a wood source moves and resets only on a deliberate restart or source change',()=>{
 const {wood,calls,programs,config}=fixture();
 assert.equal(calls.allocations.length,5);assert.equal(calls.allocations.reduce((n,t)=>n+t.w*t.h*16,0),5*1024*1024);
 wood.configure(config);assert.equal(wood.enabled,true);
 const step=()=>wood.step({name:'gas'},{name:'source'},{name:'object'},1/30,{clock:3,age:3,starter:false,timeScale:7});
 step();assert.deepEqual(calls.draws,[programs[0],programs[1]]);const first=wood.stockTexture;
 wood.configure({...config,centre:[1,.6],bounds:[-.3,.18,2.3,.89]});step();
 assert.equal(calls.draws.filter(p=>p===programs[0]).length,1,'Dragging does not refill the stock');
 assert.notEqual(wood.stockTexture,first,'Thermal state ping-pongs');
 assert.equal(calls.uniforms.filter(u=>u.name==='woodStarter').at(-1).value[0],0,'Stopping the starter stops its imposed thermal flux');
 assert.equal(calls.uniforms.filter(u=>u.name==='woodTimeScale').at(-1).value[0],7);
 wood.reset();step();assert.equal(calls.draws.filter(p=>p===programs[0]).length,2);
 wood.configure({...config,key:'hearth:2'});step();assert.equal(calls.draws.filter(p=>p===programs[0]).length,3);
 wood.bind({},true);assert.deepEqual(calls.bindings.slice(-3).map(b=>b.unit),[5,6,7]);
 const allocations=calls.allocations.length;wood.configure({...config,key:'explosion:0',kind:0});assert.equal(step(),false);assert.equal(calls.allocations.length,allocations);
 wood.destroy();assert.equal(calls.deletedTextures.length,5);assert.equal(calls.deletedFBOs.length,3);assert.equal(calls.deletedPrograms.length,2);
});

test('Wood release, charring, and Original rendering use the persistent shared material fields',async()=>{
 const fire=await readFile(resolve(root,'fire.js'),'utf8'),props=await readFile(resolve(root,'fire-props.js'),'utf8'),emitters=await readFile(resolve(root,'fire-emitters.js'),'utf8'),ground=await readFile(resolve(root,'ground-fuel-gl.js'),'utf8');
 assert.match(fire,/woodFuelGas\(vec3\(worldX,worldZ,worldY\),delta,fuel,oxygen,temp\)/);
 assert.match(fire,/sourceEnabled>\.5&&woodEnabled<\.5/);
 assert.match(fire,/woodEnabled<\.5\s*&&\s*brushActive/);
 assert.match(fire,/elapsed > DURATION && !manualFuelSession && !woodState.enabled/);
 assert.match(props,/woodMaterial\(materialPoint,materialNormal,stock.g,stock.r,stock.a,wear.z/);
 assert.match(ground,/woodMaterial\(at,n,stock.g,stock.r,stock.a,wear.z/);
 assert.match(emitters,/if\(emitterKind==16\|\|emitterKind==17\|\|emitterKind==20\)return/);
 assert.doesNotMatch(emitters,/finiteFuel/);
 const {programs}=fixture();
 assert.match(programs[1].fragment,/gasHeatToWoodHeat\(gas.b\)/);
 assert.match(programs[1].fragment,/woodThermoStep\(old,wear,heat,delta,starter,oxygen,1\./);
 assert.match(programs[0].fragment,/normalizer\+=w\*exp/,'Depth emission normalizes against the actual discrete gas grid');
});

test('Current projected subtree mass has bounded donors and Euler ranges, independent of bond-local depletion',async()=>{
 const previousFetch=globalThis.fetch;
 globalThis.fetch=async name=>{const url=new URL(String(name),pathToFileURL(resolve(root,'index.html')));const bytes=await readFile(fileURLToPath(url));return{ok:true,json:async()=>JSON.parse(bytes),arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)};};
 try{
  const {gl}=fixture();gl.MAX_TEXTURE_SIZE=900;gl.getParameter=()=>4096;gl.texSubImage2D=gl.uniform3fv=gl.uniform1f=gl.uniform1i=gl.uniform3f=gl.clearBufferfv=()=>{};
  const structure=createWoodStructureGL(gl,{shared:'fixture shared',program:fragment=>({fragment}),uniform:(p,name)=>name,bind:()=>{}});
  const summaries=[];
  for(const name of['logs','house','wood-sigil','cybr-tree']){
   await structure.load(name);const asset=structure.asset;
   assert.ok(asset.massCount>0&&asset.massCount<=64**3);assert.equal(asset.massData.length,256*asset.massHeight*4);assert.ok(asset.states[0].height<=2048,'Atlas fits minimum WebGL2 texture dimension');
   const masses=Array.from({length:asset.massCount},(_,i)=>asset.massData[i*4+2]),total=masses.reduce((s,m)=>s+m,0);
   const rootPoint=10*4;assert.equal(asset.data[rootPoint],0);assert.equal(asset.data[rootPoint+1],asset.massCount);
   const ownMass=Array.from({length:asset.count},(_,i)=>asset.data[(Math.floor(i/4)*48+(i%4)*12+2)*4]).reduce((s,m)=>s+m,0);
   assert.ok(Math.abs(total-ownMass)/Math.max(total,1e-9)<.0001,'Corrected thermal columns conserve the authored graph mass');
   const perOwner=new Float64Array(asset.count),prefix=new Float64Array(asset.massCount+1);for(let j=0;j<asset.massCount;j++){const mass=asset.massData[j*4+2];perOwner[asset.massData[j*4+3]]+=mass;prefix[j+1]=prefix[j]+mass;}
   let maxOwnerError=0,maxSubtreeError=0;for(let i=0;i<asset.count;i++){const point=(Math.floor(i/4)*48+(i%4)*12)*4,own=asset.data[point+8],subtree=asset.data[point+9],start=asset.data[point+40],end=asset.data[point+41];maxOwnerError=Math.max(maxOwnerError,Math.abs(perOwner[i]-own));maxSubtreeError=Math.max(maxSubtreeError,Math.abs(prefix[end]-prefix[start]-subtree));assert.ok(Math.abs(perOwner[i]-own)<Math.max(2e-6,own*1e-5),'Each overlapping beam retains its physical mass');assert.ok(Math.abs(prefix[end]-prefix[start]-subtree)<Math.max(2e-6,subtree*1e-5),'Each subtree load matches the actual depth owners');}
   for(let i=0;i<asset.count;i++){const point=(Math.floor(i/4)*48+(i%4)*12+10)*4;assert.ok(asset.data[point]>=0&&asset.data[point+1]>=asset.data[point]&&asset.data[point+1]<=asset.massCount);}
   summaries.push({name,nodes:asset.count,donors:asset.massCount,projectedModelKg:total,graphModelKg:ownMass,maxOwnerErrorKg:maxOwnerError,maxSubtreeErrorKg:maxSubtreeError,atlasWidth:48,atlasHeight:asset.states[0].height});
   if(process.env.FIRE_STUDIO_WOOD_OUTPUT){const dir=resolve(process.env.FIRE_STUDIO_WOOD_OUTPUT);await mkdir(dir,{recursive:true});await writeFile(resolve(dir,name+'-graph.f32.bin'),new Uint8Array(asset.data.buffer));await writeFile(resolve(dir,name+'-donors.f32.bin'),new Uint8Array(asset.massData.buffer));await writeFile(resolve(dir,name+'-fixture.json'),JSON.stringify({name,nodes:asset.count,rows:asset.rows,width:48,height:asset.states[0].height,donors:asset.massCount,massHeight:asset.massHeight,base:asset.base,runtimeRoot:root}));}
  }
  if(process.env.FIRE_STUDIO_WOOD_OUTPUT)await writeFile(resolve(process.env.FIRE_STUDIO_WOOD_OUTPUT,'projected-mass-summary.json'),JSON.stringify(summaries,null,2));
  assert.match(woodMechanicsGLSL,/woodRemainingMassAt\(i\)\*pow\(worldScale,3\.\)/);assert.doesNotMatch(woodMechanicsGLSL,/9\.81\*clamp\(stock\+ch/);
  assert.match(woodMechanicsGLSL,/for\(int corner=0;corner<8;corner\+\+\)/,'Contact uses every rotated subtree AABB corner');
  structure.destroy();
 }finally{globalThis.fetch=previousFetch;}
});

test('Dropped wood retains exact cold thermal state and shared finite dry/char inventory',async()=>{
 const cold=advanceFloorWood({deposit:1.5,dt:0});assert.equal(cold.stock[0],1.5);assert.ok(Math.abs((300+1200*cold.stock[1])-293.15)<1e-9);
 const smoke=advanceFloorWood({...cold,incomingGasHeat:1,ignite:true,smokeOnly:true,dt:1/30});assert.deepEqual(smoke.stock,cold.stock);assert.deepEqual(smoke.wear,cold.wear);
 const first=advanceFloorWood({...cold,ignite:true,dt:1/30});let hot=first;
 for(let i=0;i<29;i++)hot=advanceFloorWood({...hot,incomingGasHeat:1,dt:1/30});
 assert.ok(hot.stock[0]<1.49&&hot.stock[3]>0&&hot.stock[2]>0&&hot.wear[1]<cold.wear[1]);assert.ok(hot.stock[0]+hot.stock[3]<1.5,'Gas/water products leave the finite material ledger');
 if(process.env.FIRE_STUDIO_WOOD_OUTPUT)await writeFile(resolve(process.env.FIRE_STUDIO_WOOD_OUTPUT,'floor-wood-reference.json'),JSON.stringify({cold,first,hot}));
});
