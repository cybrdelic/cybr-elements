import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
const root=process.env.FIRE_STUDIO_ROOT?path.resolve(process.env.FIRE_STUDIO_ROOT):fileURLToPath(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url));
const {adaptiveFlowShaders,initialAdaptiveFlowCommands,ADAPTIVE_FLOW_OFFSETS:offsets,ADAPTIVE_FLOW_COMMAND_BYTES}=await import(pathToFileURL(path.join(root,'pyro-gpu/adaptive-flow.js')).href);
const {simulationShaders}=await import(pathToFileURL(path.join(root,'pyro-gpu/shaders.js')).href);

test('fine flow mask work is compiled only for the opted-in solver',()=>{
 assert.doesNotMatch(simulationShaders().correctScalar,/atomicOr\(&opticalAlive,4u\)/);
 assert.match(simulationShaders(128,256,{flowSupport:true}).correctScalar,/atomicOr\(&opticalAlive,4u\)/);
});

// Execute the production finish command writes. Only the scalar WGSL dialect
// is translated here; there is no second implementation of its decisions.
function finishFixture(N=128,D=256){
 const source=adaptiveFlowShaders(N,D).build;
 const start=source.indexOf('fn finish(){');
 assert.notEqual(start,-1,'production finish entry point');
 let body=source.slice(start+'fn finish(){'.length).trim();
 assert.equal(body.at(-1),'}');body=body.slice(0,-1);
 body=body.replace(/\/\/[^\n]*/g,'')
  .replaceAll('atomicLoad(&count)','count')
  .replaceAll('any(tiles[k].xyz==vec3u(u32(B-1)))','tiles[k].xyz.some(value=>value===B-1)')
  .replace(/\b(\d+)u\b/g,'$1')
  .replace(/\blet\b/g,'const').replace(/\bvar\b/g,'let');
 assert.doesNotMatch(body,/atomicLoad|vec3u|u32|\bfn\b/,'fixture covers current WGSL dialect');
 const execute=new Function('count','tiles','commands','select','B','T',body);
 return (commands,tiles)=>execute(tiles.length,tiles.map(xyz=>({xyz})),commands,(a,b,c)=>c?b:a,N/8,(N/8)**3);
}
function dispatch(commands,offset){return Array.from(commands.slice(offset/4,offset/4+3));}
const classifiers=['sourceWork','restrict','chemistry','mark','build','finish'];
const dense=['densePredict','denseCurl','denseCorrect'];

