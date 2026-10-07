import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const runtime=new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/',import.meta.url);
const {ALL_FIRE_PRESETS}=await import(new URL('pyro-gpu/presets.js',runtime));
const {createFireDomain}=await import(new URL('fire-domain.js',runtime));
const source=await readFile(new URL('original-fine-flow.js',runtime),'utf8'),context={window:{}};vm.runInNewContext(source,context);const Flow=context.window.OriginalFineFlow;
// Shader generation only. This mock never allocates a pixel array, draws or compiles.
function capture(domain){
 const gl=Object.fromEntries('R32F RG32F RGBA32F RGBA16F RED RG RGBA FLOAT HALF_FLOAT TEXTURE_2D TEXTURE_MIN_FILTER TEXTURE_MAG_FILTER TEXTURE_WRAP_S TEXTURE_WRAP_T LINEAR NEAREST CLAMP_TO_EDGE FRAMEBUFFER COLOR_ATTACHMENT0 COLOR_ATTACHMENT1 FRAMEBUFFER_COMPLETE COLOR VERTEX_SHADER FRAGMENT_SHADER COMPILE_STATUS LINK_STATUS'.split(' ').map((name,i)=>[name,i+1]));
 for(const name of ['bindTexture','texParameteri','texImage2D','bindFramebuffer','framebufferTexture2D','drawBuffers','clearBufferfv','compileShader','linkProgram'])gl[name]=()=>{};
 for(const name of ['createTexture','createFramebuffer','createVertexArray'])gl[name]=()=>({});
 gl.checkFramebufferStatus=()=>gl.FRAMEBUFFER_COMPLETE;gl.createProgram=()=>({shaders:[]});gl.createShader=type=>({type});gl.shaderSource=(shader,text)=>{shader.source=text;};gl.attachShader=(program,shader)=>program.shaders.push(shader);gl.getShaderParameter=gl.getProgramParameter=()=>true;
 const flow=Flow.setup(gl,{nx:domain.nx,ny:domain.ny,depth:domain.depth,extent:domain.extent,minimum:domain.minimum,pressureGLSL:'uniform sampler2D pressureCorrectionTex;vec3 samplePressureCorrection(vec3 p){return vec3(0);}'});
 const upper=flow.upperApplyProgram.shaders.find(s=>s.type===gl.FRAGMENT_SHADER).source;flow.enableMaterialLedger(true);return {flow,upper,shaders:flow.shaders.map(s=>s.source)};
}
const domains=new Map(),presets=[...new Set(ALL_FIRE_PRESETS.map(p=>p.id.replace(/^legacy:/,''))), 'campfire','sigil','sigil-cybr','violet-sigil','free'];
for(const grid of ['', '896'])for(const preset of presets){globalThis.location={href:'https://fixture.invalid/?grid='+grid};const d=createFireDomain(preset),key=JSON.stringify([d.nx,d.ny,d.depth,d.extent,d.minimum]);if(!domains.has(key))domains.set(key,{domain:d,presets:[]});domains.get(key).presets.push({preset,grid});}
delete globalThis.location;
const captured=[...domains.values()].map(x=>({...x,...capture(x.domain)}));
test('Fireball fragment changes only its two invalid integer multiplication literals',async()=>{
 const previous=await readFile(new URL('./fixtures/fireball-v7-upper-apply.glsl',import.meta.url),'utf8'),actual=captured.find(x=>x.domain.blast).upper;
 assert.match(previous,/v\.x\+=6\*/);assert.match(previous,/v\.y\+=6\*/);
 assert.equal(actual,previous.replace('v.x+=6*','v.x+=6.0*').replace('v.y+=6*','v.y+=6.0*'));
});
test('every authored preset and supported grid generates finite, balanced shader forms',t=>{
 assert.equal(captured.length,5);assert(presets.includes('fireball'));assert(presets.length>50);
 let shaders=0;for(const row of captured)for(const source of row.shaders){shaders++;assert(source.startsWith('#version 300 es\n'));assert.equal([...source.matchAll(/\bvoid\s+main\s*\(/g)].length,1);assert.doesNotMatch(source,/\$\{|\b(?:NaN|Infinity|undefined)\b/);const text=source.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,''),stack=[],pairs={')':'(',']':'[','}':'{'};for(const c of text){if('([{'.includes(c))stack.push(c);else if(')]}'.includes(c))assert.equal(stack.pop(),pairs[c]);}assert.equal(stack.length,0);}
 t.diagnostic(JSON.stringify({presets:presets.length,gridSelections:2,domainForms:captured.length,generatedShaderStages:shaders,scope:'CPU source structure and finite constants; native compilation is a separate gate'}));
});
test('every upper correction coefficient has float syntax and retains its exact numeric value',()=>{
 const floatToken='(?:[0-9]+\\.[0-9]*|\\.[0-9]+|[0-9]+[eE][+-]?[0-9]+)(?:[eE][+-]?[0-9]+)?';
 for(const {domain,upper}of captured)for(const [axis,n,extent]of [['x',domain.nx,domain.extent[0]],['y',domain.ny,domain.extent[1]]]){const token=upper.match(new RegExp('v\\.'+axis+'\\+=('+floatToken+')\\*'))?.[1];assert(token,'Missing typed coefficient for '+axis);assert.equal(Number(token),n/(extent**2));assert.equal(Math.fround(Number(token)),Math.fround(n/(extent**2)));if(!Number.isInteger(n/(extent**2)))assert.equal(token,String(n/(extent**2)),'Already valid nonintegral shader text changes');}
});
