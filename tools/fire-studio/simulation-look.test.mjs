import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const sourceRoot=fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const root=resolve(process.env.FIRE_STUDIO_ROOT||sourceRoot);
const moduleURL=file=>pathToFileURL(resolve(root,file)).href;
const {cleanLook,lookStore}=await import(moduleURL('look-storage.js'));
const {filterLibrary,libraryItemSimulation}=await import(moduleURL('pyro-gpu/library.js'));
const {ALL_FIRE_PRESETS,FIRE_PRESETS,LEGACY_PRESETS}=await import(moduleURL('pyro-gpu/presets.js'));
const memory=initial=>{const data=new Map(initial);return {getItem:key=>data.get(key),setItem:(key,value)=>data.set(key,value)};};

test('saved sparse looks retain mode independently of the shared source ID',()=>{
  const storage=memory(),store=lookStore(storage,ALL_FIRE_PRESETS);
  store.add({name:'Sparse sigil',fire:'sigil-cybr',simulation:'sparse',sourceGuide:false,fireLight:0,lights:{ambient:1,key:220},camera:{zoom:2,angle:0,pan:[0,1]}});
  const reloaded=lookStore(storage,ALL_FIRE_PRESETS);assert.equal(reloaded.items[0].simulation,'sparse');
  const exported=reloaded.export();assert.equal(exported.version,1);
  const imported=lookStore(memory(),ALL_FIRE_PRESETS);assert.equal(imported.import(exported),1);assert.deepEqual(imported.items,reloaded.items);
  const copy=imported.items;copy[0].simulation='volume';assert.equal(imported.items[0].simulation,'sparse');
});

test('existing version-one looks infer their original modes and incompatible modes normalize',()=>{
  const old=memory([['cybr-pyro-library-v1',JSON.stringify([{name:'Original',fire:'legacy:sigil'},{name:'Volume',fire:'bonfire'}])]]);
  assert.deepEqual(lookStore(old,ALL_FIRE_PRESETS).items.map(item=>item.simulation),['legacy','volume']);
  assert.equal(cleanLook({name:'Original',fire:'legacy:sigil',simulation:'sparse'},ALL_FIRE_PRESETS).simulation,'legacy');
  assert.equal(cleanLook({name:'Volume',fire:'bonfire',simulation:'invalid'},ALL_FIRE_PRESETS).simulation,'volume');
});

test('sparse library uses the complete shared volume catalog without duplicating source IDs',()=>{
  const sparse=filterLibrary(ALL_FIRE_PRESETS,'','sparse');
  assert.deepEqual(sparse.map(item=>item.id),FIRE_PRESETS.map(item=>item.id));
  assert.equal(new Set(sparse.map(item=>item.id)).size,FIRE_PRESETS.length);
  assert.equal(filterLibrary(ALL_FIRE_PRESETS,'','current','bonfire','sparse').length,FIRE_PRESETS.length);
  assert.equal(filterLibrary(ALL_FIRE_PRESETS,'','legacy').length,LEGACY_PRESETS.length);
  assert.equal(filterLibrary(ALL_FIRE_PRESETS,'sparse voxels','sparse').length,FIRE_PRESETS.length);
});

test('shared source applications follow the selected filter while saved looks retain their mode',()=>{
  const source={id:'bonfire',name:'Bonfire'};
  assert.equal(libraryItemSimulation(source,'current','bonfire','sparse'),'sparse');
  assert.equal(libraryItemSimulation(source,'volume','bonfire','sparse'),'volume');
  assert.equal(libraryItemSimulation(source,'sparse','legacy:sigil','legacy'),'sparse');
  assert.equal(libraryItemSimulation(source,'all','bonfire','sparse'),'sparse');
  assert.equal(libraryItemSimulation({id:'legacy:sigil'},'sparse','bonfire','sparse'),'legacy');
  const saved=[{name:'Sparse',fire:'bonfire',simulation:'sparse'},{name:'Dense',fire:'bonfire',simulation:'volume'}];
  assert.deepEqual(filterLibrary(saved,'','current','bonfire','sparse').map(item=>item.name),['Sparse']);
  assert.deepEqual(filterLibrary(saved,'','volume').map(item=>item.name),['Dense']);
  assert.equal(libraryItemSimulation(saved[0],'volume','bonfire','volume'),'sparse');
  assert.equal(filterLibrary([{id:'fully-lit',kind:'lighting',name:'Fully lit'}],'','sparse').length,1);
});
