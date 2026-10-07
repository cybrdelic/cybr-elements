// Collective barrier compatibility. Full Tint checking is in
// wgsl-uniformity-qa.mjs; native sparse gates verify allocation.
import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {brickPoolKernels,planBrickPool}=await import(pathToFileURL(resolve(root,'pyro-gpu/brick-pool.js')).href);

const plans=[
  ...[1,4,255,256,257,512,1024,4096].map(capacity=>({capacity})),
  ...[1,64,256,257,512].map(capacity=>({brick:32,capacity})),
];

test('every topology lane reaches every barrier across sparse, failure and dense paths',()=>{
  for(const options of plans){
    const code=brickPoolKernels(planBrickPool(options)).topology;
    const body=code.slice(code.indexOf('@compute')).replace(/\/\/[^\n]*/g,'');
    assert.doesNotMatch(body,/\b(return|discard|workgroupUniformLoad)\b/);
    let depth=0,barriers=0;
    for(const token of body.matchAll(/[{}]|\b(?:workgroupBarrier|storageBarrier)\s*\(/g)){
      if(token[0]==='{')depth++;
      else if(token[0]==='}')depth--;
      else{assert.equal(depth,1,'barriers must be outside every conditional and loop');barriers++;}
    }
    assert.equal(depth,0);assert.equal(barriers,9);
    assert.match(code,/if\(lane==0u\)\{mode=poolState\[0\];failureFlags=0u;\}/);
    assert.ok(code.indexOf('next[p]=current[p]')<code.indexOf('mode=poolState[0]'));
    assert.ok(code.indexOf('failureFlags|=1u')<code.indexOf('let mutate='));
    assert.ok(code.indexOf('let mutate=mode==0u&&failureFlags==0u;')<code.indexOf('poolState[16u+s]=0u'));
    assert.equal((code.match(/if\(mutate\)\{/g)||[]).length,2,'both release and allocation require successful sparse preflight');
    assert.match(code,/if\(lane==0u&&mutate\)\{poolState\[2\]=totals.x/);
    assert.match(code,/poolState\[0\]=1u;poolState\[7\]=1u/,'fallback remains sticky and migrates intact old pages');
    assert.doesNotMatch(code,/diagnostic\s*\(\s*off/);
  }
});
