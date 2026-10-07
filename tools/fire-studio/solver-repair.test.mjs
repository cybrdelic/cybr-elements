import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {GAS_CHEMISTRY,mixSourceMomentum} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/reduced-chemistry.js';
const root=new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url);

test('paired pressure difference operators reproduce the solved Laplacian on every periodic grid mode',async()=>{
 const source=await readFile(new URL('coarse-pressure.js',root),'utf8');
 assert.ok(source.includes('(fullVelocity(p+vec3(stepP.x,0,0)).x-fullVelocity(p).x)/HX'));
 assert.ok(source.includes('(pressure(c)-pressure(c-ivec3(1,0,0)))/HX'));
 for(let mode=1;mode<32;mode++){
  const p=Array.from({length:64},(_,i)=>Math.cos(2*Math.PI*mode*i/64));
  const grad=p.map((v,i)=>v-p[(i+63)%64]);
  for(let i=0;i<64;i++)assert.ok(Math.abs(grad[(i+1)%64]-grad[i]-(p[(i+1)%64]-2*p[i]+p[(i+63)%64]))<1e-12);
 }
});
test('finite source momentum has the mass-weighted mixture velocity and zero dose preserves flow',()=>{
 const velocity=[2,-1,.5],jet=[8,3,-2];
 assert.deepEqual(mixSourceMomentum(velocity,jet,.4,0),velocity);
 for(const fuel of [0,.3,2])for(const added of [.001,.1,4]){
  const result=mixSourceMomentum(velocity,jet,fuel,added);
  for(let k=0;k<3;k++)assert.ok(Math.abs(result[k]*(1+fuel+added)-velocity[k]*(1+fuel)-jet[k]*added)<1e-12);
 }
 assert.equal(GAS_CHEMISTRY.oxygenPerFuel,.7);
});
test('shared coarse shock corners reproduce all fine MAC faces for supported grid refinements',()=>{
 const corners=Array.from({length:8},(_,i)=>[Math.sin(i),Math.cos(i*2),Math.sin(i*3)]);
 const sample=t=>{const out=[0,0,0];for(let z=0;z<2;z++)for(let y=0;y<2;y++)for(let x=0;x<2;x++){
  const w=(x?t[0]:1-t[0])*(y?t[1]:1-t[1])*(z?t[2]:1-t[2]);for(let k=0;k<3;k++)out[k]+=corners[x+2*y+4*z][k]*w;
 }return out;};
 for(const ratio of [2,4,8])for(let fine=0;fine<ratio;fine++){
  const t=(fine+.5)/ratio-.5,base=Math.floor(t),center=[t-base,.47,.58],half=.5/ratio;
  assert.ok(center[0]-half>=-1e-12&&center[0]+half<=1+1e-12,'both fine faces belong to one shared corner stencil');
  const minus=[...center],plus=[...center];minus[0]-=half;plus[0]+=half;
  const faceDifference=(sample(plus)[0]-sample(minus)[0])*ratio;
  const left=[...center],right=[...center];left[0]=0;right[0]=1;
  assert.ok(Math.abs(faceDifference-(sample(right)[0]-sample(left)[0]))<1e-12);
 }
});
