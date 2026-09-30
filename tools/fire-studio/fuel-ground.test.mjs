import test from 'node:test';import assert from 'node:assert/strict';
import {resolve} from 'node:path';import {fileURLToPath,pathToFileURL} from 'node:url';
const sourceRoot=fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {FuelBrush,floorHit,fuelHalf,groundFuelStep,groundVaporProfile}=await import(pathToFileURL(resolve(process.env.FIRE_STUDIO_ROOT||sourceRoot,'fuel-ground.js')).href);

test('floor picks reject invalid, behind, parallel and out-of-domain rays without clamping',()=>{
 const bounds={minX:-7,maxX:7,minZ:-.9,maxZ:.9};
 assert.deepEqual(floorHit([0,3,2],[0,-1,-2/3],bounds),[0,.01200000000000001]);
 for(const ray of [[0,1,0],[0,0,1],[10,-1,0],[NaN,-1,0],[0,-1,1]])assert.equal(floorHit([0,3,2],ray,bounds),null);
 assert.equal(floorHit([0,-1,0],[0,-1,0],bounds),null);
});
test('brush queues additive mass only, rejects invalid centers and returns stable R16F snapshots',()=>{
 const brush=new FuelBrush({width:128,height:128});assert.equal(brush.consume(),null);
 assert.equal(brush.stamp(NaN,0),false);assert.equal(brush.stamp(3.1,0),false);
 brush.stamp(0,0);const a=brush.consume();assert.equal(a.data.length,128*128);assert.ok(a.data.some(v=>v>0));assert.equal(brush.consume(),null);
 brush.stamp(0,0);brush.stamp(0,0);const b=brush.consume();assert.ok(b.data[64*128+64]>a.data[64*128+64]);
 const stable=a.data.slice();brush.stamp(0,0);brush.clear();assert.equal(brush.consume(),null);assert.deepEqual(a.data,stable);
 assert.equal(fuelHalf(4),0x4400);assert.equal(fuelHalf(1),0x3c00);assert.equal(fuelHalf(0),0);assert.equal(fuelHalf(1/2),0x3800);
});
test('strokes cover world-space paths while no-motion and invalid paths add no mass',()=>{
 const brush=new FuelBrush();assert.equal(brush.stroke([0,0],[0,0]),false);assert.equal(brush.stroke([0,0],[9,0]),false);
 assert.equal(brush.stroke([-1,0],[1,0]),true);const data=brush.consume().data;
 for(let x=44;x<84;x++)assert.ok(data[64*128+x]>0);
});
test('cold deposits stay unlit; sustained actual heat releases finite mass through normal gas source',()=>{
 let cold={fuel:0,heat:0,char:0},hot={fuel:0,heat:0,char:0},released=0;
 for(let i=0;i<1200;i++){
  cold=groundFuelStep(cold,0,i===0?.65:0,1/30);hot=groundFuelStep(hot,1,i===0?.65:0,1/30);released+=hot.release/30;
 }
 assert.equal(cold.fuel,.65);assert.equal(cold.heat,0);assert.equal(cold.release,0);assert.equal(cold.char,0);
 assert.ok(hot.fuel<1e-12);assert.ok(Math.abs(released+hot.fuel-.65)<1e-12);assert.ok(Math.abs(hot.char-released)<1e-12);
 const next=groundFuelStep(hot,0,0,1/30);assert.ok(next.heat<hot.heat);assert.ok(next.release<1e-12);
});
test('vertical vapor profile integrates surface release once and clips outside its source layer',()=>{
 let integral=0;const n=10000;for(let i=0;i<n;i++)integral+=groundVaporProfile((i+.5)*.24/n)*.24/n;
 assert.ok(Math.abs(integral-1)<1e-7);assert.equal(groundVaporProfile(-.01),0);assert.equal(groundVaporProfile(.25),0);
});
test('explicit ignition is one finite thermal impulse on existing fuel, with no deposit-time heat',()=>{
 const cold=groundFuelStep({fuel:.65,heat:0,char:0},0,0,1/30);assert.equal(cold.heat,0);assert.equal(cold.release,0);
 const lit=groundFuelStep(cold,0,0,1/30,true);assert.equal(lit.heat,1.2);assert.ok(lit.fuel<cold.fuel);assert.ok(lit.release>0);
 const cooling=groundFuelStep(lit,0,0,1/30);assert.ok(cooling.heat<lit.heat,'Impulse does not repeat');
 const empty=groundFuelStep({fuel:0,heat:0,char:0},0,0,1/30,true);assert.equal(empty.heat,0);assert.equal(empty.release,0);
});
test('actual smoke simulations disable reservoir ignition, release and stock consumption',()=>{
 let state={fuel:.65,heat:0,char:0};
 for(let i=0;i<300;i++)state=groundFuelStep(state,1,0,1/30,i===0,false);
 assert.equal(state.fuel,.65);assert.equal(state.char,0);assert.equal(state.release,0);assert.ok(state.heat>.65,'Actual sampled heat still reaches the material');
});
