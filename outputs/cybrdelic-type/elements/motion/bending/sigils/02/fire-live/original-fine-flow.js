/* Compatible fine pressure impulse and conservative directional Hancock transport.
 * Original only. Pressure uses the shipped forward D/backward G. Oxygen remains
 * intensive. Flux limiting changes face reconstruction, never cell inventory.
 */
(() => {
 'use strict';
 const VERTEX=`#version 300 es
 precision highp float;
 void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.-1.,0,1);}`;
 function hierarchy(grid,extent,minimum){
  const rows=[];let n=grid.slice();
  for(;;){
   const h=extent.map((e,i)=>e/(i===2?n[i]-1:n[i])),floor=Math.max(0,Math.min(n[1]-2,Math.round(-minimum[1]/extent[1]*n[1])));
   rows.push({n:n.slice(),h,floor,tiles:8,width:n[0]*8,height:n[1]*Math.ceil(n[2]/8)});
   if(n[0]<=10&&n[1]<=8)break;
   const xy=Math.max(h[0],h[1]),depth=n[2]>5&&h[2]<2.5*xy?Math.max(5,Math.ceil((n[2]-1)/2)+1):n[2];
   n=[Math.max(6,Math.ceil(n[0]/2)),Math.max(6,Math.ceil(n[1]/2)),depth];
  }return rows;
 }
 function common(g){
  const [x,y,z]=g.n,w=g.h.map(v=>1/(v*v));
  return `precision highp float;precision highp int;precision highp sampler2D;
  const ivec3 N=ivec3(${x},${y},${z});const vec3 NF=vec3(${x}.0,${y}.0,${z}.0);
  const int FLOOR=${g.floor};const vec3 W=vec3(${w.join(',')});
  ivec3 cell(){ivec2 p=ivec2(gl_FragCoord.xy);return ivec3(p.x%N.x,p.y%N.y,p.x/N.x+8*(p.y/N.y));}
  ivec2 pixel(ivec3 c){return ivec2((c.z%8)*N.x+c.x,(c.z/8)*N.y+c.y);}
  bool valid(ivec3 c){return all(greaterThanEqual(c,ivec3(0)))&&all(lessThan(c,N));}
  bool fluid(ivec3 c){return c.x>0&&c.x<N.x-1&&c.y>=FLOOR&&c.y<N.y-1&&c.z>0&&c.z<N.z-1;}
  float phi(sampler2D tex,ivec3 c){c.y=max(c.y,FLOOR);return fluid(c)?texelFetch(tex,pixel(c),0).r:0.;}
  float lap(sampler2D p,ivec3 c){float q=phi(p,c);return W.x*(phi(p,c+ivec3(1,0,0))+phi(p,c-ivec3(1,0,0))-2.*q)+W.y*(phi(p,c+ivec3(0,1,0))+phi(p,c-ivec3(0,1,0))-2.*q)+W.z*(phi(p,c+ivec3(0,0,1))+phi(p,c-ivec3(0,0,1))-2.*q);}
  layout(location=0) out vec4 result;`;
 }
 class OriginalFineFlow {
  static setup(gl,options){return new OriginalFineFlow(gl,options);}
  static hierarchy=hierarchy;
  // DD^T has three independent blocks on the clamped upper-depth plane:
  // rectangle, x outlet edge and y outlet edge. Its corner has no tangential
  // freedom. K=(n/extent)^2 minimizes physical velocity energy.
  static upperBoundaryHierarchy(g,extent){
   const levels=[];let m=g.n[0]-1,r=g.n[1]-g.floor-1,kx=(g.n[0]/extent[0])**2,ky=(g.n[1]/extent[1])**2;
   for(;;){levels.push({m,r,kx,ky,width:m+1,height:r+1});if(m<=7&&r<=7)break;
    const nextM=Math.max(1,Math.ceil((m+1)/2)-1),nextR=Math.max(1,Math.ceil(r/2));
    kx*=((nextM+1)/(m+1))**2;ky*=((nextR+.5)/(r+.5))**2;m=nextM;r=nextR;
   }return levels;
  }
  static upperBoundaryGLSL(g){return `precision highp float;precision highp int;precision highp sampler2D;
   const int M=${g.m},R=${g.r};const vec2 K=vec2(${g.kx},${g.ky});layout(location=0)out vec4 result;
   int region(ivec2 c){return (c.x==M?2:0)+(c.y==R?1:0);}
   float value(sampler2D tex,ivec2 c,int block){
    if(block==3)return 0.;
    if(block==1){if(c.x<0||c.x>=M)return 0.;c.y=R;}
    else if(block==2){if(c.y>=R)return 0.;c=ivec2(M,max(c.y,0));}
    else {c.y=max(c.y,0);if(c.x<0||c.x>=M||c.y>=R)return 0.;}
    return texelFetch(tex,c,0).r;
   }
   float diagonal(ivec2 c){return (c.x<M?2.*K.x:0.)+(c.y<R?(c.y==0?K.y:2.*K.y):0.);}
   float operatorA(sampler2D tex,ivec2 c){int block=region(c);float p=value(tex,c,block),a=0.;
    if(c.x<M)a+=K.x*(2.*p-value(tex,c-ivec2(1,0),block)-value(tex,c+ivec2(1,0),block));
    if(c.y<R)a+=K.y*(2.*p-value(tex,c-ivec2(0,1),block)-value(tex,c+ivec2(0,1),block));return a;
   }`;}
  // One normal-face reconstruction for the actual intensive-scalar trajectory
  // and its acceptance metric. Tangential values are piecewise constant; each
  // normal component is linear between the exact transport face slots.
  static faceReconstructionGLSL(g){
   const [nx,ny,nz]=g.n;if(!g.n.every(n=>Number.isInteger(n)&&n>=2)||!Number.isInteger(g.floor)||g.floor<0||g.floor>=ny)throw Error('Invalid normal-face reconstruction grid');
   return `const ivec3 ORIGINAL_FACE_N=ivec3(${nx},${ny},${nz});const vec3 ORIGINAL_FACE_NF=vec3(${nx}.0,${ny}.0,${nz}.0);
    const vec3 ORIGINAL_FACE_H=vec3(${1/nx},${1/ny},${1/(nz-1)});const int ORIGINAL_FACE_FLOOR=${g.floor};
    ivec2 originalFacePixel(ivec3 c){return ivec2((c.z%8)*ORIGINAL_FACE_N.x+c.x,(c.z/8)*ORIGINAL_FACE_N.y+c.y);}
    vec3 originalFaceAt(ivec3 c){return vec3((vec2(c.xy)+.5)/ORIGINAL_FACE_NF.xy,float(c.z)/(ORIGINAL_FACE_NF.z-1.));}
    ivec3 originalFaceCell(vec3 p){p=clamp(p,vec3(0),vec3(1));return clamp(ivec3(floor(vec3(p.xy*ORIGINAL_FACE_NF.xy,p.z*(ORIGINAL_FACE_NF.z-1.)+.5))),ivec3(0),ORIGINAL_FACE_N-1);}
    vec3 originalFaceWidth(ivec3 c){return ORIGINAL_FACE_H*vec3(1,1,(c.z==0||c.z==ORIGINAL_FACE_N.z-1)?.5:1.);}
    vec3 originalFaceCoordinate(vec3 p,ivec3 c){vec3 lower=vec3(vec2(c.xy)*ORIGINAL_FACE_H.xy,c.z==0?0.:(float(c.z)-.5)*ORIGINAL_FACE_H.z);return (clamp(p,vec3(0),vec3(1))-lower)/originalFaceWidth(c);}
    vec3 originalFaceSlot(sampler2D tex,ivec3 c,bool coarse){c=clamp(c,ivec3(0),ORIGINAL_FACE_N-1);vec3 v=texelFetch(tex,originalFacePixel(c),0).xyz;if(coarse)v+=samplePressureCorrection(originalFaceAt(c));if(c.y<ORIGINAL_FACE_FLOOR)v=vec3(0);if(c.y==ORIGINAL_FACE_FLOOR)v.y=0.;return v;}
    vec3 originalFaceUpper(sampler2D tex,ivec3 c,bool coarse){return vec3(originalFaceSlot(tex,c+ivec3(1,0,0),coarse).x,originalFaceSlot(tex,c+ivec3(0,1,0),coarse).y,originalFaceSlot(tex,c+ivec3(0,0,1),coarse).z);}
    vec3 originalFaceVelocity(sampler2D tex,vec3 p,bool coarse){ivec3 c=originalFaceCell(p);return mix(originalFaceSlot(tex,c,coarse),originalFaceUpper(tex,c,coarse),originalFaceCoordinate(p,c));}
    float originalFaceDivergence(sampler2D tex,vec3 p,bool coarse){ivec3 c=originalFaceCell(p);vec3 normalDerivativeMask=step(vec3(0),p)*step(p,vec3(1));return dot((originalFaceUpper(tex,c,coarse)-originalFaceSlot(tex,c,coarse))/originalFaceWidth(c),normalDerivativeMask);}
   `;
  }
  static projectionScore(m){return m?.length===4&&m.every(Number.isFinite)&&m[3]===0?Math.max(m[1]/(.1*Math.max(m[2],1e-6)),m[1]/(.2*Math.max(m[0],1e-6))):Infinity;}
  // The normal four-cycle path is unchanged. Extra work is admitted only for
  // a near-target, contracting measured residual, with a predicted bounded exit.
  static correctionDecision(history,extraElapsedMs=0){
   const last=history.at(-1),score=Math.max(last.centerScore,last.midpointScore??0);
   if(!Number.isFinite(score))return {action:'reject',reason:'nonfinite'};
   if(score<=1&&last.midpointScore!==null)return {action:'accept',reason:'targets met'};
   if(last.cycles<4)return {action:'correct',reason:'normal budget'};
   const remaining=6-last.cycles;if(remaining<=0)return {action:'reject',reason:'correction count budget'};
   const key=(last.midpointScore??0)>last.centerScore?'midpointScore':'centerScore',previous=history.slice(0,-1).reverse().find(h=>Number.isFinite(h[key])&&h[key]>0);
   const contraction=previous?last[key]/previous[key]:Infinity;
   if(score>1.6||contraction>=.95||!(contraction>0))return {action:'reject',reason:'residual is not near and contracting',contraction};
   const predictedCycles=Math.max(1,Math.ceil(Math.log(1/score)/Math.log(contraction))),predictedMs=predictedCycles*last.wallMs;
   if(predictedCycles>remaining||extraElapsedMs+predictedMs>48)return {action:'reject',reason:'predicted correction exceeds budget',contraction,predictedCycles,predictedMs};
   return {action:'correct',reason:'near-target residual correction',contraction,predictedCycles,predictedMs};
  }
  // Binomial-filter residuals only along axes that are coarsened. Combined
  // filter/interpolation weights reproduce [.25,.5,.25] then mapped sampling.
  // Raw residuals are zero outside the fluid mask; pressure ghosts stay separate.
  static restrictionGLSL(fine,coarse){
   const reduced=fine.n.map((n,a)=>n>coarse.n[a]),counts=reduced.map(r=>r?4:1);
   return `uniform sampler2D uFine;const ivec3 F=ivec3(${fine.n.join(',')});
   float residual(ivec3 c){if(any(lessThan(c,ivec3(0)))||any(greaterThanEqual(c,F)))return 0.;return texelFetch(uFine,ivec2((c.z%8)*F.x+c.x,(c.z/8)*F.y+c.y),0).r;}
   vec4 weights(float a){return vec4(.25*(1.-a),.5-.25*a,.25+.25*a,.25*a);}
   void main(){ivec3 c=cell();if(!fluid(c)){result=vec4(0);return;}
    vec3 center=vec3((vec2(c.xy)+.5)/NF.xy,float(c.z)/(NF.z-1.));
    vec3 q=vec3(center.xy*vec2(F.xy)-.5,center.z*float(F.z-1));
    ${reduced.map((r,a)=>r?'':`q[${a}]=float(c[${a}]);`).join('')}
    ivec3 lo=ivec3(floor(q));vec3 a=fract(q);ivec3 start=lo-ivec3(${reduced.map(Number).join(',')});
    vec4 wx=${reduced[0]?'weights(a.x)':'vec4(1,0,0,0)'},wy=${reduced[1]?'weights(a.y)':'vec4(1,0,0,0)'},wz=${reduced[2]?'weights(a.z)':'vec4(1,0,0,0)'};
    float sum=0.;for(int z=0;z<${counts[2]};z++)for(int y=0;y<${counts[1]};y++)for(int x=0;x<${counts[0]};x++)sum+=residual(start+ivec3(x,y,z))*wx[x]*wy[y]*wz[z];result=vec4(sum,0,0,1);
   }`;
  }
  static hancockGLSL=`float hancock(float left,float center,float right,float uLeft,float uRight,float sigma,float side){
   float a=2.*(center-left);float b=.5*(right-left);float d=2.*(right-center);
   float slope=.25*(sign(a)+sign(b))*abs(sign(a)+sign(d))*min(abs(a),min(abs(b),abs(d)));
   float base=center*(1.-(.5*sigma)*(uRight-uLeft));float drift=(.25*sigma)*(uRight+uLeft);
   float leftValue=base+(-.5-drift)*slope;float rightValue=base+(.5-drift)*slope;
   float lower=min(leftValue,rightValue);float theta=lower<0.?min(1.,base/(base-lower))*(1.-8.*1.1920928955078125e-7):1.;
   return base+theta*((side*.5-drift)*slope);
  }`;
  static schedule(delta,rates){if(!(delta>0)||!Number.isFinite(delta)||rates.length!==3||!rates.every(r=>Number.isFinite(r)&&r>=0))throw Error('Invalid Hancock clock or rates');return [[0,.5],[1,.5],[2,1],[1,.5],[0,.5]].map(([axis,fraction])=>{let steps=Math.max(1,Math.ceil(delta*fraction*rates[axis]/(.9*(1-8*2**-23))));while(Math.fround(Math.fround(delta*fraction/steps)*rates[axis])>.9)steps++;if(steps>512)throw Error('Hancock CFL requires unsupported work: '+steps);const step=Math.fround(delta*fraction/steps);return {axis,fraction,steps,delta:step,CFL:Math.fround(step*rates[axis])};});}

  constructor(gl,{nx,ny,depth,extent,minimum,pressureGLSL}){
   this.gl=gl;this.grid=[nx,ny,depth];this.extent=extent;this.minimum=minimum;this.pressureGLSL=pressureGLSL;
   this.textures=[];this.fbos=[];this.programs=[];this.shaders=[];this.locations=new Map();this.vao=gl.createVertexArray();
   this.levels=hierarchy(this.grid,extent,minimum).map((g,i)=>({...g,p:[this.target(g,i===0?gl.RG32F:gl.R32F),this.target(g,i===0?gl.RG32F:gl.R32F)],rhs:this.target(g,gl.R32F),residual:this.target(g,gl.R32F),current:0}));
   const fine=this.levels[0];this.projected=this.target(fine,gl.RGBA16F);
   // Projection owns these planes first. Transport aliases them only after all
   // acceptance reductions finish; debug pressure/RHS references then expire.
   this.states=fine.p.map((p,i)=>this.transportTarget(p,i===0?fine.rhs:fine.residual));
   this.neutral=this.target({width:1,height:1},gl.RGBA16F);this.clear(this.neutral);
   this.reduceTargets=[];let width=fine.width,height=fine.height;
   while(width>1||height>1){width=Math.ceil(width/4);height=Math.ceil(height/4);this.reduceTargets.push(this.target({width,height},gl.RGBA32F));}
   const point=`${common(fine)}
   const vec3 EXTENT=vec3(${extent.join(',')});const vec3 H=vec3(${(1/nx)},${(1/ny)},${(1/(depth-1))});
   vec3 at(ivec3 c){return vec3((vec2(c.xy)+.5)/NF.xy,float(c.z)/(NF.z-1.));}
   ivec3 bounded(ivec3 c){return clamp(c,ivec3(0),N-1);}
   vec4 raw(sampler2D tex,ivec3 c){return texelFetch(tex,pixel(bounded(c)),0);}
   vec4 fieldFine(sampler2D tex,vec3 p){vec3 q=vec3(clamp(p.xy*NF.xy-.5,vec2(0),NF.xy-1.),clamp(p.z,0.,1.)*(NF.z-1.));ivec3 lo=ivec3(floor(q)),hi=min(lo+1,N-1);vec3 a=fract(q);return mix(mix(mix(raw(tex,lo),raw(tex,ivec3(hi.x,lo.y,lo.z)),a.x),mix(raw(tex,ivec3(lo.x,hi.y,lo.z)),raw(tex,ivec3(hi.x,hi.y,lo.z)),a.x),a.y),mix(mix(raw(tex,ivec3(lo.x,lo.y,hi.z)),raw(tex,ivec3(hi.x,lo.y,hi.z)),a.x),mix(raw(tex,ivec3(lo.x,hi.y,hi.z)),raw(tex,hi),a.x),a.y),a.z);}
   ${pressureGLSL}
   uniform sampler2D uVf,uChem;
   vec3 traced(ivec3 c){c=bounded(c);vec3 v=raw(uVf,c).xyz+samplePressureCorrection(at(c));if(c.y<FLOOR)v=vec3(0);if(c.y==FLOOR)v.y=0.;return v;}
   float divergence(sampler2D v,ivec3 c){vec3 q=raw(v,c).xyz;return (raw(v,c+ivec3(1,0,0)).x-q.x)/H.x+(raw(v,c+ivec3(0,1,0)).y-q.y)/H.y+(raw(v,c+ivec3(0,0,1)).z-q.z)/H.z;}
   float source(ivec3 c){vec4 v=raw(uVf,c),q=raw(uChem,c);return min(max(v.a,0.)*5.5/(max(1.+q.r,1.)*max(.25+q.b,.25)),64.);}
   float outgoing(sampler2D v,ivec3 c){float depthWeight=(c.z==0||c.z==N.z-1)?.5:1.;return (max(raw(v,c+ivec3(1,0,0)).x,0.)+max(-raw(v,c).x,0.))/H.x+(max(raw(v,c+ivec3(0,1,0)).y,0.)+max(-raw(v,c).y,0.))/H.y+(max(raw(v,c+ivec3(0,0,1)).z,0.)+max(-raw(v,c).z,0.))/(H.z*depthWeight);}`;
   this.rhsProgram=this.program(point+`void main(){ivec3 c=cell();if(!fluid(c)){result=vec4(0);return;}vec3 v=traced(c);float d=(traced(c+ivec3(1,0,0)).x-v.x)/H.x+(traced(c+ivec3(0,1,0)).y-v.y)/H.y+(traced(c+ivec3(0,0,1)).z-v.z)/H.z;result=vec4(d-source(c),0,0,1);}`);
   this.applyProgram=this.program(point+`uniform sampler2D uP;void main(){ivec3 c=cell();if(!valid(c)){result=vec4(0);return;}vec4 v=raw(uVf,c);float p=phi(uP,c);vec3 grad=vec3(p-phi(uP,c-ivec3(1,0,0)),p-phi(uP,c-ivec3(0,1,0)),p-phi(uP,c-ivec3(0,0,1)))/vec3(${fine.h.join(',')});v.xyz=traced(c)-grad/EXTENT;if(c.y<FLOOR)v.xyz=vec3(0);if(c.y==FLOOR)v.y=0.;result=v;}`);
   this.pressureCopyProgram=this.program(common(fine)+`uniform sampler2D uInput;void main(){ivec3 c=cell();result=fluid(c)?vec4(texelFetch(uInput,pixel(c),0).r,0,0,1):vec4(0);}`);this.warmPressure=null;this.warmValid=false;
   const fused=(metric,maximum=false)=>metric+`void main(){ivec2 base=ivec2(gl_FragCoord.xy)*4,sz=ivec2(${fine.width},${fine.height});result=vec4(0);for(int y=0;y<4;y++)for(int x=0;x<4;x++){ivec2 p=base+ivec2(x,y);if(all(lessThan(p,sz))){ivec3 c=ivec3(p.x%N.x,p.y%N.y,p.x/N.x+8*(p.y/N.y));vec4 q=metric(c);${maximum?'result=max(result,q);':'result.xyz+=q.xyz;result.a=max(result.a,q.a);'}}}}`;
   this.metricsProgram=this.program(fused(point+`uniform sampler2D uProjected,uRhs;uniform float uReusePre;vec4 metric(ivec3 c){if(!valid(c))return vec4(0);float d=divergence(uProjected,c),s=source(c),pre=uReusePre>0.?0.:raw(uRhs,c).r;float includeCell=float(fluid(c));return vec4(abs(pre)*includeCell,abs(d-s)*includeCell,uReusePre>0.?0.:(abs(pre+s)+abs(s))*includeCell,0);}`));
   this.faceReconstructionGLSL=OriginalFineFlow.faceReconstructionGLSL(fine);
   this.midpointProgram=this.program(fused(point+`uniform sampler2D uProjected;uniform float uDelta,uReusePre;
   ${this.faceReconstructionGLSL}
   vec3 flowAt(vec3 p,bool post){return post?originalFaceVelocity(uProjected,p,false):originalFaceVelocity(uVf,p,true);}
   float sourceAt(vec3 p){return source(originalFaceCell(p));}
   float divergenceAt(vec3 p,bool post){return post?originalFaceDivergence(uProjected,p,false):originalFaceDivergence(uVf,p,true);}
   vec4 metric(ivec3 c){if(!fluid(c))return vec4(0);vec3 p=at(c),post=p-.5*flowAt(p,true)*uDelta;float b=divergenceAt(post,true);if(uReusePre>0.)return vec4(0,abs(b-sourceAt(post)),0,0);vec3 pre=p-.5*flowAt(p,false)*uDelta;float a=divergenceAt(pre,false);return vec4(abs(a-sourceAt(pre)),abs(b-sourceAt(post)),abs(a)+abs(sourceAt(pre)),0);}`));
   this.rateProgram=this.program(fused(point+`uniform sampler2D uProjected;vec4 metric(ivec3 c){if(!valid(c))return vec4(0);vec3 l=raw(uProjected,c).xyz,r=vec3(raw(uProjected,c+ivec3(1,0,0)).x,raw(uProjected,c+ivec3(0,1,0)).y,raw(uProjected,c+ivec3(0,0,1)).z);vec3 width=H;width.z*=c.z==0||c.z==N.z-1?.5:1.;return vec4(max(max(abs(l),abs(r)),max(r,vec3(0))+max(-l,vec3(0)))/width,0);}`,true));
   this.reduceProgram=this.program(`#version 300 es
   precision highp float;precision highp int;precision highp sampler2D;uniform sampler2D uInput;layout(location=0)out vec4 result;
   void main(){ivec2 base=ivec2(gl_FragCoord.xy)*4,sz=textureSize(uInput,0);vec4 sum=vec4(0);for(int y=0;y<4;y++)for(int x=0;x<4;x++){ivec2 p=base+ivec2(x,y);if(all(lessThan(p,sz))){vec4 q=texelFetch(uInput,p,0);sum.xyz+=q.xyz;sum.a=max(sum.a,q.a);}}result=sum;}`);
   this.reduceMaxProgram=this.program(`#version 300 es
   precision highp float;precision highp int;precision highp sampler2D;uniform sampler2D uInput;layout(location=0)out vec4 result;
   void main(){ivec2 base=ivec2(gl_FragCoord.xy)*4,sz=textureSize(uInput,0);result=vec4(0);for(int y=0;y<4;y++)for(int x=0;x<4;x++){ivec2 p=base+ivec2(x,y);if(all(lessThan(p,sz)))result=max(result,texelFetch(uInput,p,0));}}`);
   for(let i=0;i<this.levels.length;i++){
    const l=this.levels[i],g=common(l);
    l.smooth=this.program(g+`uniform sampler2D uP,uRhs;void main(){ivec3 c=cell();if(!fluid(c)){result=vec4(0);return;}float p=phi(uP,c),diag=2.*(W.x+W.y+W.z)-(c.y==FLOOR?W.y:0.);float next=p+(lap(uP,c)-texelFetch(uRhs,pixel(c),0).r)/diag;result=vec4(mix(p,next,2./3.),0,0,1);}`);
    l.residualProgram=this.program(g+`uniform sampler2D uP,uRhs;void main(){ivec3 c=cell();result=fluid(c)?vec4(texelFetch(uRhs,pixel(c),0).r-lap(uP,c),0,0,1):vec4(0);}`);
    if(i+1<this.levels.length){
     const coarse=this.levels[i+1],C=common(coarse),[fx,fy,fz]=l.n;
     coarse.restrict=this.program(C+OriginalFineFlow.restrictionGLSL(l,coarse));
     l.prolong=this.program(g+`uniform sampler2D uP,uCoarse;const ivec3 C=ivec3(${coarse.n.join(',')});const int CFLOOR=${coarse.floor};float cp(ivec3 c){c.y=max(c.y,CFLOOR);if(c.x<=0||c.x>=C.x-1||c.y>=C.y-1||c.z<=0||c.z>=C.z-1)return 0.;return texelFetch(uCoarse,ivec2((c.z%8)*C.x+c.x,(c.z/8)*C.y+c.y),0).r;}void main(){ivec3 c=cell();if(!fluid(c)){result=vec4(0);return;}vec3 at=vec3((vec2(c.xy)+.5)/NF.xy,float(c.z)/(NF.z-1.));vec3 q=vec3(at.xy*vec2(C.xy)-.5,at.z*float(C.z-1));ivec3 lo=ivec3(floor(q));vec3 a=fract(q);float value=0.;for(int z=0;z<2;z++)for(int y=0;y<2;y++)for(int x=0;x<2;x++){vec3 w=mix(1.-a,a,vec3(x,y,z));value+=cp(lo+ivec3(x,y,z))*w.x*w.y*w.z;}result=vec4(phi(uP,c)+value,0,0,1);}`);
    }
   }
   const transport=common(fine)+`const vec3 H=vec3(${1/nx},${1/ny},${1/(depth-1)});uniform sampler2D uQ,uS,uVf;
   vec3 q(ivec3 c){if(!valid(c))return vec3(0);return vec3(texelFetch(uQ,pixel(c),0).rg,texelFetch(uS,pixel(c),0).r);}
   vec3 velocity(ivec3 c){c=clamp(c,ivec3(0),N-1);vec3 v=texelFetch(uVf,pixel(c),0).xyz;if(c.y<FLOOR)v=vec3(0);if(c.y==FLOOR)v.y=0.;return v;}
   float width(ivec3 c,int axis){return H[axis]*(axis==2&&(c.z==0||c.z==N.z-1)?.5:1.);}
   ${OriginalFineFlow.hancockGLSL}
   vec3 flux(ivec3 face,ivec3 e,int axis,float dt){float u=velocity(face)[axis];ivec3 donor=u>=0.?face-e:face;if(!valid(donor))return vec3(0);vec3 l=q(donor-e),center=q(donor),r=q(donor+e);float uL=velocity(donor)[axis],uR=velocity(donor+e)[axis],sigma=dt/width(donor,axis),side=u>=0.?1.:-1.;return u*vec3(hancock(l.r,center.r,r.r,uL,uR,sigma,side),hancock(l.g,center.g,r.g,uL,uR,sigma,side),hancock(l.b,center.b,r.b,uL,uR,sigma,side));}`;
   this.seedProgram=this.program(common(fine)+`uniform sampler2D uChem;layout(location=1)out float sootResult;void main(){ivec3 c=cell();vec4 q=valid(c)?texelFetch(uChem,pixel(c),0):vec4(0);result=vec4(q.r,(1.+q.r)*q.b,0,0);sootResult=q.a;}`);
   this.fluxProgram=this.program(transport+`uniform float uDelta,uAxis;layout(location=1)out float sootResult;void main(){ivec3 c=cell();if(!valid(c)){result=vec4(0);sootResult=0.;return;}int axis=int(uAxis);ivec3 e=ivec3(axis==0?1:0,axis==1?1:0,axis==2?1:0);vec3 next=q(c)-(uDelta/width(c,axis))*(flux(c+e,e,axis,uDelta)-flux(c,e,axis,uDelta));result=vec4(next.rg,0,0);sootResult=next.b;}`);
   this.materialTransportGLSL=transport;this.materialFusedGLSL=fused;this.materialLedgerEnabled=false;this.materialLedgerState=null;
   this.lastProjection=null;this.lastTransport=null;
   this.setupUpperBoundary(fine);
  }
  setupUpperBoundary(fine){
   const gl=this.gl,[nx,ny,nz]=fine.n,floor=fine.floor;
   this.upperLevels=OriginalFineFlow.upperBoundaryHierarchy(fine,this.extent).map(g=>({...g,p:[this.target(g,gl.R32F),this.target(g,gl.R32F)],rhs:this.target(g,gl.R32F),residual:this.target(g,gl.R32F),current:0}));
   this.upperVelocity=this.target({width:nx,height:ny},gl.RGBA16F);
   const finest=this.upperLevels[0],base=OriginalFineFlow.upperBoundaryGLSL(finest);
   const plane=`const int FLOOR=${floor};const ivec2 OFFSET=ivec2(${(nz-1)%8*nx},${Math.floor((nz-1)/8)*ny});
    vec4 upper(sampler2D tex,ivec2 c){return texelFetch(tex,OFFSET+clamp(c,ivec2(0),ivec2(${nx-1},${ny-1})),0);}`;
   this.upperRhsProgram=this.program(base+plane+`uniform sampler2D uProjected,uSourceVF,uSourceChem;
    void main(){ivec2 c=ivec2(gl_FragCoord.xy);if(region(c)==3){result=vec4(0);return;}ivec2 xy=c+ivec2(0,FLOOR);
     vec4 v=upper(uProjected,xy),vf=upper(uSourceVF,xy),q=upper(uSourceChem,xy);
     float d=(upper(uProjected,xy+ivec2(1,0)).x-v.x)*${nx}.+(upper(uProjected,xy+ivec2(0,1)).y-v.y)*${ny}.;
     float s=min(max(vf.a,0.)*5.5/(max(1.+q.r,1.)*max(.25+q.b,.25)),64.);result=vec4(s-d,0,0,1);
    }`);
   this.upperApplyProgram=this.program(base+plane+`uniform sampler2D uProjected,uP;
    float xPhi(ivec2 c){return c.x<0||c.x>=M?0.:texelFetch(uP,c,0).r;}
    float yPhi(ivec2 c){return c.y<0||c.y>=R?0.:texelFetch(uP,c,0).r;}
    void main(){ivec2 xy=ivec2(gl_FragCoord.xy);vec4 v=upper(uProjected,xy);if(xy.y<FLOOR){result=v;return;}
     ivec2 c=xy-ivec2(0,FLOOR);v.x+=${nx/(this.extent[0]**2)}*(xPhi(c-ivec2(1,0))-xPhi(c));
     if(c.y>0)v.y+=${ny/(this.extent[1]**2)}*(yPhi(c-ivec2(0,1))-yPhi(c));result=v;
    }`);
   for(let i=0;i<this.upperLevels.length;i++){
    const l=this.upperLevels[i],g=OriginalFineFlow.upperBoundaryGLSL(l);
    l.smooth=this.program(g+`uniform sampler2D uP,uRhs;void main(){ivec2 c=ivec2(gl_FragCoord.xy);float diag=diagonal(c);if(diag==0.){result=vec4(0);return;}
     float p=texelFetch(uP,c,0).r,next=p+(texelFetch(uRhs,c,0).r-operatorA(uP,c))/diag;result=vec4(mix(p,next,2./3.),0,0,1);}`);
    l.residualProgram=this.program(g+`uniform sampler2D uP,uRhs;void main(){ivec2 c=ivec2(gl_FragCoord.xy);result=region(c)==3?vec4(0):vec4(texelFetch(uRhs,c,0).r-operatorA(uP,c),0,0,1);}`);
    if(i+1<this.upperLevels.length){
     const child=this.upperLevels[i+1],C=OriginalFineFlow.upperBoundaryGLSL(child),reducedX=l.m>child.m,reducedY=l.r>child.r;
     child.restrict=this.program(C+`uniform sampler2D uFine;const int FM=${l.m},FR=${l.r};
      float residual(ivec2 c,int block){if(block==1){if(c.x<0||c.x>=FM)return 0.;c.y=FR;}
       else if(block==2){if(c.y>=FR)return 0.;c=ivec2(FM,max(c.y,0));}
       else {c.y=max(c.y,0);if(c.x<0||c.x>=FM||c.y>=FR)return 0.;}return texelFetch(uFine,c,0).r;}
      vec4 weights(float a){return vec4(.25*(1.-a),.5-.25*a,.25+.25*a,.25*a);}
      void main(){ivec2 c=ivec2(gl_FragCoord.xy);int block=region(c);if(block==3){result=vec4(0);return;}
       vec2 q=vec2((float(c.x)+1.)*float(FM+1)/float(M+1)-1.,(float(c.y)+.5)*(float(FR)+.5)/(float(R)+.5)-.5);
       if(block==1)q.y=float(FR);if(block==2)q.x=float(FM);ivec2 lo=ivec2(floor(q));vec2 a=fract(q);vec4 wx=${reducedX?'weights(a.x)':'vec4(1,0,0,0)'},wy=${reducedY?'weights(a.y)':'vec4(1,0,0,0)'};
       float sum=0.;for(int y=0;y<${reducedY?4:1};y++)for(int x=0;x<${reducedX?4:1};x++){
        if((block==1&&y>0)||(block==2&&x>0))continue;
        ivec2 at=lo+ivec2(block==2?0:x-${reducedX?1:0},block==1?0:y-${reducedY?1:0});sum+=residual(at,block)*(block==2?1.:wx[x])*(block==1?1.:wy[y]);
       }result=vec4(sum,0,0,1);
      }`);
     l.prolong=this.program(g+`uniform sampler2D uP,uCoarse;const int CM=${child.m},CR=${child.r};
      float cp(ivec2 c,int block){if(block==1){if(c.x<0||c.x>=CM)return 0.;c.y=CR;}
       else if(block==2){if(c.y>=CR)return 0.;c=ivec2(CM,max(c.y,0));}
       else {c.y=max(c.y,0);if(c.x<0||c.x>=CM||c.y>=CR)return 0.;}return texelFetch(uCoarse,c,0).r;}
      void main(){ivec2 c=ivec2(gl_FragCoord.xy);int block=region(c);if(block==3){result=vec4(0);return;}
       vec2 q=vec2((float(c.x)+1.)*float(CM+1)/float(M+1)-1.,(float(c.y)+.5)*(float(CR)+.5)/(float(R)+.5)-.5);
       if(block==1)q.y=float(CR);if(block==2)q.x=float(CM);ivec2 lo=ivec2(floor(q));vec2 a=fract(q);float correction=0.;
       for(int y=0;y<2;y++)for(int x=0;x<2;x++){vec2 w=mix(1.-a,a,vec2(x,y));correction+=cp(lo+ivec2(x,y),block)*w.x*w.y;}
       result=vec4(texelFetch(uP,c,0).r+correction,0,0,1);
      }`);
    }
   }
  }
  smoothUpper(l,count){for(let j=0;j<count;j++){const next=1-l.current;this.draw(l.smooth,l.p[next],{uP:l.p[l.current].texture,uRhs:l.rhs.texture});l.current=next;}}
  cycleUpper(i=0){const l=this.upperLevels[i];if(i===this.upperLevels.length-1){this.smoothUpper(l,48);return;}
   this.smoothUpper(l,2);this.draw(l.residualProgram,l.residual,{uP:l.p[l.current].texture,uRhs:l.rhs.texture});const child=this.upperLevels[i+1];
   this.draw(child.restrict,child.rhs,{uFine:l.residual.texture});child.current=0;this.clear(child.p[0]);this.cycleUpper(i+1);
   const next=1-l.current;this.draw(l.prolong,l.p[next],{uP:l.p[l.current].texture,uCoarse:child.p[child.current].texture});l.current=next;this.smoothUpper(l,2);
  }
  prepareUpperBoundary(vf,chem){const l=this.upperLevels[0];l.current=0;this.clear(l.p[0]);
   this.draw(this.upperRhsProgram,l.rhs,{uProjected:this.projected.texture,uSourceVF:vf,uSourceChem:chem});
   for(let cycle=0;cycle<4;cycle++)this.cycleUpper();
  }
  copyUpperBoundary(){const gl=this.gl,[nx,ny,nz]=this.grid,l=this.upperLevels[0];
   // Only x/y are independent of the interior pressure cycles. Read each new
   // projected plane again so its current z component and alpha are retained.
   this.draw(this.upperApplyProgram,this.upperVelocity,{uProjected:this.projected.texture,uP:l.p[l.current].texture});
   gl.bindFramebuffer(gl.READ_FRAMEBUFFER,this.upperVelocity.fbo);gl.readBuffer(gl.COLOR_ATTACHMENT0);
   gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,this.projected.texture);gl.copyTexSubImage2D(gl.TEXTURE_2D,0,(nz-1)%8*nx,Math.floor((nz-1)/8)*ny,0,0,nx,ny);
  }
  target(g,internal){const gl=this.gl,texture=gl.createTexture(),fbo=gl.createFramebuffer();this.textures.push(texture);this.fbos.push(fbo);gl.bindTexture(gl.TEXTURE_2D,texture);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,internal===gl.RGBA16F?gl.LINEAR:gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,internal===gl.RGBA16F?gl.LINEAR:gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texImage2D(gl.TEXTURE_2D,0,internal,g.width,g.height,0,internal===gl.R32F?gl.RED:internal===gl.RG32F?gl.RG:gl.RGBA,internal===gl.RGBA16F?gl.HALF_FLOAT:gl.FLOAT,null);gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,texture,0);gl.drawBuffers([gl.COLOR_ATTACHMENT0]);if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('Fine flow target unavailable');return {texture,fbo,width:g.width,height:g.height};}
  transportTarget(fuelHeat,soot){const gl=this.gl,fbo=gl.createFramebuffer();this.fbos.push(fbo);gl.bindFramebuffer(gl.FRAMEBUFFER,fbo);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,fuelHeat.texture,0);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT1,gl.TEXTURE_2D,soot.texture,0);const attachments=[gl.COLOR_ATTACHMENT0,gl.COLOR_ATTACHMENT1];gl.drawBuffers(attachments);if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('Hancock MRT target unavailable');return {texture:fuelHeat.texture,fuelHeat:fuelHeat.texture,soot:soot.texture,fbo,width:fuelHeat.width,height:fuelHeat.height,attachments};}
  location(program,name){let locations=this.locations.get(program);if(!locations){locations=new Map();this.locations.set(program,locations);}if(!locations.has(name))locations.set(name,this.gl.getUniformLocation(program,name));return locations.get(name);}
  program(source){const gl=this.gl,p=gl.createProgram();this.programs.push(p);for(const [type,text]of [[gl.VERTEX_SHADER,VERTEX],[gl.FRAGMENT_SHADER,source.startsWith('#version')?source:'#version 300 es\n'+source]]){const s=gl.createShader(type);this.shaders.push(s);gl.shaderSource(s,text);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));gl.attachShader(p,s);}gl.linkProgram(p);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));return p;}
  draw(p,target,inputs={},uniforms={}){const gl=this.gl;gl.bindVertexArray(this.vao);gl.useProgram(p);gl.bindFramebuffer(gl.FRAMEBUFFER,target.fbo);gl.drawBuffers(target.attachments||[gl.COLOR_ATTACHMENT0]);gl.viewport(0,0,target.width,target.height);let unit=0;for(const [name,texture]of Object.entries(inputs)){const location=this.location(p,name);if(location===null)continue;gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,texture);gl.uniform1i(location,unit++);}for(const [name,value]of Object.entries(uniforms))gl.uniform1f(this.location(p,name),value);gl.drawArrays(gl.TRIANGLES,0,3);}
  clear(target){const gl=this.gl;gl.bindFramebuffer(gl.FRAMEBUFFER,target.fbo);gl.clearBufferfv(gl.COLOR,0,new Float32Array(4));}
  smooth(l,count){for(let j=0;j<count;j++){const next=1-l.current;this.draw(l.smooth,l.p[next],{uP:l.p[l.current].texture,uRhs:l.rhs.texture});l.current=next;}}
  cycle(i){const l=this.levels[i];if(i===this.levels.length-1){this.smooth(l,48);return;}this.smooth(l,2);this.draw(l.residualProgram,l.residual,{uP:l.p[l.current].texture,uRhs:l.rhs.texture});const child=this.levels[i+1];this.draw(child.restrict,child.rhs,{uFine:l.residual.texture});child.current=0;this.clear(child.p[0]);this.cycle(i+1);const next=1-l.current;this.draw(l.prolong,l.p[next],{uP:l.p[l.current].texture,uCoarse:child.p[child.current].texture});l.current=next;this.smooth(l,2);}
  reduceTexture(texture,{alreadyFirst=false,maximum=false,targets=this.reduceTargets}={}){for(const target of targets.slice(alreadyFirst?1:0)){this.draw(maximum?this.reduceMaxProgram:this.reduceProgram,target,{uInput:texture});texture=target.texture;}return targets.at(-1);}
  readReduction(target){const gl=this.gl,out=new Float32Array(4);gl.bindFramebuffer(gl.READ_FRAMEBUFFER,target.fbo);gl.readBuffer(gl.COLOR_ATTACHMENT0);gl.readPixels(0,0,1,1,gl.RGBA,gl.FLOAT,out);return Array.from(out);}
  reduce(texture,options={}){return this.readReduction(this.reduceTexture(texture,options));}
  project(vf,chem,coarse,delta=1/30){const start=performance.now(),l=this.levels[0],scratch=this.reduceTargets[0],inputs={uVf:vf,uChem:chem,pressureCorrectionTex:coarse,uProjected:this.projected.texture,uRhs:l.rhs.texture},warmStart=this.warmValid,probeZero=warmStart||!this.lastProjection||this.lastProjection.cycles===0;this.invalidateMaterialLedger();this.warmValid=false;l.current=0;if(warmStart)this.draw(this.pressureCopyProgram,l.p[0],{uInput:this.warmPressure.texture});else this.clear(l.p[0]);this.draw(this.rhsProgram,l.rhs,inputs);let metrics,midpoint,midpointCycle=-1,cycles=0,centerPre,midpointPre,decision,extraStart=null;const history=[];
   const accepted=m=>OriginalFineFlow.projectionScore(m)<=1;let upperReady=false;
   const measureCenter=()=>{this.draw(this.applyProgram,this.projected,{...inputs,uP:l.p[l.current].texture});if(!upperReady){this.prepareUpperBoundary(vf,chem);upperReady=true;}this.copyUpperBoundary();this.draw(this.metricsProgram,scratch,inputs,{uReusePre:centerPre?1:0});const m=this.reduce(scratch.texture,{alreadyFirst:true});if(centerPre){m[0]=centerPre[0];m[2]=centerPre[1];}else centerPre=[m[0],m[2]];return m;};
   const measureMidpoint=()=>{this.draw(this.midpointProgram,scratch,inputs,{uDelta:delta,uReusePre:midpointPre?1:0});const m=this.reduce(scratch.texture,{alreadyFirst:true});if(midpointPre){m[0]=midpointPre[0];m[2]=midpointPre[1];}else midpointPre=[m[0],m[2]];midpointCycle=cycles;return m;};
   let warmFallback=false;if(probeZero){metrics=measureCenter();if(warmStart&&(!Number.isFinite(metrics[1])||metrics[1]>metrics[0])){this.clear(l.p[0]);metrics=measureCenter();warmFallback=true;}if(accepted(metrics))midpoint=measureMidpoint();}
   if(!metrics||!accepted(metrics)||!midpoint||!accepted(midpoint))for(;;){const correctionStart=performance.now();this.cycle(0);cycles++;metrics=measureCenter();if(accepted(metrics)||cycles>=4)midpoint=measureMidpoint();else midpoint=null;history.push({cycles,centerScore:OriginalFineFlow.projectionScore(metrics),midpointScore:midpoint?OriginalFineFlow.projectionScore(midpoint):null,wallMs:performance.now()-correctionStart});decision=OriginalFineFlow.correctionDecision(history,extraStart===null?0:performance.now()-extraStart);if(decision.action!=='correct')break;if(cycles===4)extraStart=performance.now();}
   if(midpointCycle!==cycles)midpoint=measureMidpoint();
   let finite=[...metrics,...midpoint].every(Number.isFinite),converged=finite&&accepted(metrics)&&accepted(midpoint),axisRates=null;
   if(converged){this.draw(this.rateProgram,scratch,{uProjected:this.projected.texture});axisRates=this.reduce(scratch.texture,{alreadyFirst:true,maximum:true}).slice(0,3);finite=axisRates.every(Number.isFinite);converged=finite;}
   if(converged&&(cycles>0||warmStart)){if(!this.warmPressure)this.warmPressure=this.target(l,this.gl.R32F);this.draw(this.pressureCopyProgram,this.warmPressure,{uInput:l.p[l.current].texture});this.warmValid=true;}
   this.lastProjection={sourceVF:vf,sourceChem:chem,coarseCorrection:coarse,rhs:l.rhs.texture,pressure:l.p[l.current].texture,storageLive:converged,output:this.projected.texture,cycles,history,decision:decision||{action:'accept',reason:'zero-cycle measured acceptance'},warmStart,warmFallback,warmPressureBytes:this.warmPressure?l.width*l.height*4:0,extraCycles:Math.max(0,cycles-4),extraWallMs:extraStart===null?0:performance.now()-extraStart,normalCycleBudget:4,maximumCycles:6,extraAdmissionBudgetMs:48,preMetricsReused:true,midpointReconstruction:'shared normal-face velocity and analytic divergence; exact cell-source law',rho:metrics[1]/Math.max(metrics[0],1e-6),eta:metrics[1]/Math.max(metrics[2],1e-6),midpointRho:midpoint[1]/Math.max(midpoint[0],1e-6),midpointEta:midpoint[1]/Math.max(midpoint[2],1e-6),converged,finite,rhoTolerance:.2,etaTolerance:.1,preL1:metrics[0],postL1:metrics[1],midpointPreL1:midpoint[0],midpointPostL1:midpoint[1],midpointQ:midpoint[2],axisRates,synchronizedWallMs:performance.now()-start,scope:'Unchanged center and midpoint targets. Midpoint evaluates the analytic normal-face field actually used for intensive scalar forward/reverse backtrace, with the solved cell-source representation and unchanged sample support. Prior pressure is an initial guess only. Conditional residual work and serial readback architecture are unchanged. Rejected storage remains diagnostic.'};
   if(!converged){const error=new Error(finite?'Fine projection rejected: center or midpoint tolerance unmet':'Nonfinite fine projection metric');error.projection=this.lastProjection;throw error;}return this.projected.texture;
  }
  prepareTransport(delta){if(!this.lastProjection?.converged||!this.lastProjection.storageLive)throw Error('Transport requires a new converged projection storage boundary');return OriginalFineFlow.schedule(delta,this.lastProjection.axisRates);}
  invalidateMaterialLedger(){if(this.materialLedgerState)this.materialLedgerState.valid=false;}
  discardCandidateHistory(){this.warmValid=false;this.invalidateMaterialLedger();}
  resetProjectionHistory(){this.discardCandidateHistory();this.lastProjection=null;}
  enableMaterialLedger(enabled=true){
   this.materialLedgerEnabled=!!enabled;if(!enabled){this.invalidateMaterialLedger();return;}
   if(this.materialLedgerState)return;
   const gl=this.gl,[nx,ny,nz]=this.grid,blocks=Math.ceil(Math.max(nx,ny)/4),targets=[];let width=blocks*2,height=Math.ceil(Math.max(ny,nz)/4);
   for(;;){targets.push(this.target({width,height},gl.RGBA32F));if(width===1&&height===1)break;width=Math.ceil(width/4);height=Math.ceil(height/4);}
   const transport=this.materialTransportGLSL;
   const boundary=this.program(transport+`uniform float uDelta,uAxis;void main(){
    ivec2 pixel=ivec2(gl_FragCoord.xy);int side=pixel.x/${blocks};ivec2 base=ivec2(pixel.x%${blocks},pixel.y)*4;
    int axis=int(uAxis);ivec3 e=ivec3(axis==0?1:0,axis==1?1:0,axis==2?1:0);result=vec4(0);
    for(int y=0;y<4;y++)for(int x=0;x<4;x++){ivec2 uv=base+ivec2(x,y);ivec3 c=axis==0?ivec3(side==0?0:N.x-1,uv.x,uv.y):axis==1?ivec3(uv.x,side==0?0:N.y-1,uv.y):ivec3(uv.x,uv.y,side==0?0:N.z-1);
     if(!valid(c))continue;float area=H.x*H.y*H.z/H[axis];if(axis!=2&&(c.z==0||c.z==N.z-1))area*=.5;
     vec3 amount=flux(side==0?c:c+e,e,axis,uDelta)*((side==0?-1.:1.)*uDelta*area);
     result.xyz+=amount;result.a=max(result.a,float(any(isnan(amount))||any(isinf(amount))));
    }
   }`);
   const inventory=this.program(this.materialFusedGLSL(transport+`vec4 metric(ivec3 c){if(!valid(c))return vec4(0);vec3 value=q(c);float volume=H.x*H.y*H.z*((c.z==0||c.z==N.z-1)?.5:1.);return vec4(value*volume,float(any(isnan(value))||any(isinf(value))));}`));
   const add=this.program(`#version 300 es
    precision highp float;precision highp int;precision highp sampler2D;uniform sampler2D uA,uB;layout(location=0)out vec4 result;
    void main(){vec4 a=texelFetch(uA,ivec2(0),0),b=texelFetch(uB,ivec2(0),0);result=vec4(a.xyz+b.xyz,max(a.a,b.a));}`);
   const small=()=>this.target({width:1,height:1},gl.RGBA32F);
   this.materialLedgerState={targets,boundary,inventory,add,totals:[small(),small()],before:small(),after:small(),current:0,valid:false,sequence:0,drawPasses:0};
  }
  captureMaterialInventory(state,destination){const ledger=this.materialLedgerState,scratch=this.reduceTargets[0];this.draw(ledger.inventory,scratch,{uQ:state.fuelHeat,uS:state.soot});const total=this.reduceTexture(scratch.texture,{alreadyFirst:true});this.clear(ledger.totals[1-ledger.current]);this.draw(ledger.add,destination,{uA:total.texture,uB:ledger.totals[1-ledger.current].texture});ledger.drawPasses+=this.reduceTargets.length+1;}
  accumulateMaterialBoundary(state,vf,sweep){const ledger=this.materialLedgerState;this.draw(ledger.boundary,ledger.targets[0],{uQ:state.fuelHeat,uS:state.soot,uVf:vf},{uDelta:sweep.delta,uAxis:sweep.axis});const reduced=this.reduceTexture(ledger.targets[0].texture,{alreadyFirst:true,targets:ledger.targets}),next=1-ledger.current;this.draw(ledger.add,ledger.totals[next],{uA:ledger.totals[ledger.current].texture,uB:reduced.texture});ledger.current=next;ledger.drawPasses+=ledger.targets.length+1;}
  readMaterialLedger(){
   const ledger=this.materialLedgerState;if(!ledger?.valid||!this.lastProjection?.converged||this.lastProjection.storageLive)return {available:false,scope:'No completed audited transport at the current projection boundary.'};
   const gl=this.gl,saved=gl.getParameter(gl.READ_FRAMEBUFFER_BINDING);try{
    const before=this.readReduction(ledger.before),after=this.readReduction(ledger.after),boundary=this.readReduction(ledger.totals[ledger.current]),closure=after.slice(0,3).map((value,i)=>value+boundary[i]-before[i]);
    return {available:true,sequence:ledger.sequence,before:before.slice(0,3),after:after.slice(0,3),outwardBoundaryFlux:boundary.slice(0,3),closure,relativeClosure:closure.map((value,i)=>value/Math.max(Math.abs(before[i]),1e-30)),finite:[...before,...after,...boundary].every(Number.isFinite)&&before[3]===0&&after[3]===0&&boundary[3]===0,drawPasses:ledger.drawPasses,substeps:this.lastTransport.substeps,channels:['fuel','heatProxy=(1+F)T','soot'],scope:'One actual conservative transport only. Normalized physical-volume inventory plus signed outward flux from every directional substep, using identical pre-sweep states and production Hancock faces, including endpoint half-depth and the floor. Excludes diffusion, oxygen, reaction and source stages. GPU totals are read only on explicit request.'};
   }finally{gl.bindFramebuffer(gl.READ_FRAMEBUFFER,saved);}
  }
  transport(vf,chem,delta){const start=performance.now(),schedule=this.prepareTransport(delta);this.lastProjection.storageLive=false;this.lastProjection.rhs=null;this.lastProjection.pressure=null;
   this.draw(this.seedProgram,this.states[0],{uChem:chem});let current=0;const ledger=this.materialLedgerEnabled?this.materialLedgerState:null;
   if(ledger){ledger.valid=false;ledger.current=0;ledger.sequence++;ledger.drawPasses=0;this.clear(ledger.totals[0]);this.captureMaterialInventory(this.states[0],ledger.before);}
   for(const sweep of schedule)for(let j=0;j<sweep.steps;j++){const next=1-current,state=this.states[current];if(ledger)this.accumulateMaterialBoundary(state,vf,sweep);this.draw(this.fluxProgram,this.states[next],{uQ:state.fuelHeat,uS:state.soot,uVf:vf},{uDelta:sweep.delta,uAxis:sweep.axis});current=next;}
   const state=this.states[current],conserved={fuelHeat:state.fuelHeat,soot:state.soot};if(ledger){this.captureMaterialInventory(state,ledger.after);ledger.valid=true;}this.lastTransport={sourceChem:chem,sourceVF:vf,conserved,packed:null,schedule,substeps:schedule.reduce((sum,s)=>sum+s.steps,0),delta,maximumOutgoingCFL:Math.max(...schedule.map(s=>s.CFL)),submissionWallMs:performance.now()-start,materialLedger:ledger?{sequence:ledger.sequence,drawPasses:ledger.drawPasses,scope:'Optional signed boundary-accounted conservative-transport ledger; explicit read only.'}:null,inventoryChannels:['fuel','heatProxy=(1+F)T','soot'],oxygen:'Existing intensive predictor/corrector; packing merged into its half-float target',noConcentrationCeiling:true};return conserved;
  }
  dispose(){const gl=this.gl;for(const f of this.fbos)gl.deleteFramebuffer(f);for(const t of this.textures)gl.deleteTexture(t);for(const p of this.programs)gl.deleteProgram(p);for(const s of this.shaders)gl.deleteShader(s);if(this.vao)gl.deleteVertexArray(this.vao);this.fbos=[];this.textures=[];this.programs=[];this.shaders=[];this.vao=null;}
 }
 window.OriginalFineFlow=OriginalFineFlow;
})();
