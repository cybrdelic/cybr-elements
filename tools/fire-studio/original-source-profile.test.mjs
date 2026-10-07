import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const root=resolve(import.meta.dirname,'../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live');
const {FIRE_PRESETS}=await import(pathToFileURL(resolve(root,'pyro-gpu/presets.js')).href);
const {emitterKindFor}=await import(pathToFileURL(resolve(root,'original-source-profile.js')).href);

test('free fire and sooty plume share the broad Original inlet; Volume retains its continuous plume',async()=>{
 const plume=FIRE_PRESETS.find(p=>p.id==='sooty-plume');
 assert.ok(plume);
 assert.equal(plume.effect[0],0,'Effect zero selects the generic plume profile in the volume solver');
 assert.equal(plume.effect[3],1,'The plume remains a continuous source');
 assert.equal(emitterKindFor(plume),0,'Original routes the plume to its broad emitter, not the hearth tongues');
 assert.equal(emitterKindFor({id:'campfire',effect:[1]}),1,'Ordinary hearth sources keep their multi-tongue emitter');
 const emitters=await readFile(resolve(root,'fire-emitters.js'),'utf8');
 const legacy=(await readFile(resolve(root,'fire.js'),'utf8')+'\n'+await readFile(resolve(root,'original-shaders.js'),'utf8'));
 const volume=await readFile(resolve(root,'pyro-gpu/shaders.js'),'utf8');
 assert.match(emitters,/emitterKind==0&&sourceEffectKind<=0/);
 assert.match(legacy,/emitterKind==0&&sourceEffectKind<=0\?3\.5/,'Free fire and the plume receive the same large-scale roll-up confinement');
 assert.match(legacy,/sourceMomentumFraction\(fuelBeforeRelease,added\)/,'Source momentum follows the finite fuel dose');
 assert.match(volume,/p\.effect\.x<\.5&&p\.effect\.w>\.5/,'The volume solver keeps this continuous plume distinct from finite bursts');
 assert.match(volume,/vec3f\(\.62,\.20,\.44\)/,'The volume source uses a broad shallow footprint');
});


test('Original preserves shared heat/fuel channels and normalized room soot scattering',async()=>{
 const code=(await readFile(resolve(root,'fire.js'),'utf8')+'\n'+await readFile(resolve(root,'original-shaders.js'),'utf8'));
 assert.match(code,/\(profile\?\.power\?1:fuel\[0\]\*sourceShape\[2\]\)\*\(profile\?\.chemistry\[1\]\?\?1\)/);
 assert.match(code,/const sourceHeat=profile\?\.chemistry\[0\]\?\?1/);
 assert.match(code,/sootExtinction\(soot\)\*mix[^;]+\/12\.56637/);
 // Reset creates ambient gas with zero soot; no plume prewarming.
 assert.match(code,/clearBufferfv\(gl.COLOR, 1, new Float32Array\(\[0, 1, 0, 0\]\)\)/);
});
