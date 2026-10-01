// Architecture regression for the two collective topology exits. Full Tint
// checking is in wgsl-uniformity-qa.mjs; native sparse gates verify allocation.
import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {brickPoolKernels,planBrickPool}=await import(pathToFileURL(resolve(root,'pyro-gpu/brick-pool.js')).href);

test('topology mode and failure exits explicitly broadcast workgroup-wide decisions',()=>{
  for(const options of [{capacity:4},{capacity:1024},{brick:32,capacity:64}]){
    const code=brickPoolKernels(planBrickPool(options)).topology;
    assert.doesNotMatch(code,/if\(poolState\[0\]==1u\)\{return;\}/);
    assert.match(code,/if\(lane==0u\)\{mode=poolState\[0\];\}/);
    assert.match(code,/if\(workgroupUniformLoad\(&mode\)==1u\)\{return;\}/);
    assert.match(code,/let failed=workgroupUniformLoad\(&failureFlags\);if\(failed!=0u\)\{return;\}/);
    assert.ok(code.indexOf('next[p]=current[p]')<code.indexOf('workgroupUniformLoad(&mode)'));
    assert.ok(code.indexOf('workgroupUniformLoad(&failureFlags)')<code.indexOf('poolState[16u+s]=0u'));
    assert.match(code,/poolState\[0\]=1u;poolState\[7\]=1u/,'fallback remains sticky and migrates intact old pages');
    assert.doesNotMatch(code,/diagnostic\s*\(\s*off/);
  }
});