test('factor-two flow includes area average, tangential extrapolation and guarded dense fallback',()=>{
 const s=adaptiveFlowShaders();
 assert.match(s.restrict,/\.25\*\(readFace\(b,k\)/);
 assert.match(s.restrict,/faceIndex\(i,k,C\)/);
 assert.match(s.fill,/if\(i.y==0\)\{v.y=0/);
 assert.match(s.build,/n\*2u<T&&!boundary/);
 assert.match(s.build,/tiles\[k\]\.xyz==vec3u\(u32\(B-1\)\)/);
 assert.match(s.mark,/\.001/);
 assert.match(s.mark,/chemistryWork\[id.x\]\.xyz\/2u/);
});
test('queued fine kernels use a full eight-cell tile and keep original fine transport code',()=>{
 const s=adaptiveFlowShaders();
 for(const key of ['fineAdvect','fineCurl','fineCorrect']){
  assert.match(s[key],/binding\(14\)/);
  assert.match(s[key],/let i=work\[group.x\]\.xyz\*8u/);
  assert.doesNotMatch(s[key],/global_invocation_id/);
 }
 assert.match(s.fineCorrect,/Brinkman/);
 assert.match(s.fineCorrect,/flameActivity\(c\)/);
 assert.match(s.fineAdvect,/Near-integer|tolerance=8\./);
 assert.match(s.coarseAdvect,/@workgroup_size\(4,4,4\)/);
 assert.match(s.fillCell,/textureSampleLevel/);
});
test('invalid hierarchy is rejected before any allocation',()=>{
 assert.throws(()=>adaptiveFlowShaders(127),/hierarchy/);
 assert.throws(()=>adaptiveFlowShaders(128,128),/hierarchy/);
 assert.throws(()=>adaptiveFlowShaders(128,256,16),/hierarchy/);
 assert.throws(()=>initialAdaptiveFlowCommands(128,128),/hierarchy/);
 assert.throws(()=>initialAdaptiveFlowCommands(Infinity,Infinity),/hierarchy/);
});
test('initial command upload enables classifiers and safe original dense flow',()=>{
 const commands=initialAdaptiveFlowCommands();
 assert.equal(commands.byteLength,ADAPTIVE_FLOW_COMMAND_BYTES);
 assert.equal(ADAPTIVE_FLOW_COMMAND_BYTES,168);
 assert.deepEqual(dispatch(commands,offsets.sourceWork),[8,8,8]);
 assert.deepEqual(dispatch(commands,offsets.restrict),[17,17,17]);
 assert.deepEqual(dispatch(commands,offsets.chemistry),[512,1,1]);
 assert.deepEqual(dispatch(commands,offsets.mark),[16,16,16]);
 assert.deepEqual(dispatch(commands,offsets.build),[4,4,4]);
 assert.deepEqual(dispatch(commands,offsets.finish),[1,1,1]);
 assert.deepEqual(dispatch(commands,offsets.densePredict),[17,33,33]);
 assert.deepEqual(dispatch(commands,offsets.denseCurl),[32,32,32]);
 assert.deepEqual(dispatch(commands,offsets.denseCorrect),[33,33,33]);
 assert.deepEqual(Array.from(commands.slice(21,24)),[0,0,0]);
});
test('production finish keeps classification enabled while sparse coverage is safe',()=>{
 const commands=initialAdaptiveFlowCommands(),before=commands.slice();
 finishFixture()(commands,[[4,4,4],[5,4,4],[6,4,4]]);
 assert.equal(commands[offsets.stickyDense/4],0);
 assert.equal(commands[offsets.sparse/4],1);
 assert.equal(commands[offsets.fineCount/4],3);
 assert.deepEqual(dispatch(commands,offsets.coarse),[17,17,17]);
 assert.deepEqual(dispatch(commands,offsets.fill),[33,33,33]);
 assert.deepEqual(dispatch(commands,offsets.finePredict),[3,2,2]);
 assert.deepEqual(dispatch(commands,offsets.fineCurlCorrect),[3,2,4]);
 for(const key of dense)assert.equal(commands[offsets[key]/4],0);
 for(const key of classifiers)assert.deepEqual(dispatch(commands,offsets[key]),dispatch(before,offsets[key]));
});
test('production finish latches dense coverage and suppresses every classifier thereafter',()=>{
 const finish=finishFixture(),commands=initialAdaptiveFlowCommands(),before=commands.slice();
 finish(commands,Array.from({length:2048},()=>[4,4,4]));
 assert.equal(commands[offsets.stickyDense/4],1);
 assert.equal(commands[offsets.sparse/4],0);
 assert.equal(commands[offsets.fineCount/4],2048);
 for(const key of dense)assert.deepEqual(dispatch(commands,offsets[key]),dispatch(before,offsets[key]));
 for(const key of ['coarse','fill','finePredict','fineCurlCorrect',...classifiers])assert.equal(commands[offsets[key]/4],0,key);
 const sticky=commands.slice();
 finish(commands,[[4,4,4]]);
 assert.deepEqual(commands,sticky,'even a direct finish call cannot unlock sticky mode');
});
test('outer packed-face ownership still forces sticky dense mode at low coverage',()=>{
 const finish=finishFixture();
 for(let axis=0;axis<3;axis++){
  const commands=initialAdaptiveFlowCommands(),xyz=[4,4,4];xyz[axis]=15;
  finish(commands,[xyz]);
  assert.equal(commands[offsets.stickyDense/4],1,`outer axis ${axis}`);
  assert.equal(commands[offsets.sparse/4],0);
  for(const key of dense)assert.ok(commands[offsets[key]/4]>0);
  for(const key of classifiers)assert.equal(commands[offsets[key]/4],0);
 }
});
test('only a clean command reset restores sparse classification eligibility',()=>{
 const finish=finishFixture(),commands=initialAdaptiveFlowCommands();
 finish(commands,[[15,4,4]]);
 commands.set(initialAdaptiveFlowCommands());
 assert.equal(commands[offsets.stickyDense/4],0);
 for(const key of classifiers)assert.ok(commands[offsets[key]/4]>0);
 finish(commands,[[4,4,4]]);
 assert.equal(commands[offsets.sparse/4],1);
 assert.equal(commands[offsets.stickyDense/4],0);
});
