import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {supportTexture,guideUV,crossing,traceGuide} from './sigil-guide-reference.mjs';

const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {rendererShaders}=await import(pathToFileURL(path.join(root,'pyro-gpu/renderer.js')).href);
const {simulationShaders}=await import(pathToFileURL(path.join(root,'pyro-gpu/shaders.js')).href);
const raw=fs.readFileSync(path.join(root,'source/source-native.rgba8.bin'));
const texture=supportTexture(raw,896,504);
const location=(x,y)=>{const uv=[(x+.5)/896,(y+.5)/504];return [((uv[0]*14-7)/4)*1.8,1+((uv[1]*7.875-2.95)/4)*1.8,0];};

test('native guide coordinates reproduce the exact live source UV and zero texture border',()=>{
 const source=simulationShaders().correctScalar;
 assert.match(source,/vec2f\(\(q\.x\*4\.\+7\.\)\/14\.,\(q\.y\*4\.\+2\.95\)\/7\.875\)/);
 for(const [x,y] of [[0,0],[895,503],[123,401],[650,82]]){
  const p=location(x,y),uv=guideUV([p[0]/1.8,(p[1]-1)/1.8,0]);
  assert.ok(Math.abs(uv[0]-(x+.5)/896)<1e-12);assert.ok(Math.abs(uv[1]-(y+.5)/504)<1e-12);
 }
 for(let x=0;x<896;x++){assert.equal(texture.read(x,0),0);assert.equal(texture.read(x,503),0);}
 for(let y=0;y<504;y++){assert.equal(texture.read(0,y),0);assert.equal(texture.read(895,y),0);}
});

test('front and back caps retain native contour support and both orientations',()=>{
 let hits=0,misses=0;
 for(let y=0;y<504;y+=7)for(let x=0;x<896;x+=7){
  const at=location(x,y);if(at[1]<=.01||Math.abs(at[0])>2.87)continue;
  const active=texture.read(x,y)>=.5;
  for(const sign of [-1,1]){
   const hit=traceGuide(texture,[at[0],at[1],4*sign],[0,0,-sign]);
   assert.equal(hit.distance<100,active,`native pixel ${x},${y}`);
   if(active){assert.ok(Math.abs(hit.distance-(4-.018*1.8))<1e-9);assert.deepEqual(hit.normal,[0,0,sign]);hits++;}else misses++;
  }
 }
 assert.ok(hits>500&&misses>5000);
});

test('bilinear contour detects a narrow interior crossing when both endpoints are empty',()=>{
 const root=crossing([.4,.9,.9,.4],[0,0],[1,1]);
 const expected=(1-Math.sqrt(.6))/2;
 assert.ok(Math.abs(root-expected)<1/4096);
 assert.equal(crossing([0,0,0,0],[.2,.2],[.7,.7]),2);
});

test('finite substrate has lateral walls at edge-on views, including negative ray direction',()=>{
 const bytes=new Uint8Array(8*8*4);for(let y=0;y<8;y++)bytes[(y*8+4)*4]=255;
 const small=supportTexture(bytes,8,8),y=1+((4.5/8*7.875-2.95)/4)*1.8;
 const left=traceGuide(small,[-4,y,0],[1,0,0]);
 const right=traceGuide(small,[4,y,0],[-1,0,0]);
 assert.ok(Math.abs(left.distance-4)<.002);assert.ok(Math.abs(right.distance-(4-.7875))<.002);
 assert.equal(left.normal[0],-1);assert.equal(right.normal[0],1);
 assert.ok(Math.abs(left.normal[1])+Math.abs(right.normal[1])<1e-12);
 assert.ok(left.cells<=20&&right.cells<=20);
});

test('existing nearer surface, disabled guide and floor clipping are respected',()=>{
 const bytes=new Uint8Array(8*8*4).fill(255),solid=supportTexture(bytes,8,8);
 const settings={source:[0,1,0],scale:1.8};
 assert.equal(traceGuide(solid,[0,1,4],[0,0,-1],2,settings).distance,2);
 assert.equal(traceGuide(solid,[0,1,4],[0,0,-1],100,{...settings,kind:0}).distance,100);
 assert.equal(traceGuide(solid,[0,-.01,4],[0,0,-1],100,settings).distance,100);
});

test('every actual render family uses guide and fuel only through physical surface composition',()=>{
 for(const tree of [false,true])for(const sparse of [false,true])for(const fast of sparse?[false,true]:[false]){
  const {render,light,room}=rendererShaders(tree,sparse,fast);
  assert.match(render,/@binding\(31\) var guideSource:texture_2d<f32>/);
  assert.match(render,/@binding\(32\) var floorFuel:texture_2d<f32>/);
  assert.ok(render.indexOf('let guide=sigilGuideHit')<render.lastIndexOf('let end=min(limit'));
  assert.match(render,/if\(guide\.w<limit\)\{limit=guide\.w/);
  assert.match(render,/let hdr=sum\+T\*surface/);
  assert.match(render,/let step=6\.\/256\./);assert.match(render,/i<512u/);
  assert.match(render,/if\(cam\.right\.w>\.5&&hit\.y>\.9\)/);
  assert.match(render,/pow\(max\(bed\.y-\.5,0\.\),3\.\)/);
  // The renderer import deliberately excludes simulation-only p.shape helpers.
  assert.doesNotMatch(render,/fn floorFeed|fn floorWork/);
  assert.match(light,/@compute/);assert.match(room,/@binding\(8\) var roomOut/);
 }
});
