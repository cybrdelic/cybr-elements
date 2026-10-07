import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';

const sourceRoot=fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const root=resolve(process.env.FIRE_STUDIO_ROOT||sourceRoot);
const {fuelHalf}=await import(pathToFileURL(resolve(root,'fuel-ground.js')).href);
const {SMOKE_CLEAR_DENSITY}=await import(pathToFileURL(resolve(root,'smoke-lifecycle.js')).href);
const decode=half=>{const e=half>>>10,m=half&1023;return e===0?m*2**-24:(1+m/1024)*2**(e-15);};
const damping=Math.fround(Math.exp(-.055/30));
const stored=value=>decode(fuelHalf(value));
const oldStep=value=>stored(Math.fround(Math.fround(value)*damping));
const newStep=value=>{const damped=Math.fround(Math.fround(value)*damping);return damped<SMOKE_CLEAR_DENSITY?0:stored(damped);};

test('binary16 cold-soot damping plateau reproduces and eventually clears',()=>{
  for(const initial of [1,.1,.001,.0001,.00001]){
    let legacy=stored(initial),fixed=legacy;
    for(let i=0;i<10000;i++){legacy=oldStep(legacy);fixed=newStep(fixed);}
    assert.ok(legacy>0&&legacy<SMOKE_CLEAR_DENSITY,'Legacy storage retains an invisible nonzero residue');
    assert.equal(oldStep(legacy),legacy,'Binary16 rounding prevents further decay');
    assert.equal(fixed,0,'Cleanup allows all cold soot to leave the field');
  }
});
test('visible smoke retains the existing decay trajectory until the invisible cutoff',()=>{
  let legacy=stored(.1),fixed=legacy,unchanged=0;
  while(legacy>=SMOKE_CLEAR_DENSITY){
    const next=oldStep(legacy),candidate=newStep(fixed);
    if(candidate===0){assert.ok(next<=SMOKE_CLEAR_DENSITY);break;}
    assert.equal(candidate,next);legacy=next;fixed=candidate;unchanged++;assert.ok(unchanged<10000);
  }
  assert.ok(unchanged>3000,'Fresh smoke is not shortened by the storage cleanup');
});
test('production cleanup is after absorbing boundaries and before chemistry storage',()=>{
  const source=(readFileSync(resolve(root,'fire.js'),'utf8')+'\n'+readFileSync(resolve(root,'original-shaders.js'),'utf8'));
  assert.match(source,/import\s*\{SMOKE_CLEAR_DENSITY\}\s*from\s*['"]\.\/smoke-lifecycle\.js\?v=[a-z0-9-]+['"]/);
  assert.match(source,/soot=clamp\(\(soot-oxidized\)\*exp\(-smokeLossRate\(temp\)\*smokeDecayDt\)/);
  const boundary=source.indexOf('fuel*=edge; temp*=edge; soot*=edge;'),cleanup=source.indexOf('if(soot<${SMOKE_CLEAR_DENSITY})soot=0.;'),store=source.indexOf('outChem=vec4(fuel,oxygen,temp,soot);');
  assert.ok(boundary>=0&&cleanup>boundary&&store>cleanup);
});
