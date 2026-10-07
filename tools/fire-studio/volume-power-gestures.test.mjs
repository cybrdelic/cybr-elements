// Execute the production pointer callbacks against the real Volume cast pool.
// Hit testing and DOM targets are CPU fixtures; no browser or GPU is created.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,
  '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const load=file=>import(pathToFileURL(resolve(root,file)).href);
const app=readFileSync(resolve(root,'pyro-gpu/app.js'),'utf8');
const {PyroSolver}=await load('pyro-gpu/solver.js');
const {POWER_DEFINITIONS,powerDefinition,powerDirection,normalizePowerSettings}=await load('fire-powers.js');

function functionSource(name){
  const match=new RegExp('^  function '+name+'\\(','m').exec(app);
  assert.ok(match,'production '+name+' exists');
  let depth=0,quote=null,comment=null;
  for(let i=app.indexOf('{',match.index);i<app.length;i++){
    const c=app[i],next=app[i+1];
    if(comment==='line'){if(c==='\n')comment=null;continue;}
    if(comment==='block'){if(c==='*'&&next==='/'){comment=null;i++;}continue;}
    if(quote){if(c==='\\')i++;else if(c===quote)quote=null;continue;}
    if(c==='/'&&next==='/'){comment='line';i++;continue;}
    if(c==='/'&&next==='*'){comment='block';i++;continue;}
    if(c==="'"||c==='"'||c==='`'){quote=c;continue;}
    if(c==='{')depth++;
    if(c==='}'&&--depth===0)return app.slice(match.index,i+1);
  }
  throw Error('Unterminated production '+name);
}
const pointerStart=app.indexOf("  on(view, 'pointerdown', (e) => {");
const pointerEnd=app.indexOf("  on(view, 'contextmenu'",pointerStart);
assert.ok(pointerStart>=0&&pointerEnd>pointerStart,'actual pointer callback block exists');
const pointerSource=app.slice(pointerStart,pointerEnd);

function target(){
  const listeners=new Map(),captures=new Set();
  return {listeners,dataset:{},setPointerCapture:id=>captures.add(id),
    hasPointerCapture:id=>captures.has(id),releasePointerCapture:id=>captures.delete(id),
    focus(){},setAttribute(){},dispatchEvent(){},
    emit(name,properties={}){
      const e={pointerId:7,pointerType:'mouse',button:0,point:[1.5,1.2,.3],
        preventDefault(){},...properties};
      for(const callback of listeners.get(name)||[])callback(e);
    }};
}
function fixture(definition){
  const solver=Object.create(PyroSolver.prototype);
  Object.assign(solver,{effect:[definition.kind+21,1,.18,0],source:[0,1.1,0],
    powerDirection:[1,0,0],powerStrength:1,burstAge:2,time:3,seed:2,stateEpoch:0,
    maxSpeed:1,active:false,previousDt:1/60,lightReady:true,
    device:{createTexture(){throw Error('Unexpected gesture GPU allocation');},
      createBuffer(){throw Error('Unexpected gesture GPU allocation');}}});
  const view=target(),window=target(),elements=new Map();
  const $=id=>{if(!elements.has(id))elements.set(id,target());return elements.get(id);};
  const on=(where,name,handler)=>{
    if(!where.listeners.has(name))where.listeners.set(name,[]);
    where.listeners.get(name).push(handler);
  };
  const setup=new Function('solver','activeFire','view','window','$','on',
    'powerDefinition','powerDirection','normalizePowerSettings',`
      let gesture=null,activeTool='fire',paused=false,pan=[0,0],resetPending=false,pendingSourceActions=[];
      const scope={disposed:false};
      let powers=normalizePowerSettings({heading:0,elevation:0,strength:1});
      const worldPoint=e=>e.point.slice(0,2),powerPoint=e=>e.point,
        powerAim=e=>e.point,locationPoint=e=>e.point;
      const sync=()=>{},markDirty=()=>{},placeFuel=()=>{};
      const message={textContent:''};
      const burst=()=>solver.castPower(solver.source,powerDirection(powers),powers.strength);
      ${functionSource('aimDirection')}
      ${functionSource('sourceAction')}
      ${functionSource('cast')}
      ${functionSource('tool')}
      ${pointerSource}
      return {tool,state:()=>({gesture,activeTool,paused})};
    `);
  const api=setup(solver,{power:definition.id},view,window,$,on,
    powerDefinition,powerDirection,normalizePowerSettings);
  return {solver,view,window,...api};
}

