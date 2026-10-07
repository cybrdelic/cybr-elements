import test from 'node:test';
import assert from 'node:assert/strict';
import {originalAmbientScaleGLSL} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-shaders.js';

// Execute the actual scalar GLSL helper. A supplied acceleration must produce
// the same world velocity increment across unequal domain extents.
const body=originalAmbientScaleGLSL.slice(originalAmbientScaleGLSL.indexOf('{')+1,originalAmbientScaleGLSL.lastIndexOf('}')).replace('bool worldMotion','const worldMotion');
const scale=new Function('emitter','effect','sourceMode','extent',body);

test('Original cursor fire and fireball retain world acceleration across domains',()=>{
 for(const [emitter,effect] of [[0,-1],[23,23]]){
  for(const extent of [1.8,4,7.875,8,14])for(const acceleration of [-2,.05,.8,3.4]){
   const dt=1/30,normalized=acceleration*dt*scale(emitter,effect,0,extent);
   assert.ok(Math.abs(normalized*extent-acceleration*dt)<1e-14);
  }
 }
});

test('Every other Original emitter and the sigil retain their authored force units',()=>{
 for(let emitter=0;emitter<=45;emitter++)for(const effect of [-1,0,1,23]){
  if((emitter===0&&effect<0)||emitter===23)continue;
  assert.equal(scale(emitter,effect,0,14),1);
 }
 assert.equal(scale(0,-1,1,14),1);
 assert.equal(scale(23,23,1,8),1);
});
