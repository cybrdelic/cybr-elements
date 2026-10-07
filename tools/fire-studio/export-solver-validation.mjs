import fs from 'node:fs';
import {simulationShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/shaders.js';
import {planBrickPool,brickPoolScalarShaders,brickPoolVelocityShader} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/brick-pool.js';
import {POWER_DEFINITIONS} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/fire-powers.js';
import {geometryProjectionShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/pressure-geometry.js';
import {pruneShaderFunctions} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/shader-specialization.js';
import {powerContactShader} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/power-contacts.js';
import {adaptiveFlowShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/adaptive-flow.js';
import {rendererShaders} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/renderer.js';
import {pooledChemistryConsumer} from '../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/pyro-gpu/pooled-coupling.js';
const rows=[],plan=planBrickPool({D:256,capacity:4096,brick:16,sharedStorage:true});
for(const definition of POWER_DEFINITIONS)rows.push({name:'contacts/'+definition.id,code:powerContactShader(definition.kind)});
for(const kind of [null,...POWER_DEFINITIONS.map(d=>d.kind)]){
 const shaders=simulationShaders(128,256,{hasPowers:kind!==null,powerKind:kind});
 const pooled=brickPoolScalarShaders(plan,{N:128,shaders});
 pooled.correctVelocity=brickPoolVelocityShader(plan,{N:128,source:shaders.correctVelocity});
 for(const [mode,family] of [['volume',shaders],['sparse',pooled]])for(const [name,code] of Object.entries(family)){
  rows.push({name:`${mode}/${kind??'ordinary'}/${name}`,code:pruneShaderFunctions(code)});
 }
}
for(const pressureCache of [false,true])for(const kind of [null,...POWER_DEFINITIONS.map(d=>d.kind)]){
 const shaders=simulationShaders(128,256,{hasPowers:kind!==null,powerKind:kind,subgroups:true,pressureCache});
 const pooled=brickPoolScalarShaders(plan,{N:128,shaders});
 for(const [mode,code] of [['volume',shaders.correctScalar],['sparse',pooled.correctScalar]])rows.push({name:`${mode}/subgroups-cache-${pressureCache}/${kind??'ordinary'}/correctScalar`,code:pruneShaderFunctions(code)});
}
for(const subgroups of [false,true])rows.push({name:'fine-flow-mask/'+subgroups,code:simulationShaders(128,256,{hasPowers:false,flowSupport:true,subgroups}).correctScalar});
for(const kind of [null,...POWER_DEFINITIONS.map(d=>d.kind)]){
 const shaders=simulationShaders(128,256,{hasPowers:kind!==null,powerKind:kind,pressureCache:true});
 const pooled=brickPoolScalarShaders(plan,{N:128,shaders});
 pooled.correctVelocity=brickPoolVelocityShader(plan,{N:128,source:shaders.correctVelocity});
 for(const [mode,family] of [['volume',shaders],['sparse',pooled]])for(const name of ['correctScalar','correctVelocity'])rows.push({name:`${mode}/cached-pressure/${kind??'ordinary'}/${name}`,code:pruneShaderFunctions(family[name])});
 const adaptive=adaptiveFlowShaders(128,256,8,{hasPowers:kind!==null,powerKind:kind,pressureCache:true});
 for(const name of ['sourceWork','coarseCorrect','fineCorrect'])rows.push({name:`adaptive/${kind??'ordinary'}/${name}`,code:pruneShaderFunctions(adaptive[name])});
}
const geometry=geometryProjectionShaders(simulationShaders(8,16,{hasPowers:false}),8);
for(const [name,code] of Object.entries(geometry))rows.push({name:'geometry/'+name,code:pruneShaderFunctions(code)});
// Validate the actual assembled draw and lighting modules, including conditional wood hits.
for(const tree of [false,true])for(const sparse of [false,true])for(const phase of [false,true]){
 const family=rendererShaders(tree,false,false,phase,256);
 for(const [name,entry,stage] of [['render','fragment','render'],['light','main','compute'],['lightWork','main','compute'],['lightReceivers','main','compute'],['room','main','compute'],['room','bounce','compute'],['gather','main','compute'],['gatherAdaptive','main','compute']]){
  const code=sparse?pooledChemistryConsumer(family[name],plan,{atlasBinding:25,pagesBinding:28,metadataBinding:29}):family[name];
  rows.push({name:`lighting/tree-${tree}/sparse-${sparse}/phase-${phase}/${name}/${entry}`,code,entry,stage});
 }
}
fs.writeFileSync('output/fire-principal-pass/solver-validation-fixture.json',JSON.stringify(rows));
console.log(JSON.stringify({fixture:'output/fire-principal-pass/solver-validation-fixture.json',pipelines:rows.length}));