test('all hold-capable abilities aim and release one new cast without moving earlier actors',()=>{
  const held=POWER_DEFINITIONS.filter(p=>p.hold);
  assert.equal(held.length,4,'the current registry has four charge controls');
  for(const definition of held){
    const f=fixture(definition),s=f.solver;
    s.castPower([-.5,1.1,0],[1,0,0],1);s.powerCasts.step(.1);
    const earlier=s.powerCasts.snapshot().casts[0],origin=[...s.source];
    f.view.emit('pointerdown');
    let state=s.powerCasts.snapshot();
    assert.equal(state.active,2,definition.id);assert.equal(state.held,true);
    assert.deepEqual(state.casts[0],earlier,'earlier launch state is retained');
    assert.deepEqual(state.casts[1].origin,origin,'charge remains at the caster');
    s.powerCasts.step(.4);
    let requestedAim=null;const productionAim=s.aimPower;
    s.aimPower=function(at,direction){requestedAim=[...at];return productionAim.call(this,at,direction);};
    f.view.emit('pointermove',{point:[1.2,1.6,-.8]});
    const aimed=s.powerCasts.snapshot().casts[1];
    assert.deepEqual(requestedAim,[1.2,1.6,-.8],'the callback delivers the latest pointer aim to the real pool');
    assert.deepEqual(aimed.origin,origin);
    assert.ok(aimed.target.every((v,i)=>v>=s.powerCasts.bounds.min[i]&&v<=s.powerCasts.bounds.max[i]),
      'the pool applies the authored impact/fan reservation inside the domain');
    f.view.emit('pointerup',{point:[1.2,1.6,-.8]});
    state=s.powerCasts.snapshot();
    assert.equal(state.active,2);assert.equal(state.held,false);
    assert.deepEqual(state.casts[1].target,aimed.target,'release preserves the bounded aim');
    assert.equal(state.casts[1].age,definition.windup,'release starts the authored travel phase');
    const released=structuredClone(state);
    f.view.emit('pointerup');assert.deepEqual(s.powerCasts.snapshot(),released,'release is idempotent');
  }
});

test('cancel and lost capture act only on the owning pointer, including delayed old events',()=>{
  for(const name of ['pointercancel','lostpointercapture']){
    const f=fixture(powerDefinition('fireball')),s=f.solver;
    s.castPower([-.5,1.1,0],[1,0,0],1);
    f.view.emit('pointerdown',{pointerId:7});
    const before=structuredClone(s.powerCasts.snapshot());
    f.view.emit(name,{pointerId:99});
    assert.deepEqual(s.powerCasts.snapshot(),before,'unrelated '+name+' preserves the charge');
    assert.equal(f.state().gesture.id,7);
    f.view.emit(name,{pointerId:7});
    assert.equal(s.powerCasts.snapshot().active,1,'cancellation keeps the previous released cast');
    assert.equal(f.state().gesture,null);
    f.view.emit('pointerup',{pointerId:7});
    assert.equal(s.powerCasts.snapshot().active,1,'cancellation cannot later release');
    f.view.emit('pointerdown',{pointerId:8});
    f.view.emit(name,{pointerId:7});
    assert.equal(s.powerCasts.snapshot().held,true,'delayed old event preserves the new charge');
    assert.equal(f.state().gesture.id,8);
    f.view.emit('pointerup',{pointerId:8});
    assert.equal(s.powerCasts.snapshot().active,2);assert.equal(s.powerCasts.snapshot().held,false);
  }
});

test('blur or switching tools cancels unfinished charges and prevents a later pointer release',()=>{
  for(const action of ['blur','pan','fuel','fire']){
    const f=fixture(powerDefinition('solar-lance')),s=f.solver;
    s.castPower([-.5,1.1,0],[1,0,0],1);
    f.view.emit('pointerdown');s.powerCasts.step(.35);
    if(action==='blur')f.window.emit('blur');else f.tool(action);
    const cancelled=structuredClone(s.powerCasts.snapshot());
    assert.equal(cancelled.active,1);assert.equal(cancelled.held,false);assert.equal(f.state().gesture,null);
    f.view.emit('pointerup');assert.deepEqual(s.powerCasts.snapshot(),cancelled,action+' cannot launch on late pointerup');
  }
});
