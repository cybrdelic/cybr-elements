import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,'../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const source=readFileSync(resolve(root,'fire-ability-motions.js'),'utf8');
// Execute the shipped scalar contact routine. The independent oracle below
// samples the swept trajectory, so it does not reproduce the quadratic solve.
const body=source.match(/fn abilityFloorContact\([^]*?\)->f32\{([^]*?)\n\}/)[1].replace(/:(?:f32)=/g,'=');
const contact=new Function('a','b','arc','radius','floorY','const max=Math.max,sqrt=Math.sqrt;'+body);
const trajectory=(a,b,arc,u)=>a+(b-a)*u+4*arc*u*(1-u);
function oracle(a,b,arc,r,floor){
 const level=floor+r*.8;
 for(let i=1;i<=20000;i++){
  const u=i/20000,previous=(i-1)/20000;
  if(trajectory(a,b,arc,u)<=level&&trajectory(a,b,arc,previous)>level)return u;
 }return 2;
}
test('swept descending bodies hit the actual floor before penetrating it, across scale and elevated origins',()=>{
 for(const scale of [.2,.5,1,2])for(const originY of [.14,1.1,3])for(const arc of [0,.05,.28,.6])for(const r of [.13,.24,.44]){
  const floor=-originY/scale,a={y:floor+.8/scale+r},b={y:floor+.02/scale};
  const u=contact(a,b,arc,r,floor),sampled=oracle(a.y,b.y,arc,r,floor);
  assert.equal(u<=1,sampled<=1);
  if(u<=1){assert.ok(Math.abs(u-sampled)<.000051);assert.ok(Math.abs(trajectory(a.y,b.y,arc,u)-floor-r*.8)<1e-9);
   assert.ok(trajectory(a.y,b.y,arc,Math.max(0,u-.001))>=floor+r*.8);}
 }
});
test('aim points in air cannot trigger a false surface explosion',()=>{
 for(const arc of [0,.1,.4])for(const a of [1,2,4])for(const b of [.5,1,3])
  assert.equal(contact({y:a},{y:b},arc,.24,0),2);
 assert.equal(contact({y:.1},{y:0},0,.3,0),0,'initial downward overlap resolves immediately');
 assert.equal(contact({y:1},{y:.24},0,.3,0),1,'contact at the flight endpoint is retained');
});
test('the same scalar contact routine is used by both flight work bounds and source release',()=>{
 assert.ok(source.includes('let contact:f32=abilityFloorContact(a,b,arc,radius,floorY);'));
 const count=source.split('let contact:f32=abilityFloorContact(a,b,arc,radius,floorY);').length-1;
 assert.equal(count,2,'both paths share the same time of impact');
 assert.ok(source.includes('if(contact>1.){return vec4f(0);}'),'no endpoint sphere in empty air');
});

const app=readFileSync(resolve(root,'pyro-gpu/app.js'),'utf8');
const start=app.indexOf('  function powerAim(e) {'),end=app.indexOf('  function aimDirection',start);
const pickFactory=new Function('powerDefinition','activeFire','worldPoint','floorPoint','return ('+app.slice(start,end).trim()+');');
test('actual Volume picking distinguishes floor contacts from airborne targets and emitter height',()=>{
 const definition={floor:false},preset={minHeight:1.2};let hit=[1.1,.8];
 const pick=pickFactory(()=>definition,preset,e=>e.point,()=>hit);
 assert.deepEqual(pick({point:[1,.7,0]}),[1,.7,0],'aim below source placement minimum remains in air');
 assert.deepEqual(pick({point:[1,.1,0]}),[1.1,.14,.8],'floor ray supplies true horizontal depth');
 hit=null;assert.equal(pick({point:[1,.1,0]}),null,'outside-floor pointer cannot invent a hit');
 hit=[.5,-.2];definition.floor=true;
 assert.deepEqual(pick({point:[1,3,0]}),[.5,.14,-.2],'ground powers always use the floor ray');
});
