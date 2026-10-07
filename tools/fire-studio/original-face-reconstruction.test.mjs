import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const runtime='../../outputs/cybrdelic-type/elements/motion/bending/sigils/02/fire-live/';
const source=await readFile(new URL(runtime+'original-fine-flow.js',import.meta.url),'utf8'),advection=await readFile(new URL(runtime+'corrected-advection.js',import.meta.url),'utf8'),ctx={window:{}};vm.runInNewContext(source,ctx);vm.runInNewContext(advection,ctx);const Flow=ctx.window.OriginalFineFlow,Mac=ctx.window.MacCormackAdvection;
const near=(a,b,tolerance=1e-11)=>assert(Math.abs(a-b)<=tolerance*Math.max(1,Math.abs(a),Math.abs(b)),`${a} != ${b}`);
function reference(n,floor,provider){
 const h=n.map((q,a)=>1/(a===2?q-1:q)),bound=c=>c.map((q,a)=>Math.max(0,Math.min(n[a]-1,q))),slot=c=>{c=bound(c);const v=provider(c).slice();if(c[1]<floor)v.fill(0);if(c[1]===floor)v[1]=0;return v;};
 const geometry=p=>{const q=p.map(x=>Math.max(0,Math.min(1,x))),c=q.map((x,a)=>Math.min(n[a]-1,Math.floor(x/h[a]+(a===2?.5:0)))),width=h.map((x,a)=>x*(a===2&&(c[2]===0||c[2]===n[2]-1)?.5:1)),lower=[c[0]*h[0],c[1]*h[1],c[2]===0?0:(c[2]-.5)*h[2]],fraction=q.map((x,a)=>(x-lower[a])/width[a]);return {c,width,lower,fraction};};
 const sample=p=>{const g=geometry(p),left=slot(g.c),right=[0,1,2].map(a=>slot(g.c.map((x,k)=>x+(a===k?1:0)))[a]);return {...g,velocity:left.map((x,a)=>x+(right[a]-x)*g.fraction[a]),divergence:g.width.reduce((s,w,a)=>s+(p[a]>=0&&p[a]<=1?(right[a]-left[a])/w:0),0),left,right};};
 return {h,slot,geometry,sample};
}
function half(value){
 if(!Number.isFinite(value)||value===0)return value;const sign=Math.sign(value),a=Math.abs(value);if(a>=65520)return sign*Infinity;const step=2**Math.max(-24,Math.floor(Math.log2(a))-10),q=a/step,base=Math.floor(q),part=q-base;return sign*(base+(part>.5||part===.5&&base%2?1:0))*step;
}
const sourceLaw=(burn,fuel,temperature)=>Math.min(Math.max(burn,0)*5.5/(Math.max(1+fuel,1)*Math.max(.25+temperature,.25)),64);
test('actual predictor, reverse corrector and midpoint share identical generated normal-face GLSL',()=>{
 const n=[24,16,8],snippet=Flow.faceReconstructionGLSL({n,floor:2}),mock={nx:n[0],nz:n[1],depth:n[2],tilesX:8,width:192,height:16,conservativeTransport:true,faceReconstructionGLSL:snippet,makeCommonGLSL:()=>''},predictor=Mac.prototype.makePredictorFragment.call(mock,''),corrector=Mac.prototype.makeCorrectionGLSL.call(mock);
 // GLSL ES 3.00 section 3.8: these future-use words cannot be identifiers.
 assert.doesNotMatch(snippet,/\b(?:common|partition|active|asm|class|union|enum|typedef|template|this|goto|inline|noinline|public|static|extern|external|interface|long|short|double|half|fixed|unsigned|superp|input|output|filter|sizeof|cast|namespace|using)\b/);
 assert.equal(predictor.split(snippet).length,2);assert.equal(corrector.split(snippet).length,2);assert(source.includes('${this.faceReconstructionGLSL}'));
 assert.match(predictor,/velocity=originalFaceVelocity\(vfTex,at,false\)/);assert.match(predictor,/midVelocity=originalFaceVelocity\(vfTex,mid,false\)/);
 assert.match(corrector,/correctedVelocity=originalFaceVelocity\(vfTex,at,false\)/);assert.match(corrector,/back=at-originalFaceVelocity\(vfTex,scalarMid,false\)\*delta/);assert.match(corrector,/midVelocity=originalFaceVelocity\(vfTex,mid,false\)/);
 assert.match(source,/sourceAt\(vec3 p\)\{return source\(originalFaceCell\(p\)\);\}/);assert.match(source,/originalFaceDivergence\(uProjected,p,false\)/);assert.doesNotMatch(source,/float divergenceAt[^}]*p\+vec3\(H/);
 assert.throws(()=>Flow.faceReconstructionGLSL({n:[1,3,3],floor:0}),/Invalid normal-face/);assert.throws(()=>new Mac({createFramebuffer(){},getExtension(){return true;}},{nx:12,nz:9,depth:7,tilesX:8,tilesY:1,pressureSamplingGLSL:'',conservativeTransport:true}),/requires shared/);
});
test('discrete-curl normal reconstruction has zero analytic divergence throughout fluid cell interiors',t=>{
 const n=[17,13,9],floor=2,h=[1/n[0],1/n[1]],psi=(x,y,z)=>.0001*Math.sin(.7*x)*Math.max(y-floor,0)**2*Math.cos(.3*z),provider=([x,y,z])=>[(psi(x,y+1,z)-psi(x,y,z))/h[1],-(psi(x+1,y,z)-psi(x,y,z))/h[0],0],r=reference(n,floor,provider);let cells=0,max=0;
 for(let z=1;z<n[2]-1;z++)for(let y=floor;y<n[1]-1;y++)for(let x=1;x<n[0]-1;x++)for(const a of [.07,.31,.89]){const p=[(x+a)/n[0],(y+.73)/n[1],(z-.5+.43)/(n[2]-1)],s=r.sample(p);max=Math.max(max,Math.abs(s.divergence));near(s.divergence,0);cells++;}
 t.diagnostic(JSON.stringify({sampledFluidPoints:cells,maximumAnalyticDivergence:max}));
});
test('the old finite-difference false negative is corrected by changing actual reconstruction, not its error threshold',()=>{
 const ux=(i,j)=>1e-4*i*i*(2*j+1),uy=(i,j)=>-1e-4*(2*i+1)*j*j,mix=(a,b,t)=>a*(1-t)+b*t,bilinear=(v,x,y)=>{const i=Math.floor(x),j=Math.floor(y),a=x-i,b=y-j;return mix(mix(v(i,j),v(i+1,j),a),mix(v(i,j+1),v(i+1,j+1),a),b);},x=3.2,y=2.7;
 const oldDiagnostic=bilinear(ux,x+1,y)-bilinear(ux,x,y)+bilinear(uy,x,y+1)-bilinear(uy,x,y),actualOldDivergence=1e-4*((2*Math.floor(x)+1)*(2*y+1)-(2*x+1)*(2*Math.floor(y)+1));near(oldDiagnostic,0);near(actualOldDivergence,.00078);
 const r=reference([12,12,5],0,([i,j])=>[ux(i,j),uy(i,j),0]);near(r.sample([x/12,y/12,.5]).divergence,0);
});
test('normal face values and fluxes are continuous across shared faces, including floor no-penetration',()=>{
 const n=[12,10,7],floor=2,r=reference(n,floor,([x,y,z])=>[.13*Math.sin(x+y),.1*Math.cos(x-z),.07*Math.sin(y+z)]);
 for(let a=0;a<3;a++)for(let k=2;k<n[a]-2;k++){const p=[.45,.55,.45];p[a]=a===2?(k-.5)/(n[2]-1):k/n[a];const left=p.slice(),right=p.slice();left[a]-=1e-8;right[a]+=1e-8;near(r.sample(left).velocity[a],r.sample(right).velocity[a],2e-7);}
 for(const x of [.02,.31,.94])for(const z of [0,.23,1]){near(r.sample([x,floor/n[1],z]).velocity[1],0);assert.deepEqual(r.sample([x,(floor-.2)/n[1],z]).velocity,[0,0,0]);}
});
test('analytic divergence uses exact endpoint half-depth and existing clamped open-face slots',()=>{
 const n=[11,9,7],r=reference(n,0,([x,y,z])=>[0,0,(z===0?0:(z-.5)/(n[2]-1))*.3]);
 near(r.sample([.4,.5,.03]).width[2],.5/(n[2]-1));near(r.sample([.4,.5,.03]).divergence,.3);near(r.sample([.4,.5,.51]).divergence,.3);near(r.sample([.4,.5,.99]).divergence,0);near(r.sample([.4,.5,1.2]).divergence,0);
 const open=reference(n,0,([x])=>[x===0?0:1,0,0]);near(open.sample([.2/n[0],.5,.5]).divergence,n[0]);assert(Flow.projectionScore([n[0],n[0],n[0],0])>1,'Real boundary-shell divergence must remain a failure');
});
test('exact solved cell source removes a nonlinear interpolation commutator without changing reaction law',t=>{
 const n=[12,8,5],burn=.1,temp=.25,S=x=>sourceLaw(burn,x%2?4:0,temp),faces=[0];for(let x=0;x<n[0]-1;x++)faces.push(faces.at(-1)+S(x)/n[0]);const r=reference(n,0,([x])=>[faces[x],0,0]);let max=0;
 for(let x=1;x<n[0]-2;x++)for(const a of [.12,.75,.93]){const p=[(x+a)/n[0],.6,.5],s=r.sample(p),exactSource=S(s.c[0]);max=Math.max(max,Math.abs(s.divergence-exactSource));near(s.divergence,exactSource);}
 const oldInterpolatedSources=.5*(sourceLaw(.1,0,.25)+sourceLaw(.1,4,.25)),oldRecomputedSource=sourceLaw(.1,2,.25);near(oldInterpolatedSources-oldRecomputedSource,.29333333333333333);near(sourceLaw(1000,0,0),64);near(sourceLaw(-1,0,0),0);t.diagnostic(JSON.stringify({maximumConsistentSourceResidual:max,oldNonlinearCommutator:oldInterpolatedSources-oldRecomputedSource}));
});
test('genuinely divergent normal fields and unsupported floor sources still fail unchanged acceptance',()=>{
 const n=[12,10,7],r=reference(n,0,([x])=>[.3*x/n[0],0,0]),D=r.sample([.45,.51,.5]).divergence;near(D,.3);assert(Flow.projectionScore([.3,Math.abs(D),.3,0])>1);
 const floor=reference(n,2,()=>[0,1,0]),floorD=floor.sample([.4,2.5/n[1],.5]).divergence;near(floorD,10);assert(Flow.projectionScore([10,10,10,0])>1);assert(Flow.projectionScore([1,.2,1,0])>1);assert.equal(Flow.projectionScore([1,.1,1,0]),1);assert.equal(Flow.projectionScore([1,NaN,1,0]),Infinity);
});
test('half-float quantization creates measured divergence rather than being hidden by reconstruction',t=>{
 near(half(1/3),.333251953125);near(half(1+2**-11),1);near(half(1+3*2**-11),1+2**-9);near(half(2**-25),0);assert.equal(half(65520),Infinity);
 const n=[12,10,7],provider=([x,y])=>[.0001*x*x*(2*y+1)*n[1],-.0001*(2*x+1)*y*y*n[0],0],raw=reference(n,0,provider),rounded=reference(n,0,c=>provider(c).map(half)),p=[3.2/n[0],2.7/n[1],.5],before=raw.sample(p).divergence,after=rounded.sample(p).divergence;
 near(before,0);assert(Math.abs(after)>1e-5);assert(Flow.projectionScore([.001,Math.abs(after),.001,0])>1);t.diagnostic(JSON.stringify({unquantizedDivergence:before,halfFloatDivergence:after,unchangedTargetRejects:true}));
});
test('reconstructed divergence integrates to identical signed boundary face flux with half-depth weights',t=>{
 const n=[13,9,7],floor=2,r=reference(n,floor,([x,y,z])=>[.2*Math.sin(x*.31+y*.17),.13*Math.cos(y*.37-z*.23),.07*Math.sin(z*.49-x*.19)]);let integral=0,boundary=0;
 for(let z=0;z<n[2];z++)for(let y=0;y<n[1];y++)for(let x=0;x<n[0];x++){const c=[x,y,z],p=[(x+.5)/n[0],(y+.5)/n[1],z/(n[2]-1)],s=r.sample(p),volume=s.width.reduce((a,b)=>a*b,1);integral+=s.divergence*volume;for(let a=0;a<3;a++){const area=volume/s.width[a];if(c[a]===0)boundary-=s.left[a]*area;if(c[a]===n[a]-1)boundary+=s.right[a]*area;}}
 near(integral,boundary);t.diagnostic(JSON.stringify({volumeDivergence:integral,signedBoundaryFlux:boundary,closure:integral-boundary}));
});
