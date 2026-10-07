import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source=await readFile(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/original-fine-flow.js',import.meta.url),'utf8'),context={window:{},performance};vm.runInNewContext(source,context);const Flow=context.window.OriginalFineFlow;
function fakeGL(reads=[]){
 const names='R32F RG32F RGBA32F RGBA16F RED RG RGBA FLOAT HALF_FLOAT TEXTURE_2D TEXTURE_MIN_FILTER TEXTURE_MAG_FILTER TEXTURE_WRAP_S TEXTURE_WRAP_T LINEAR NEAREST CLAMP_TO_EDGE FRAMEBUFFER READ_FRAMEBUFFER COLOR_ATTACHMENT0 COLOR_ATTACHMENT1 FRAMEBUFFER_COMPLETE COLOR VERTEX_SHADER FRAGMENT_SHADER COMPILE_STATUS LINK_STATUS TRIANGLES'.split(' '),gl=Object.fromEntries(names.map((s,i)=>[s,i+1]));gl.TEXTURE0=1000;
 const textures=[],draws=[],locationCalls=new Map();let texture,fbo,program,active=0,readCount=0;const bound=new Map();
 gl.createTexture=()=>{const t={id:textures.length+1};textures.push(t);return t;};gl.createFramebuffer=()=>({attachments:new Map()});gl.createVertexArray=()=>({});gl.bindVertexArray=()=>{};
 gl.bindTexture=(target,t)=>{texture=t;bound.set(active,t);};gl.activeTexture=unit=>{active=unit-1000;};gl.texParameteri=()=>{};gl.texImage2D=(target,level,internal,width,height,border,format,type)=>Object.assign(texture,{internal,width,height,format,type});
 gl.bindFramebuffer=(target,t)=>{fbo=t;};gl.framebufferTexture2D=(target,attachment,texTarget,t)=>fbo.attachments.set(attachment,t);gl.drawBuffers=attachments=>{fbo.buffers=Array.from(attachments);};gl.checkFramebufferStatus=()=>gl.FRAMEBUFFER_COMPLETE;gl.clearBufferfv=()=>{};
 gl.createProgram=()=>({shaders:[],uniforms:new Map()});gl.createShader=type=>({type});gl.shaderSource=(s,text)=>{s.source=text;};gl.compileShader=()=>{};gl.getShaderParameter=()=>true;gl.attachShader=(p,s)=>p.shaders.push(s);gl.linkProgram=()=>{};gl.getProgramParameter=()=>true;
 gl.useProgram=p=>{program=p;};gl.getUniformLocation=(p,name)=>{const key=p.shaders.find(s=>s.type===gl.FRAGMENT_SHADER).source;const declarations=Array.from(key.matchAll(/uniform\s+\w+\s+([^;]+);/g),m=>m[1].split(',').map(s=>s.trim())).flat();if(!declarations.includes(name))return null;const names=locationCalls.get(p)||new Map();names.set(name,(names.get(name)||0)+1);locationCalls.set(p,names);return {program:p,name};};gl.uniform1i=(location,unit)=>location.program.uniforms.set(location.name,{unit});gl.uniform1f=(location,value)=>{if(location)location.program.uniforms.set(location.name,{value});};gl.viewport=()=>{};
 gl.drawArrays=()=>{const writable=Array.from(fbo.attachments.values()),inputs=Array.from(program.uniforms.values()).filter(x=>Object.hasOwn(x,'unit')).map(x=>bound.get(x.unit));assert(inputs.every(t=>!writable.includes(t)),'A sampled texture aliases the bound draw framebuffer');draws.push({program,uniforms:new Map(program.uniforms),attachments:Array.from(fbo.attachments.values()),buffers:Array.from(fbo.buffers)});};
 gl.getParameter=()=>fbo;gl.readBuffer=()=>{};gl.readPixels=(x,y,width,height,format,type,values)=>{readCount++;values.set(reads.shift()||[0,0,0,0]);};for(const name of ['deleteFramebuffer','deleteTexture','deleteProgram','deleteShader','deleteVertexArray'])gl[name]=()=>{};
 return {gl,textures,draws,locationCalls,get readCount(){return readCount;}};
}
const make=(gl,n=[640,360,32])=>Flow.setup(gl,{nx:n[0],ny:n[1],depth:n[2],extent:[14,7.875,1.8],minimum:[-7,-1.05,-.9],pressureGLSL:'uniform sampler2D pressureCorrectionTex;vec3 samplePressureCorrection(vec3 p){return vec3(0);}'});
test('two transport states reuse pressure planes with separate FBOs and reduce default requested storage to 266.93 MiB',()=>{
 const env=fakeGL(),flow=make(env.gl),l=flow.levels[0];assert.equal(flow.states.length,2);assert.equal(flow.states[0].fuelHeat,l.p[0].texture);assert.equal(flow.states[1].fuelHeat,l.p[1].texture);assert.equal(flow.states[0].soot,l.rhs.texture);assert.equal(flow.states[1].soot,l.residual.texture);assert.notEqual(flow.states[0].fbo,l.p[0].fbo);
 assert.equal(l.p[0].texture.format,env.gl.RG);assert.equal(l.p[0].texture.internal,env.gl.RG32F);assert(l.p[0].fbo.attachments.size===1);
 const bytes=env.textures.reduce((sum,t)=>sum+t.width*t.height*(t.internal===env.gl.RGBA16F||t.internal===env.gl.RG32F?8:t.internal===env.gl.R32F?4:16),0);assert.equal(bytes,279893336);assert(!Object.hasOwn(flow,'packed'));assert(!Object.hasOwn(flow,'q'));
});
test('a failed midpoint forces another compatible cycle even when the center passes',()=>{
 const env=fakeGL([[100,5,100,0],[100,11,100,0],[0,4,0,0],[0,9,0,0],[1,2,3,0]]),flow=make(env.gl,[24,16,8]);flow.lastProjection={cycles:1};flow.project({},{},{},1/30);assert.equal(flow.lastProjection.cycles,2);assert.equal(flow.lastProjection.converged,true);assert.equal(flow.lastProjection.midpointEta,.09);assert.equal(flow.lastProjection.storageLive,true);
 const pressure=flow.lastProjection.pressure,rhs=flow.lastProjection.rhs,result=flow.transport(flow.projected.texture,{},1/30);assert.equal(flow.lastProjection.storageLive,false);assert.equal(flow.lastProjection.pressure,null);assert.equal(flow.lastProjection.rhs,null);assert([flow.states[0].fuelHeat,flow.states[1].fuelHeat].includes(pressure));assert.equal(rhs,flow.states[0].soot);assert(result.fuelHeat&&result.soot);
 assert.throws(()=>flow.transport(flow.projected.texture,{},1/30),/new converged projection storage/);
 for(const map of env.locationCalls.values())for(const count of map.values())assert.equal(count,1,'Uniform lookup is cached across cycles/sweeps');
});
test('bounded correction explicitly rejects unresolved midpoint residual without hiding it',()=>{
 const reads=[];for(let i=0;i<4;i++)reads.push([100,4,100,0],[100,12,100,0]);const env=fakeGL(reads),flow=make(env.gl,[24,16,8]),vf={},chem={},coarse={};flow.lastProjection={cycles:1};assert.throws(()=>flow.project(vf,chem,coarse,1/30),/Fine projection rejected/);assert.equal(flow.lastProjection.cycles,4);assert.equal(flow.lastProjection.converged,false);assert.equal(flow.lastProjection.storageLive,false);assert.equal(flow.lastProjection.eta,.04);assert.equal(flow.lastProjection.midpointEta,.12);assert.equal(flow.lastProjection.sourceVF,vf);assert.equal(flow.lastProjection.sourceChem,chem);assert.equal(flow.lastProjection.coarseCorrection,coarse);assert(flow.lastProjection.rhs&&flow.lastProjection.pressure);const before=env.draws.length;assert.throws(()=>flow.transport(flow.projected.texture,chem,1/30),/converged/);assert.equal(env.draws.length,before);
});
test('transport schedule rejects excessive work before consuming accepted storage',()=>{
 const env=fakeGL(),flow=make(env.gl,[24,16,8]);flow.project({},{},{},1/30);flow.lastProjection.axisRates=[51168,43080,83789.9921875];const before=env.draws.length;
 assert.throws(()=>flow.prepareTransport(.015),/unsupported work: 1397/);assert.equal(env.draws.length,before);assert.equal(flow.lastProjection.storageLive,true);assert(flow.lastProjection.rhs&&flow.lastProjection.pressure);
});
test('nonfinite projection remains diagnosed and cannot enter transport',()=>{
 const env=fakeGL([[100,NaN,100,0],[100,NaN,100,0],[100,NaN,100,0],[100,NaN,100,0],[100,NaN,100,0],[1,2,3,0]]),flow=make(env.gl,[24,16,8]);
 assert.throws(()=>flow.project({},{},{},1/30),/Nonfinite/);assert.equal(flow.lastProjection.finite,false);assert.equal(flow.lastProjection.converged,false);assert.equal(flow.lastProjection.storageLive,false);assert(flow.lastProjection.rhs&&flow.lastProjection.pressure);
});
test('merged packing writes conservative fuel/heat/soot and retains the existing oxygen backtrace',async()=>{
 const advection=await readFile(new URL('../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/corrected-advection.js',import.meta.url),'utf8'),ctx={window:{}};vm.runInNewContext(advection,ctx);const prototype=ctx.window.MacCormackAdvection.prototype,mock={conservativeTransport:true,faceReconstructionGLSL:Flow.faceReconstructionGLSL({n:[12,9,7],floor:1}),nx:12,nz:9,depth:7,tilesX:8,makeCommonGLSL:()=>''},fragment=prototype.makePredictorFragment.call(mock,'');
 assert.match(fragment,/q.r,mcField\(chemTex,back\).g,q.g\/\(1\.\+q.r\),soot/);assert.match(fragment,/vec3 back=at-midVelocity\*delta/);assert.doesNotMatch(fragment,/clamp\(q|max\(q/);
});
test('actual Sigil residual history admits one predicted extra correction without changing either target',()=>{
 const center=[1004958,392393.75,180800.765625,109109.2265625].map(x=>Flow.projectionScore([2987395.75,x,2987395.75,0])),mid=[null,null,372348.3125/298039.225,298584.625/298039.225];
 const history=center.map((centerScore,i)=>({cycles:i+1,centerScore,midpointScore:mid[i],wallMs:21.1})),decision=Flow.correctionDecision(history);
 assert.equal(decision.action,'correct');assert.equal(decision.predictedCycles,1);assert(decision.contraction<.81);assert.equal(Flow.projectionScore([100,10.0183,100,0])>1,true);
});
test('extra correction refuses stagnant, divergent, distant, nonfinite and over-budget residuals',()=>{
 const history=(previous,current,wallMs=20,cycles=4)=>[{cycles:cycles-1,centerScore:.4,midpointScore:previous,wallMs},{cycles,centerScore:.3,midpointScore:current,wallMs}];
 for(const h of [history(1.2,1.2),history(1.1,1.2),history(2,1.61),history(1.5,1.4),history(1.25,1.001,49),history(1.4,1.2,20,6),history(1.4,NaN)])assert.equal(Flow.correctionDecision(h).action,'reject',JSON.stringify(h));
 assert.equal(Flow.correctionDecision(history(1.25,1.001,20),30).action,'reject');
});
test('fifth actual mocked correction is accepted only after both unchanged metrics pass, reusing fixed pre sums',()=>{
 const reads=[[100,35,100,0],[0,14,0,0],[0,6,0,0],[100,12.5,100,0],[0,3.6,0,0],[0,10.0183,0,0],[0,2.5,0,0],[0,9.3,0,0],[3,4,5,0]],env=fakeGL(reads),flow=make(env.gl,[24,16,8]);flow.lastProjection={cycles:1};flow.project({},{},{},1/30);
 assert.equal(flow.lastProjection.cycles,5);assert.equal(flow.lastProjection.extraCycles,1);assert.equal(flow.lastProjection.converged,true);assert.equal(flow.lastProjection.preL1,100);assert.equal(flow.lastProjection.midpointPreL1,100);assert.equal(flow.lastProjection.midpointQ,100);assert.equal(flow.lastProjection.rhoTolerance,.2);assert.equal(flow.lastProjection.etaTolerance,.1);
 const midpoint=env.draws.filter(d=>d.program===flow.midpointProgram);assert.deepEqual(midpoint.map(d=>d.uniforms.get('uReusePre').value),[0,1,1]);assert.equal(reads.length,0);
});
test('pressure survives transport aliases and is only an initial guess, allowing measured zero-cycle acceptance',()=>{
 const reads=[[100,5,100,0],[100,8,100,0],[1,2,3,0]],env=fakeGL(reads),flow=make(env.gl,[24,16,8]);flow.lastProjection={cycles:1};flow.project({},{},{},1/30);assert.equal(flow.warmValid,true);assert.equal(flow.warmPressure.texture.internal,env.gl.R32F);assert(!flow.states.some(s=>s.fuelHeat===flow.warmPressure.texture||s.soot===flow.warmPressure.texture));
 flow.transport(flow.projected.texture,{},1/30);reads.push([100,4,100,0],[100,8,100,0],[1,2,3,0]);const before=env.draws.length;flow.project({},{},{},1/30);assert.equal(flow.lastProjection.warmStart,true);assert.equal(flow.lastProjection.cycles,0);assert.equal(flow.lastProjection.converged,true);assert.equal(flow.lastProjection.warmPressureBytes,12288);assert(!env.draws.slice(before).some(d=>flow.levels.some(l=>d.program===l.smooth)));
 flow.discardCandidateHistory();assert.equal(flow.warmValid,false);flow.resetProjectionHistory();assert.equal(flow.lastProjection,null);
});
test('unaccepted warm-start metrics still require correction and a nonfinite guess cannot leak into transport',()=>{
 const reads=[[100,5,100,0],[100,8,100,0],[1,2,3,0]],env=fakeGL(reads),flow=make(env.gl,[24,16,8]);flow.lastProjection={cycles:1};flow.project({},{},{},1/30);reads.push([100,NaN,100,0],[100,NaN,100,0],[100,NaN,100,0]);assert.throws(()=>flow.project({},{},{},1/30),/Nonfinite/);assert.equal(flow.warmValid,false);assert.throws(()=>flow.prepareTransport(1/30),/converged/);
});
test('a warm pressure guess that worsens current divergence is discarded before the measured cold exit',()=>{
 const reads=[[100,5,100,0],[100,8,100,0],[1,2,3,0]],env=fakeGL(reads),flow=make(env.gl,[24,16,8]);flow.lastProjection={cycles:1};flow.project({},{},{},1/30);reads.push([100,200,100,0],[0,4,0,0],[100,8,100,0],[1,2,3,0]);flow.project({},{},{},1/30);assert.equal(flow.lastProjection.warmStart,true);assert.equal(flow.lastProjection.warmFallback,true);assert.equal(flow.lastProjection.cycles,0);assert.equal(flow.lastProjection.converged,true);assert.equal(flow.lastProjection.preL1,100);assert.equal(reads.length,0);
});
test('optional material ledger has bounded small storage, no per-step CPU reads and no sampler/draw alias',()=>{
 const reads=[],env=fakeGL(reads),flow=make(env.gl,[24,16,8]);flow.project({},{},{},1/30);assert.equal(flow.lastProjection.cycles,0);const beforeTextures=env.textures.length;flow.enableMaterialLedger();const added=env.textures.slice(beforeTextures),bytes=added.reduce((sum,t)=>sum+t.width*t.height*16,0);assert.equal(bytes,896);
 flow.lastProjection.axisRates=[1,2,3];const beforeDraws=env.draws.length,beforeReads=env.readCount;flow.transport(flow.projected.texture,{},1/30);assert.equal(env.readCount,beforeReads);assert.equal(flow.lastTransport.materialLedger.drawPasses,30);assert.equal(env.draws.length-beforeDraws,36);
 reads.push([10,20,5,0],[9,18,4,0],[1,2,1,0]);const ledger=flow.readMaterialLedger();assert.equal(ledger.finite,true);assert.deepEqual(Array.from(ledger.closure),[0,0,0]);assert.deepEqual(Array.from(ledger.outwardBoundaryFlux),[1,2,1]);assert.equal(env.readCount-beforeReads,3);
 flow.invalidateMaterialLedger();const count=env.readCount;assert.equal(flow.readMaterialLedger().available,false);assert.equal(env.readCount,count);flow.enableMaterialLedger(false);assert.equal(flow.materialLedgerEnabled,false);
 const fragment=flow.materialLedgerState.boundary.shaders.find(s=>s.type===env.gl.FRAGMENT_SHADER).source;assert(fragment.includes(flow.materialTransportGLSL));assert(fragment.includes('area*=.5'));assert(fragment.includes('side==0?c:c+e'));
});
