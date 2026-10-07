import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT)
  :fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const source=readFileSync(path.join(root,'scene-lights.js'),'utf8');
const storageKey='cybr-fire-lights-v1';

// Execute the actual catalog/control/binding code with a small DOM contract.
// No rendering is emulated, so this does not certify brightness or clipping.
function fixture(saved,room=true){
  const stored=new Map(saved?[[storageKey,JSON.stringify(saved)]]:[]),events=[],controls=[],outputs=new Map();
  const select={value:'',onchange:null};
  const roomToggle={checked:room,listeners:new Map(),addEventListener(type,fn){this.listeners.set(type,fn);}};
  const panel={
    html:'',
    set innerHTML(html){
      this.html=html;
      for(const [,attributes] of html.matchAll(/<input\b([^>]*data-light="[^"]+"[^>]*)>/g)){
        const attribute=k=>new RegExp(`\\b${k}="([^"]*)"`).exec(attributes)?.[1]??'';
        const control={dataset:{light:attribute('data-light')},type:attribute('type'),min:attribute('min'),max:attribute('max'),step:attribute('step'),value:'',listeners:new Map(),
          addEventListener(type,fn){this.listeners.set(type,fn);}};
        controls.push(control);outputs.set(control.dataset.light,{value:''});
      }
    },
    querySelectorAll(selector){assert.equal(selector,'[data-light]');return controls;},
    querySelector(selector){
      if(selector==='#lighting-preset')return select;
      const control=/\[data-light="([^"]+)"\]/.exec(selector);
      if(control)return controls.find(c=>c.dataset.light===control[1]);
      const output=/\[data-value="([^"]+)"\]/.exec(selector);
      if(output)return outputs.get(output[1]);
      throw Error('Unexpected lighting selector: '+selector);
    },
  };
  const window={dispatchEvent(event){events.push(event.type);}};
  const sandbox={window,Event,URL,location:{href:'https://example.com/firesim/?room='+(room?'1':'0')},
    document:{querySelector(selector){if(selector==='#lighting-controls')return panel;if(selector==='#room')return roomToggle;throw Error(selector);}},
    localStorage:{getItem:key=>stored.get(key)??null,setItem:(key,value)=>stored.set(key,value)}};
  vm.runInNewContext(source,sandbox,{filename:path.join(root,'scene-lights.js')});
  return {lights:window.SceneLights,stored,events,controls,panel,select,roomToggle};
}
const plain=value=>JSON.parse(JSON.stringify(value));

test('fully lit is a complete neutral inspection preset in the existing select and catalog',()=>{
  const f=fixture(),preset=f.lights.catalog.find(p=>p.id==='fully-lit');
  assert.ok(preset);assert.equal(preset.name,'Fully lit · neutral');assert.equal(preset.diagnostic,true);
  assert.match(preset.description,/room markings, source surfaces and cold smoke/);
  assert.match(f.panel.html,/<optgroup label="Inspection rigs">[^]*<option value="fully-lit">Fully lit · neutral<\/option>[^]*<\/optgroup>/);
  for(const key of ['tint','keyColor','rimColor'])assert.equal(preset.values[key],'#ffffff');
  for(const control of f.controls){
    const value=preset.values[control.dataset.light];
    if(control.type==='color')assert.match(value,/^#[0-9a-f]{6}$/i);
    else assert.ok(Number.isFinite(value)&&value>=+control.min&&value<=+control.max,control.dataset.light);
  }
  assert.ok(preset.values.ambient>f.lights.catalog.find(p=>p.id==='gallery').values.ambient);
  assert.equal(preset.values.keyBeam,85);assert.equal(preset.values.rimBeam,85);
  assert.ok(preset.values.key<350&&preset.values.rim<350);
  assert.equal(f.lights.revision,0);
});

test('selection persists, reload restores it, and transient inspections preserve the saved rig',()=>{
  const f=fixture(),preset=f.lights.catalog.find(p=>p.id==='fully-lit');
  f.select.onchange({target:{value:'fully-lit'}});
  assert.deepEqual(plain(f.lights.snapshot),plain(preset.values));
  assert.equal(f.select.value,'fully-lit');assert.equal(f.lights.revision,1);
  assert.deepEqual(f.events,['scene-light-change']);
  const saved=JSON.parse(f.stored.get(storageKey)),reloaded=fixture(saved);
  assert.deepEqual(plain(reloaded.lights.snapshot),saved);assert.equal(reloaded.select.value,'fully-lit');
  reloaded.lights.setTransient(true);assert.equal(reloaded.lights.apply('fire'),true);
  assert.deepEqual(JSON.parse(reloaded.stored.get(storageKey)),saved);
  reloaded.lights.setTransient(false);assert.equal(reloaded.lights.apply('fully-lit'),true);
  assert.deepEqual(JSON.parse(reloaded.stored.get(storageKey)),saved);
});

test('existing clamps still sanitize imports and stored state without changing the room',()=>{
  const f=fixture({ambient:9,key:Infinity,rim:-50,keyColor:'invalid'},false);
  assert.equal(f.lights.snapshot.ambient,2);assert.equal(f.lights.snapshot.key,0);assert.equal(f.lights.snapshot.rim,0);
  assert.equal(f.roomToggle.checked,false);
  assert.equal(f.lights.apply('fully-lit'),true);assert.equal(f.roomToggle.checked,false);
  assert.equal(f.panel.querySelector('[data-light="bounce"]').disabled,true);
  const color=f.lights.snapshot.keyColor;
  assert.equal(f.lights.apply({ambient:99,key:999,rim:-3,keyHeight:-10,bounce:Infinity,keyColor:'bad'}),true);
  assert.equal(f.lights.snapshot.ambient,2);assert.equal(f.lights.snapshot.key,350);assert.equal(f.lights.snapshot.rim,0);
  assert.equal(f.lights.snapshot.keyHeight,1);assert.equal(f.lights.snapshot.bounce,.6);assert.equal(f.lights.snapshot.keyColor,color);
  assert.equal(f.lights.apply('missing'),false);
});

test('fully lit binds finite neutral illumination through the existing two spotlights',()=>{
  const f=fixture();f.lights.apply('fully-lit');
  const values=new Map(),gl={
    uniform3fv:(name,value)=>values.set(name,[...value]),
    uniform1f:(name,value)=>values.set(name,value),
    uniform2f:(name,...value)=>values.set(name,value),
  };
  f.lights.bind(gl,name=>name,true);
  assert.deepEqual(values.get('ambientLight'),[1,1,1]);assert.equal(values.get('bounceGain'),.6);
  assert.deepEqual(values.get('spotPower[0]'),[180,180,180]);assert.deepEqual(values.get('spotPower[1]'),[140,140,140]);
  for(let index=0;index<2;index++){
    assert.ok(Math.abs(Math.hypot(...values.get(`spotDirection[${index}]`))-1)<1e-12);
    const [outer,inner]=values.get(`spotCone[${index}]`);assert.ok(inner>outer&&outer>0&&inner<1);
  }
  for(const value of values.values())assert.ok((Array.isArray(value)?value:[value]).every(Number.isFinite));
  f.lights.bind(gl,name=>name,false);assert.equal(values.get('bounceGain'),0);
  assert.equal(f.lights.active,true);
});
