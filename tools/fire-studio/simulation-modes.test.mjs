import test from 'node:test';
import assert from 'node:assert/strict';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { readFileSync } from 'node:fs';
const root=resolve(process.env.FIRE_STUDIO_ROOT || resolve(import.meta.dirname,'../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load=file=>import(pathToFileURL(resolve(root,file)).href);
const {readSimulation,volumeOptions,modeForFire,runtimeFamily}=await load('simulation-modes.js');
const {writeLook}=await load('studio-location.js');
const {matchingPreset}=await load('preset-pairs.js');
const {inspectionState}=await load('inspection-state.js');

test('canonical sparse links and old brick links select the real volume family',()=>{
  for(const query of ['simulation=sparse','simulation=volume&bricks=1']){
    assert.equal(readSimulation(new URLSearchParams(query)),'sparse');
  }
  assert.equal(readSimulation(new URLSearchParams('simulation=legacy&bricks=1')),'legacy');
  assert.equal(readSimulation(new URLSearchParams('simulation=volume')),'volume');
  assert.equal(readSimulation(new URLSearchParams('simulation=unknown')),'legacy');
  assert.equal(runtimeFamily('sparse'),'volume');
  assert.equal(modeForFire('legacy:sigil','sparse'),'legacy');
  const url=writeLook(new URL('https://example.com/firesim/?simulation=volume&bricks=1&qa=1'),
    {simulation:'sparse',fire:'sigil-cybr',room:true,fuel:'wood',sourceGuide:true});
  assert.equal(url.searchParams.get('simulation'),'sparse');
  assert.equal(url.searchParams.get('firePreset'),'sigil-cybr');
  assert.equal(url.searchParams.get('bricks'),null);
  assert.equal(url.searchParams.get('qa'),'1');
});

test('sparse mode enables only pooled chemistry regardless of stale developer flags',()=>{
  const flags=new URLSearchParams('solver=adaptive&pressureWork=1&bricks=1&lightWork=1&receivers=1');
  assert.deepEqual(volumeOptions(flags,'sparse'),{
    adaptive:false,pressureWork:false,brickPool:true,lightWork:false,lightReceivers:false,
  });
  assert.equal(volumeOptions(flags,'volume').brickPool,false);
  assert.deepEqual(volumeOptions(new URLSearchParams(),'volume'),{
    adaptive:false,pressureWork:false,brickPool:false,lightWork:false,lightReceivers:false,
  });
  const loader=readFileSync(resolve(root,'runtime-loader.js'),'utf8');
  assert.match(loader,/kind === 'volume' \|\| kind === 'sparse'.*mountVolume/);
});

test('both volume modes share source IDs and retain inspection camera model',()=>{
  assert.equal(matchingPreset('sparse','legacy:sigil'),'sigil-cybr');
  assert.equal(matchingPreset('sparse','sigil-cybr'),'sigil-cybr');
  assert.equal(matchingPreset('volume','sigil-cybr'),'sigil-cybr');
  assert.equal(matchingPreset('legacy','sigil-cybr'),'legacy:sigil-cybr');
  const inspection=inspectionState(),camera={zoom:1.8,angle:45,pan:[.2,-.1]};
  inspection.enter({camera},'volume');
  assert.deepEqual(inspection.leave('sparse').camera,camera);
  inspection.enter({camera},'sparse');
  assert.equal(inspection.leave('legacy').camera,undefined);
});
