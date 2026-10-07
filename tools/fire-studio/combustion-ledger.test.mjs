import test from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const root=resolve(process.env.FIRE_STUDIO_ROOT||resolve(import.meta.dirname,'../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live'));
const {simulationShaders}=await import(pathToFileURL(resolve(root,'pyro-gpu/shaders.js')).href);
const smoothstep=(a,b,x)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t);};
const sceneReactionRate=c=>Math.min(Math.max(c.z,0),Math.max(1-c.w,0)/.7)*5.8*smoothstep(.35,.75,c.y);

function productionLedger(){
 const code=simulationShaders(128,256).correctScalar;
 const match=/fn sceneReactionLedger\(c:vec4f,dt:f32,heatRelease:f32,sootYield:f32\)->vec4f\{/.exec(code);
 assert.ok(match,'the live scalar shader must contain the reaction ledger');
 const start=match.index+match[0].length;let end=start,depth=1;
 while(depth){if(code[end]==='{')depth++;if(code[end]==='}')depth--;end++;}
 const body=code.slice(start,end-1).replace(/\b(max|min|exp|abs)\(/g,'Math.$1(').replace(/vec4f\(/g,'Array.of(');
 const run=new Function('c','dt','heatRelease','sootYield','sceneReactionRate','object','select','richSootYield',body);return (...args)=>run(...args,{tint:{w:0}},(a,b,test)=>test?b:a,(fuel,oxygen)=>.35+.65*smoothstep(.3,1.2,.7*Math.max(fuel,0)/Math.max(oxygen,.02)));
}

test('reaction ledger cannot consume more fuel or oxygen than the cell contains',()=>{
 const ledger=productionLedger();
 for(const state of [[.2,.9,.8,0],[.1,.65,1.2,.92],[1,.74,.03,.1]]){
  const unburntFuel=state[2],oxygenDeficit=state[3];
  const cell={x:state[0],y:state[1],z:state[2],w:state[3]};
  const [burned,oxygen,heat,soot]=ledger(cell,.1,3.2,1.1,sceneReactionRate);
  assert.ok(burned>=0&&burned<=unburntFuel+1e-12,JSON.stringify({state,burned,unburntFuel}));
  assert.ok(oxygen>=0&&oxygen<=1-oxygenDeficit+1e-12);
  assert.ok(Math.abs(oxygen-.7*burned)<1e-12);
  assert.ok(heat>=0&&soot>=0);
 }
 const exhausted=ledger({x:0,y:.9,z:2,w:1},.5,3.2,1.1,sceneReactionRate);
 assert.equal(exhausted[0],0);
 assert.equal(ledger({x:0,y:.9,z:2,w:0},0,3.2,1.1,sceneReactionRate)[0],0);
});
