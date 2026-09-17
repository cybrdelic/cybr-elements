/*
 * CYBR FLIP III — sparse WebGL2 compute backend.
 *
 * A sparse brick atlas stores the MAC grid. Particle-to-grid transfers use
 * actual floating-point GPU blending; field operators, PCG reductions,
 * viscosity and particle updates are fragment/vertex programs. The host
 * compacts a SMALL coarse brick-activation map. It never solves pressure or
 * advances particle velocities on the CPU.
 *
 * This backend deliberately shares the existing Three.js WebGL2 context.
 * Call endCompute() before returning control to Three.js. It requires
 * EXT_color_buffer_float and EXT_float_blend. No browser security changes,
 * network dependencies, WebGPU shims, or emulated JavaScript GPU kernels.
 */
(function(global){
'use strict';
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const nextPow2=x=>2**Math.ceil(Math.log2(Math.max(1,x)));
const PREFIX=`#version 300 es
precision highp float;
precision highp int;
precision highp sampler2D;
`;
const QUAD=`${PREFIX}
void main(){vec2 p=vec2((gl_VertexID==1)?3.:-1.,(gl_VertexID==2)?3.:-1.);gl_Position=vec4(p,0.,1.);}`;
const COMMON=`
uniform sampler2D uMap,uBlocks,uPosition,uParticleVelocity,uA0,uA1,uA2;
uniform sampler2D uGrid,uValid,uOldGrid,uPhi,uMask,uCoeff,uRhs;
uniform sampler2D uState,uDirection,uAd,uScalar,uScalarOld,uInput,uInput2,uForce;
uniform ivec3 uGridSize,uBlockDims;
uniform ivec2 uMapSize,uListSize,uAtlasSize,uParticleSize,uReduceSize;
uniform int uBlockCount,uAtlasColumns,uCount,uOldCount,uSolidCount,uScene,uPass;
uniform float uH,uDt,uTime,uRho,uSigma,uNu,uFlip,uTolerance,uReferenceNorm2;
uniform vec3 uExtent,uGravity;
uniform vec4 uSolidCenter[16],uSolidSize[16],uSolidVelocity[16];
uniform bool uAffine;
ivec2 flatPixel(int id,ivec2 size){return ivec2(id%size.x,id/size.x);}
vec4 particle(sampler2D s,int id){return texelFetch(s,flatPixel(id,uParticleSize),0);}
bool inGrid(ivec3 g){return all(greaterThanEqual(g,ivec3(0)))&&all(lessThanEqual(g,uGridSize));}
int brickId(ivec3 g){
 if(!inGrid(g))return -1;
 ivec3 b=g/8;int index=b.x+uBlockDims.x*(b.y+uBlockDims.y*b.z);
 return int(texelFetch(uMap,flatPixel(index,uMapSize),0).r+.5)-1;
}
ivec2 gridPixel(ivec3 g){
 int b=brickId(g);if(b<0)return ivec2(-1);
 ivec3 q=g-(g/8)*8;
 return ivec2((b%uAtlasColumns)*64+q.x+8*q.y,(b/uAtlasColumns)*8+q.z);
}
ivec3 worldCell(ivec2 p){
 int b=p.x/64+uAtlasColumns*(p.y/8);if(b>=uBlockCount)return ivec3(-999);
 ivec3 origin=ivec3(texelFetch(uBlocks,flatPixel(b,uListSize),0).xyz+.5)*8;
 int x=p.x%64;return origin+ivec3(x%8,x/8,p.y%8);
}
vec4 grid(sampler2D s,ivec3 g){ivec2 q=gridPixel(g);return q.x<0?vec4(0.):texelFetch(s,q,0);}
float phiAt(ivec3 g){ivec2 q=gridPixel(g);return q.x<0?3.*uH:texelFetch(uPhi,q,0).r;}
float smoothPhi(ivec3 g){ivec2 q=gridPixel(g);return q.x<0?3.*uH:texelFetch(uPhi,q,0).g;}
bool solidPosition(vec3 p,float margin){
 if(any(lessThan(p,vec3(uH+margin)))||any(greaterThan(p,uExtent-vec3(uH+margin))))return true;
 for(int i=0;i<16;i++){if(i>=uSolidCount)break;vec3 q=p-uSolidCenter[i].xyz;
  if(uSolidCenter[i].w>.5){if(length(q)<uSolidSize[i].x+margin)return true;}
  else if(all(lessThan(abs(q),uSolidSize[i].xyz+margin)))return true;
 }return false;
}
int kind(ivec3 g){
 if(!inGrid(g)||solidPosition((vec3(g)+.5)*uH,0.))return 2;
 return grid(uMask,g).r>.5?1:0;
}
vec3 wallVelocity(vec3 p){
 for(int i=0;i<16;i++){if(i>=uSolidCount)break;vec3 q=p-uSolidCenter[i].xyz;
  bool close=uSolidCenter[i].w>.5?length(q)<uSolidSize[i].x+uH:all(lessThan(abs(q),uSolidSize[i].xyz+uH));
  if(close)return uSolidVelocity[i].xyz;
 }return vec3(0.);
}
ivec3 axis(int c){return c==0?ivec3(1,0,0):c==1?ivec3(0,1,0):ivec3(0,0,1);}
vec3 facePosition(ivec3 g,int c){return (vec3(g)+.5-.5*vec3(axis(c)))*uH;}
float theta(ivec3 liquid,ivec3 air){float a=min(-.08*uH,phiAt(liquid)),b=max(.08*uH,phiAt(air));return clamp(-a/(b-a),.08,1.);}
float capillary(ivec3 g){return uSigma*grid(uPhi,g).b;}
float component(sampler2D s,int c,vec3 p){
 vec3 f=p/uH-.5+.5*vec3(axis(c));ivec3 b=clamp(ivec3(floor(f)),ivec3(0),uGridSize-1);f=clamp(f-vec3(b),0.,1.);
 float result=0.;for(int i=0;i<8;i++){ivec3 d=ivec3(i&1,(i>>1)&1,(i>>2)&1);vec3 w=mix(1.-f,f,vec3(d));result+=w.x*w.y*w.z*grid(s,b+d)[c];}return result;
}
vec3 velocity(sampler2D s,vec3 p){return vec3(component(s,0,p),component(s,1,p),component(s,2,p));}
vec3 gradientComponent(sampler2D s,int c,vec3 p){
 vec3 f=p/uH-.5+.5*vec3(axis(c));ivec3 b=clamp(ivec3(floor(f)),ivec3(0),uGridSize-1);f=clamp(f-vec3(b),0.,1.);vec3 v=vec3(0.);
 for(int i=0;i<8;i++){ivec3 d=ivec3(i&1,(i>>1)&1,(i>>2)&1);vec3 w=mix(1.-f,f,vec3(d)),signs=2.*vec3(d)-1.;float s=grid(s,b+d)[c];v+=s*vec3(signs.x*w.y*w.z,signs.y*w.x*w.z,signs.z*w.x*w.y);}
 return v/uH;
}

void collideParticle(inout vec3 p,inout vec3 v){
 float margin=.12*uH;
 for(int c=0;c<3;c++){float lo=uH+margin,hi=uExtent[c]-uH-margin;if(p[c]<lo){p[c]=lo;v[c]=max(0.,v[c]);}if(p[c]>hi){p[c]=hi;v[c]=min(0.,v[c]);}}
 for(int i=0;i<16;i++){if(i>=uSolidCount)break;vec3 q=p-uSolidCenter[i].xyz,n=vec3(0.);bool hit=false;
  if(uSolidCenter[i].w>.5){float radius=uSolidSize[i].x+margin,d=length(q);if(d<radius){n=d>1e-8?q/d:vec3(0.,1.,0.);p=uSolidCenter[i].xyz+n*radius;hit=true;}}
  else{vec3 depth=uSolidSize[i].xyz+margin-abs(q);if(all(greaterThan(depth,vec3(0.)))){int c=depth.x<depth.y?(depth.x<depth.z?0:2):(depth.y<depth.z?1:2);n[c]=q[c]<0.?-1.:1.;p[c]=uSolidCenter[i][c]+n[c]*(uSolidSize[i][c]+margin);hit=true;}}
  if(hit){float vn=dot(v-uSolidVelocity[i].xyz,n);if(vn<0.)v-=vn*n;}}
}

float divergence(ivec3 g){return (grid(uGrid,g+ivec3(1,0,0)).x-grid(uGrid,g).x+grid(uGrid,g+ivec3(0,1,0)).y-grid(uGrid,g).y+grid(uGrid,g+ivec3(0,0,1)).z-grid(uGrid,g).z)/uH;}
`;
const fragment=(body,outputs=1)=>PREFIX+COMMON+Array.from({length:outputs},(_,i)=>`layout(location=${i}) out vec4 out${i};`).join('\n')+'\n'+body;
const shaders={};
shaders.activate={vertex:PREFIX+COMMON+`
void main(){int id=gl_VertexID/8,corner=gl_VertexID%8;vec3 p=particle(uPosition,id).xyz;
 ivec3 g=ivec3(floor(p/uH))+ivec3((corner&1)==0?-3:3,(corner&2)==0?-3:3,(corner&4)==0?-3:3);
 if(!inGrid(g)){gl_Position=vec4(2.,2.,2.,1.);return;}
 ivec3 b=g/8;int n=b.x+uBlockDims.x*(b.y+uBlockDims.y*b.z);ivec2 px=flatPixel(n,uMapSize);
 gl_Position=vec4((vec2(px)+.5)/vec2(uMapSize)*2.-1.,0.,1.);gl_PointSize=1.;}
`,fragment:PREFIX+'layout(location=0) out vec4 out0;void main(){out0=vec4(1.);}'};
shaders.mask={vertex:PREFIX+COMMON+`
void main(){vec3 p=particle(uPosition,gl_VertexID).xyz;ivec2 px=gridPixel(ivec3(floor(p/uH)));if(px.x<0){gl_Position=vec4(2.,2.,2.,1.);return;}gl_Position=vec4((vec2(px)+.5)/vec2(uAtlasSize)*2.-1.,0.,1.);gl_PointSize=1.;}
`,fragment:PREFIX+'layout(location=0) out vec4 out0;void main(){out0=vec4(1.);}'};
shaders.splat={vertex:PREFIX+COMMON+`
out vec3 vSum;out vec3 vWeight;
void main(){int id=gl_VertexID/24,c=(gl_VertexID/8)%3,i=gl_VertexID%8;vec3 p=particle(uPosition,id).xyz;
 vec3 f=p/uH-.5+.5*vec3(axis(c));ivec3 b=clamp(ivec3(floor(f)),ivec3(0),uGridSize-1);f=clamp(f-vec3(b),0.,1.);ivec3 d=ivec3(i&1,(i>>1)&1,(i>>2)&1);ivec2 px=gridPixel(b+d);
 if(px.x<0){gl_Position=vec4(2.,2.,2.,1.);vSum=vWeight=vec3(0.);return;}
 vec3 w=mix(1.-f,f,vec3(d));float mass=w.x*w.y*w.z;vec3 A=c==0?particle(uA0,id).xyz:c==1?particle(uA1,id).xyz:particle(uA2,id).xyz;
 float v=particle(uParticleVelocity,id)[c]+(uAffine?dot(A,uH*(vec3(d)-f)):0.);vSum=vec3(axis(c))*mass*v;vWeight=vec3(axis(c))*mass;
 gl_Position=vec4((vec2(px)+.5)/vec2(uAtlasSize)*2.-1.,0.,1.);gl_PointSize=1.;}
`,fragment:PREFIX+'in vec3 vSum;in vec3 vWeight;layout(location=0) out vec4 out0;layout(location=1) out vec4 out1;void main(){out0=vec4(vSum,0.);out1=vec4(vWeight,0.);}'};
shaders.sdf={vertex:PREFIX+COMMON+`
out float vDistance;
void main(){int id=gl_VertexID/27,n=gl_VertexID%27;vec3 p=particle(uPosition,id).xyz;ivec3 b=ivec3(floor(p/uH)),d=ivec3(n%3,(n/3)%3,n/9)-1;ivec3 g=b+d;ivec2 px=gridPixel(g);
 if(px.x<0){gl_Position=vec4(2.,2.,2.,1.);vDistance=3.*uH;return;}vDistance=length((vec3(g)+.5)*uH-p)-.80*uH;gl_Position=vec4((vec2(px)+.5)/vec2(uAtlasSize)*2.-1.,0.,1.);gl_PointSize=1.;}
`,fragment:PREFIX+'in float vDistance;layout(location=0) out vec4 out0;void main(){out0=vec4(vDistance,vDistance,0.,0.);}'};
shaders.copy={fragment:fragment('void main(){out0=texelFetch(uInput,ivec2(gl_FragCoord.xy),0);}')};
shaders.normalize={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);out0=out1=vec4(0.);if(!inGrid(g))return;
 vec3 mass=texelFetch(uInput2,px,0).xyz,v=texelFetch(uInput,px,0).xyz/max(mass,vec3(1e-12)),valid=vec3(greaterThan(mass,vec3(1e-8)));
 for(int c=0;c<3;c++)if(kind(g)==2||kind(g-axis(c))==2){v[c]=wallVelocity(facePosition(g,c))[c];valid[c]=1.;}
 out0=vec4(v,0.);out1=vec4(valid,float(kind(g)));}
`,2)};
shaders.extend={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);out0=out1=vec4(0.);if(!inGrid(g))return;vec3 v=texelFetch(uGrid,px,0).xyz,valid=texelFetch(uValid,px,0).xyz;
 for(int c=0;c<3;c++)if(valid[c]<.5){float sum=0.,weight=0.;for(int a=0;a<3;a++)for(int s=-1;s<=1;s+=2){ivec3 n=g+axis(a)*s;float w=grid(uValid,n)[c];sum+=w*grid(uGrid,n)[c];weight+=w;}if(weight>.5){v[c]=sum/weight;valid[c]=1.;}}
 out0=vec4(v,0.);out1=vec4(valid,float(kind(g)));}
`,2)};
shaders.smoothPhi={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);if(!inGrid(g)){out0=vec4(3.*uH,3.*uH,0.,0.);return;}float raw=phiAt(g),value=uPass==0?raw:smoothPhi(g),sum=.4*value;
 for(int c=0;c<3;c++)for(int s=-1;s<=1;s+=2)sum+=.1*(uPass==0?phiAt(g+axis(c)*s):smoothPhi(g+axis(c)*s));out0=vec4(raw,sum,0.,0.);}
`)};
shaders.curvature={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);out0=texelFetch(uPhi,px,0);if(!inGrid(g)||kind(g)!=1)return;
 float f=smoothPhi(g),h=uH,hh=h*h;vec3 d=vec3(0.),dd=vec3(0.);
 for(int c=0;c<3;c++){float a=smoothPhi(g+axis(c)),b=smoothPhi(g-axis(c));d[c]=(a-b)/(2.*h);dd[c]=(a-2.*f+b)/hh;}
 float xy=(smoothPhi(g+ivec3(1,1,0))-smoothPhi(g+ivec3(1,-1,0))-smoothPhi(g+ivec3(-1,1,0))+smoothPhi(g+ivec3(-1,-1,0)))/(4.*hh);
 float xz=(smoothPhi(g+ivec3(1,0,1))-smoothPhi(g+ivec3(1,0,-1))-smoothPhi(g+ivec3(-1,0,1))+smoothPhi(g+ivec3(-1,0,-1)))/(4.*hh);
 float yz=(smoothPhi(g+ivec3(0,1,1))-smoothPhi(g+ivec3(0,1,-1))-smoothPhi(g+ivec3(0,-1,1))+smoothPhi(g+ivec3(0,-1,-1)))/(4.*hh);
 float g2=dot(d,d),k=g2>1e-8?((d.y*d.y+d.z*d.z)*dd.x+(d.x*d.x+d.z*d.z)*dd.y+(d.x*d.x+d.y*d.y)*dd.z-2.*(d.x*d.y*xy+d.x*d.z*xz+d.y*d.z*yz))/pow(g2,1.5):0.;out0.b=clamp(k,-1.5/h,1.5/h);}
`)};
shaders.forces={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);out0=out1=vec4(0.);if(!inGrid(g))return;vec3 v=texelFetch(uGrid,px,0).xyz,valid=texelFetch(uValid,px,0).xyz;
 for(int c=0;c<3;c++){if(kind(g)==2||kind(g-axis(c))==2){v[c]=wallVelocity(facePosition(g,c))[c];valid[c]=1.;continue;}if(valid[c]<.5)continue;v[c]+=uGravity[c]*uDt;
  if(uScene==1){vec3 p=facePosition(g,c);vec2 d=p.xz-uExtent.xz*.5;float a=1.1*exp(-dot(d,d)/1.5);vec3 f=vec3(a*d.y,0.,-a*d.x);v[c]+=f[c]*uDt;}}
 out0=vec4(v,0.);out1=vec4(valid,float(kind(g)));}
`,2)};
shaders.viscosity={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);out0=out1=vec4(0.);if(!inGrid(g))return;vec3 v=texelFetch(uGrid,px,0).xyz,valid=texelFetch(uValid,px,0).xyz;float a=uNu*uDt/(uH*uH);
 for(int c=0;c<3;c++){if(kind(g)==2||kind(g-axis(c))==2){v[c]=wallVelocity(facePosition(g,c))[c];continue;}if(kind(g)!=1&&kind(g-axis(c))!=1)continue;float sum=texelFetch(uForce,px,0)[c],den=1.;
  for(int d=0;d<3;d++)for(int s=-1;s<=1;s+=2){ivec3 n=g+axis(d)*s;int r=kind(n),l=kind(n-axis(c));if(r==2||l==2){sum+=a*wallVelocity(facePosition(n,c))[c];den+=a;}else if(r==1||l==1){sum+=a*grid(uGrid,n)[c];den+=a;}}
  v[c]=sum/den;}out0=vec4(v,0.);out1=vec4(valid,float(kind(g)));}
`,2)};
shaders.matrix={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);out0=out1=vec4(0.);if(!inGrid(g)||kind(g)!=1)return;
 float diagonal=0.,rhs=-uRho*uH*uH/uDt*divergence(g);vec3 plus=vec3(0.),minus=vec3(0.);
 for(int c=0;c<3;c++)for(int s=-1;s<=1;s+=2){ivec3 n=g+axis(c)*s;int k=kind(n);if(k==2)continue;float w=k==1?1.:1./theta(g,n);diagonal+=w;if(k==1){if(s==1)plus[c]=w;else minus[c]=w;}else rhs+=w*capillary(g);}
 out0=vec4(plus,max(diagonal,1e-12));out1=vec4(minus,rhs);}
`,2)};
shaders.pcgInit={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);float diagonal=texelFetch(uCoeff,p,0).a,b=texelFetch(uRhs,p,0).a,z=diagonal>1e-10?b/diagonal:0.;out0=vec4(0.,b,z,0.);out1=vec4(z,0.,0.,0.);}
`,2)};
shaders.matvec={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(p);vec4 a=texelFetch(uCoeff,p,0),b=texelFetch(uRhs,p,0);float d=texelFetch(uDirection,p,0).r,Ad=a.a*d;
 for(int c=0;c<3;c++)Ad-=a[c]*grid(uDirection,g+axis(c)).r+b[c]*grid(uDirection,g-axis(c)).r;out0=vec4(Ad,d*Ad,0.,0.);}
`)};
shaders.pcgUpdate={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);vec4 state=texelFetch(uState,p,0),rho=texelFetch(uScalarOld,ivec2(0),0);float den=texelFetch(uScalar,ivec2(0),0).r;
 float alpha=(rho.g>uTolerance*uTolerance*uReferenceNorm2&&den>1e-30)?rho.r/den:0.;
 float r=state.g-alpha*texelFetch(uAd,p,0).r,diagonal=texelFetch(uCoeff,p,0).a,z=diagonal>1e-10?r/diagonal:0.;out0=vec4(state.r+alpha*texelFetch(uDirection,p,0).r,r,z,0.);}
`)};
shaders.pcgDirection={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);float previous=texelFetch(uScalarOld,ivec2(0),0).r,next=texelFetch(uScalar,ivec2(0),0).r;float beta=previous>1e-30?next/previous:0.;out0=vec4(texelFetch(uState,p,0).b+beta*texelFetch(uDirection,p,0).r,0.,0.,0.);}
`)};
shaders.dotState={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);vec4 s=texelFetch(uState,p,0);float b=texelFetch(uRhs,p,0).a;out0=vec4(s.g*s.b,s.g*s.g,b*b,texelFetch(uCoeff,p,0).a>1e-10?1.:0.);}
`)};
shaders.dotAd={fragment:fragment('void main(){out0=vec4(texelFetch(uAd,ivec2(gl_FragCoord.xy),0).g,0.,0.,0.);}')};
shaders.reduce={fragment:fragment(`
void main(){ivec2 b=ivec2(gl_FragCoord.xy)*2;out0=vec4(0.);for(int y=0;y<2;y++)for(int x=0;x<2;x++){ivec2 p=b+ivec2(x,y);if(all(lessThan(p,uReduceSize)))out0+=texelFetch(uInput,p,0);}}
`)};
shaders.project={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(px);out0=out1=vec4(0.);if(!inGrid(g))return;vec3 v=texelFetch(uGrid,px,0).xyz,valid=texelFetch(uValid,px,0).xyz;int r=kind(g);
 for(int c=0;c<3;c++){ivec3 left=g-axis(c);int l=kind(left);if(r==2||l==2){v[c]=wallVelocity(facePosition(g,c))[c];valid[c]=1.;continue;}if(l!=1&&r!=1)continue;
  float pL=l==1?grid(uState,left).r:capillary(g),pR=r==1?grid(uState,g).r:capillary(left),fraction=l==1&&r==1?1.:l==1?theta(left,g):theta(g,left);
  v[c]-=uDt/(uRho*uH*fraction)*(pR-pL);valid[c]=1.;}out0=vec4(v,0.);out1=vec4(valid,float(r));}
`,2)};
shaders.divergence={fragment:fragment(`
void main(){ivec3 g=worldCell(ivec2(gl_FragCoord.xy));float d=inGrid(g)&&kind(g)==1?divergence(g):0.;out0=vec4(d*d,inGrid(g)&&kind(g)==1?1.:0.,abs(d),0.);}
`)};
shaders.advect={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);int id=px.x+uParticleSize.x*px.y;out0=out1=out2=out3=out4=vec4(0.);if(id>=uCount)return;
 vec3 p=texelFetch(uPosition,px,0).xyz,v=texelFetch(uParticleVelocity,px,0).xyz,pic=velocity(uGrid,p),old=velocity(uOldGrid,p);
 v=mix(pic,v+pic-old,uFlip);vec3 A0=gradientComponent(uGrid,0,p),A1=gradientComponent(uGrid,1,p),A2=gradientComponent(uGrid,2,p);
 vec3 midpoint=p+.5*uDt*pic;p+=uDt*velocity(uGrid,midpoint);collideParticle(p,v);
 out0=vec4(p,1.);out1=vec4(v,1.);out2=vec4(A0,0.);out3=vec4(A1,0.);out4=vec4(A2,0.);}
`,5)};

shaders.collide={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);int id=p.x+uParticleSize.x*p.y;out0=out1=out2=out3=out4=vec4(0.);if(id>=uCount)return;
 vec3 x=texelFetch(uPosition,p,0).xyz,v=texelFetch(uParticleVelocity,p,0).xyz;collideParticle(x,v);
 out0=vec4(x,1.);out1=vec4(v,1.);out2=texelFetch(uA0,p,0);out3=texelFetch(uA1,p,0);out4=texelFetch(uA2,p,0);}
`,5)};
shaders.grow={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);out0=out1=out2=out3=out4=vec4(0.);if(any(greaterThanEqual(p,uReduceSize)))return;
 out0=texelFetch(uPosition,p,0);out1=texelFetch(uParticleVelocity,p,0);out2=texelFetch(uA0,p,0);out3=texelFetch(uA1,p,0);out4=texelFetch(uA2,p,0);}
`,5)};
shaders.trueResidual={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(p);vec4 a=texelFetch(uCoeff,p,0),b=texelFetch(uRhs,p,0);float pressure=texelFetch(uState,p,0).r,Ap=a.a*pressure;
 for(int c=0;c<3;c++)Ap-=a[c]*grid(uState,g+axis(c)).r+b[c]*grid(uState,g-axis(c)).r;
 float r=b.a-Ap;out0=vec4(r*r,b.a*b.a,0.,0.);}
`)};

// Reliable residual replacement: keep p, recompute r=b-Ap, and restart d=M^-1 r.
// This prevents a small recursive FP32 residual from falsely satisfying the target.
shaders.pcgRestart={fragment:fragment(`
void main(){ivec2 p=ivec2(gl_FragCoord.xy);ivec3 g=worldCell(p);vec4 a=texelFetch(uCoeff,p,0),b=texelFetch(uRhs,p,0);float pressure=texelFetch(uState,p,0).r,Ap=a.a*pressure;
 for(int c=0;c<3;c++)Ap-=a[c]*grid(uState,g+axis(c)).r+b[c]*grid(uState,g-axis(c)).r;
 float residual=b.a-Ap,z=a.a>1e-10?residual/a.a:0.;out0=vec4(pressure,residual,z,0.);out1=vec4(z,0.,0.,0.);}
`,2)};

// Reduction of particle safety/CFL metadata: only 16 bytes leave the GPU.
shaders.particleStats={fragment:fragment(`
void main(){ivec2 px=ivec2(gl_FragCoord.xy);int id=px.x+px.y*uParticleSize.x;out0=vec4(0.);if(id>=uCount)return;
 vec3 p=particle(uPosition,id).xyz,v=particle(uParticleVelocity,id).xyz;
 bool invalid=any(isnan(p))||any(isinf(p))||any(isnan(v))||any(isinf(v));
 out0=vec4(invalid?0.:dot(v,v),invalid?1.:0.,solidPosition(p,-uH*.001)?1.:0.,1.);}`)};
shaders.reduceStats={fragment:fragment(`
void main(){ivec2 b=ivec2(gl_FragCoord.xy)*2;out0=vec4(0.);for(int y=0;y<2;y++)for(int x=0;x<2;x++){
 ivec2 p=b+ivec2(x,y);if(any(greaterThanEqual(p,uReduceSize)))continue;vec4 v=texelFetch(uInput,p,0);out0.x=max(out0.x,v.x);out0.yzw+=v.yzw;}}`)};
class SparseGPUFLIP{
 constructor(threeRenderer,config,positions,velocities,options={}){
  if(!threeRenderer?.getContext)throw Error('A Three.js WebGLRenderer is required.');
  this.renderer=threeRenderer;this.gl=threeRenderer.getContext();const gl=this.gl;
  if(!(gl instanceof WebGL2RenderingContext))throw Error('Sparse FLIP requires WebGL2.');
  if(!gl.getExtension('EXT_color_buffer_float')||!gl.getExtension('EXT_float_blend'))throw Error('Sparse GPU FLIP requires float render targets and float blending.');
  if(gl.getParameter(gl.MAX_DRAW_BUFFERS)<5)throw Error('At least five float render attachments are required.');
  this.config=structuredClone(config);this.h=config.h;this.count=positions.length/3;this.initialCount=this.count;this.spawned=0;this.time=0;this.steps=0;
  if(!Number.isInteger(this.count)||velocities.length!==positions.length)throw Error('Invalid primary particle arrays.');
  this.options={pressureTolerance:1e-4,pressureIterations:192,atlasColumns:0,...options};this.atlasColumns=1;this.randomState=(options.randomState??config.seed??7)>>>0;this.emitCarry=options.emitCarry??0;
  this.config.pressureTolerance=options.pressureTolerance??config.pressureTolerance??1e-4;
  this.programs={};this.targets=new Set();this.textures=new Set();this.passCount=0;this.primaryReadbackBytes=0;this.telemetryReadbackBytes=0;this.statsTargets=[];this.lastPressure=null;this.lastMetrics=null;
  if((config.obstacles??[]).length>16)throw Error('The GPU backend supports at most 16 analytic colliders.');
  this.motionBase=(config.obstacles??[]).map(o=>o.center.slice());this.obstacles=structuredClone(config.obstacles??[]);
  this.gridSize=[config.nx,config.ny,config.nz];this.blockDims=this.gridSize.map(n=>Math.ceil((n+1)/8));this.coarseCount=this.blockDims.reduce((a,b)=>a*b,1);
  this.mapSize=[Math.min(128,nextPow2(this.coarseCount)),Math.ceil(this.coarseCount/Math.min(128,nextPow2(this.coarseCount)))];
  this.mapArray=new Float32Array(this.mapSize[0]*this.mapSize[1]*4);this.coarsePixels=new Float32Array(this.mapArray.length);
  this.activation=this.target(...this.mapSize);this.mapTexture=this.texture(...this.mapSize,this.mapArray);
  this.listSize=[128,Math.max(1,Math.ceil(this.coarseCount/128))];this.blockArray=new Float32Array(this.listSize[0]*this.listSize[1]*4);this.blockTexture=this.texture(...this.listSize,this.blockArray);
  this.particleCapacity=Math.max(1024,nextPow2(this.count));this.particleSize=[Math.min(1024,this.particleCapacity),Math.ceil(this.particleCapacity/Math.min(1024,this.particleCapacity))];
  this.particles=[this.target(...this.particleSize,5),this.target(...this.particleSize,5)];this.particlePing=0;
  this.uploadParticles(positions,velocities);this.gridCapacity=0;this.blockCount=0;this.reduction=[];this.vao=gl.createVertexArray();
  this.scalarOld=this.target(1,1);this.scalarNew=this.target(1,1);this.scalarDen=this.target(1,1);this.scalarDiv=this.target(1,1);
  this.maxSpeed=0;for(let i=0;i<velocities.length;i+=3)this.maxSpeed=Math.max(this.maxSpeed,Math.hypot(...velocities.subarray(i,i+3)));
  this.capabilities={backend:'sparse WebGL2 GPU compute',floatBlend:true,floatTargets:true,maxTextureSize:gl.getParameter(gl.MAX_TEXTURE_SIZE),brickSize:[8,8,8],coarseActivationCompaction:'CPU readback of coarse flags only',primarySolver:'GPU floating-blend P2G, sparse MAC operators, GPU PCG, GPU G2P/RK2'};
  this.endCompute();
 }
 texture(w,h,data=null){const gl=this.gl,t=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,t);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA32F,w,h,0,gl.RGBA,gl.FLOAT,data);this.textures.add(t);return {texture:t,width:w,height:h};}
 target(w,h,count=1){const gl=this.gl,t={width:w,height:h,fbo:gl.createFramebuffer(),textures:[]};gl.bindFramebuffer(gl.FRAMEBUFFER,t.fbo);for(let i=0;i<count;i++){const tx=this.texture(w,h);t.textures.push(tx);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0+i,gl.TEXTURE_2D,tx.texture,0);}gl.drawBuffers(t.textures.map((_,i)=>gl.COLOR_ATTACHMENT0+i));if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error(`Incomplete float framebuffer ${w}x${h}/${count}`);this.targets.add(t);return t;}
 releaseTarget(t){if(!t)return;const gl=this.gl;for(const x of t.textures){gl.deleteTexture(x.texture);this.textures.delete(x.texture);}gl.deleteFramebuffer(t.fbo);this.targets.delete(t);}
 upload(tx,data){const gl=this.gl;gl.bindTexture(gl.TEXTURE_2D,tx.texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);gl.texSubImage2D(gl.TEXTURE_2D,0,0,0,tx.width,tx.height,gl.RGBA,gl.FLOAT,data);}
 uploadParticles(p,v,affine=null){const n=this.particleSize[0]*this.particleSize[1],data=Array.from({length:5},()=>new Float32Array(n*4));for(let i=0;i<p.length/3;i++){data[0].set(p.subarray(i*3,i*3+3),i*4);data[0][i*4+3]=1;data[1].set(v.subarray(i*3,i*3+3),i*4);data[1][i*4+3]=1;if(affine)for(let c=0;c<3;c++)data[c+2].set(affine.subarray(i*9+c*3,i*9+c*3+3),i*4);}for(let i=0;i<5;i++)this.upload(this.particles[this.particlePing].textures[i],data[i]);}
 beginCompute(){const gl=this.gl;this.renderer.resetState();gl.bindVertexArray(this.vao);gl.disable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);gl.disable(gl.SCISSOR_TEST);gl.disable(gl.STENCIL_TEST);gl.disable(gl.BLEND);gl.colorMask(true,true,true,true);gl.depthMask(false);}
 endCompute(){const gl=this.gl;gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.bindVertexArray(null);gl.useProgram(null);gl.disable(gl.BLEND);this.renderer.resetState();}
 program(name){if(this.programs[name])return this.programs[name];const gl=this.gl,s=shaders[name];if(!s)throw Error('Unknown GPU stage: '+name);const build=(type,source)=>{const sh=gl.createShader(type);gl.shaderSource(sh,source);gl.compileShader(sh);if(!gl.getShaderParameter(sh,gl.COMPILE_STATUS))throw Error(name+': '+gl.getShaderInfoLog(sh)+'\n'+source);return sh;};const vs=build(gl.VERTEX_SHADER,s.vertex??QUAD),fs=build(gl.FRAGMENT_SHADER,s.fragment),p=gl.createProgram();gl.attachShader(p,vs);gl.attachShader(p,fs);gl.linkProgram(p);gl.deleteShader(vs);gl.deleteShader(fs);if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(name+': '+gl.getProgramInfoLog(p));const uniforms={};for(let i=0;i<gl.getProgramParameter(p,gl.ACTIVE_UNIFORMS);i++){const u=gl.getActiveUniform(p,i);uniforms[u.name.replace(/\[0\]$/,'')]={type:u.type,location:gl.getUniformLocation(p,u.name),size:u.size};}return this.programs[name]={program:p,uniforms};}
 uniforms(){const p=this.particles[this.particlePing],c=this.config;return {uMap:this.mapTexture,uBlocks:this.blockTexture,uPosition:p.textures[0],uParticleVelocity:p.textures[1],uA0:p.textures[2],uA1:p.textures[3],uA2:p.textures[4],uGridSize:this.gridSize,uBlockDims:this.blockDims,uMapSize:this.mapSize,uListSize:this.listSize,uAtlasSize:this.atlasSize??[1,1],uParticleSize:this.particleSize,uBlockCount:this.blockCount,uAtlasColumns:this.atlasColumns,uCount:this.count,uOldCount:this.count,uSolidCount:this.obstacles.length,uH:this.h,uDt:this.dt??1/120,uTime:this.time,uRho:c.density??1000,uSigma:c.surfaceTension??0,uNu:c.kinematicViscosity??0,uFlip:c.flip??.93,uTolerance:c.pressureTolerance,uReferenceNorm2:this.referenceNorm2??1,uExtent:c.extent,uGravity:c.gravity??[0,-9.81,0],uAffine:c.affine!==false,uScene:c.nameKey==='vortex'?1:0,uPass:0,...this.solidUniforms()};}
 solidUniforms(){const center=new Float32Array(64),size=new Float32Array(64),velocity=new Float32Array(64);this.obstacles.forEach((o,i)=>{center.set([...o.center,o.kind==='sphere'?1:0],i*4);size.set(o.kind==='sphere'?[o.radius,o.radius,o.radius,0]:[...o.half,0],i*4);velocity.set([...(o.velocity??[0,0,0]),0],i*4);});return {uSolidCenter:center,uSolidSize:size,uSolidVelocity:velocity};}
 bindUniforms(program,extra){const gl=this.gl,values={...this.uniforms(),...extra};let unit=0;for(const [name,u] of Object.entries(program.uniforms)){const v=values[name];if(v===undefined)throw Error('Missing GPU uniform '+name);const loc=u.location;switch(u.type){case gl.SAMPLER_2D:gl.activeTexture(gl.TEXTURE0+unit);gl.bindTexture(gl.TEXTURE_2D,v.texture);gl.uniform1i(loc,unit++);break;case gl.INT:case gl.BOOL:gl.uniform1i(loc,v);break;case gl.INT_VEC2:gl.uniform2iv(loc,v);break;case gl.INT_VEC3:gl.uniform3iv(loc,v);break;case gl.FLOAT:gl.uniform1f(loc,v);break;case gl.FLOAT_VEC2:gl.uniform2fv(loc,v);break;case gl.FLOAT_VEC3:gl.uniform3fv(loc,v);break;case gl.FLOAT_VEC4:gl.uniform4fv(loc,v);break;default:throw Error('Unsupported uniform '+name+' '+u.type);}}}
 draw(name,target,extra={},count=3,blend=null){const gl=this.gl,p=this.program(name);gl.bindFramebuffer(gl.FRAMEBUFFER,target.fbo);gl.drawBuffers(target.textures.map((_,i)=>gl.COLOR_ATTACHMENT0+i));gl.viewport(0,0,target.width,target.height);gl.useProgram(p.program);this.bindUniforms(p,extra);if(blend!==null){gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE);gl.blendEquation(blend);}else gl.disable(gl.BLEND);gl.drawArrays(shaders[name].vertex?gl.POINTS:gl.TRIANGLES,0,count);this.passCount++;}
 clear(target,value=[0,0,0,0]){const gl=this.gl;gl.bindFramebuffer(gl.FRAMEBUFFER,target.fbo);gl.drawBuffers(target.textures.map((_,i)=>gl.COLOR_ATTACHMENT0+i));for(let i=0;i<target.textures.length;i++)gl.clearBufferfv(gl.COLOR,i,value);}
 read(target,index=0,out=null){const bytes=target.width*target.height*16;if(this.particles?.includes(target))this.primaryReadbackBytes+=bytes;else this.telemetryReadbackBytes+=bytes;const gl=this.gl;gl.bindFramebuffer(gl.FRAMEBUFFER,target.fbo);gl.readBuffer(gl.COLOR_ATTACHMENT0+index);const a=out??new Float32Array(target.width*target.height*4);gl.readPixels(0,0,target.width,target.height,gl.RGBA,gl.FLOAT,a);return a;}
 allocateGrid(blocks){const capacity=blocks<=8?8:Math.ceil(blocks/16)*16;if(capacity<=this.gridCapacity)return;for(const name of ['splat','mask','fieldA','fieldB','fieldC','oldA','oldB','oldC','gridA','gridB','force','matrix','pcgInitTarget','pcgRestartTarget','stateA','stateB','directionA','directionB','Ad','dot'])this.releaseTarget(this[name]);for(const t of this.reduction)this.releaseTarget(t);this.reduction=[];this.gridCapacity=capacity;this.atlasColumns=this.options.atlasColumns||Math.max(1,nextPow2(Math.sqrt(capacity/8)));this.atlasSize=[64*this.atlasColumns,8*Math.ceil(capacity/this.atlasColumns)];const [w,h]=this.atlasSize;if(Math.max(w,h)>this.gl.getParameter(this.gl.MAX_TEXTURE_SIZE))throw Error('Sparse atlas exceeds the GPU texture limit.');for(const name of ['splat','oldA','oldB','oldC','gridA','gridB','force','matrix','pcgInitTarget','pcgRestartTarget'])this[name]=this.target(w,h,2);for(const name of ['mask','fieldA','fieldB','fieldC','stateA','stateB','directionA','directionB','Ad','dot'])this[name]=this.target(w,h);let rw=w,rh=h;while(rw>1||rh>1){rw=Math.ceil(rw/2);rh=Math.ceil(rh/2);this.reduction.push(this.target(rw,rh));}}
 activate(){const gl=this.gl;this.clear(this.activation);this.draw('activate',this.activation,{},this.count*8,gl.MAX);this.read(this.activation,0,this.coarsePixels);this.mapArray.fill(0);this.blockArray.fill(0);let n=0;for(let i=0;i<this.coarseCount;i++)if(this.coarsePixels[i*4]>.5){this.mapArray[i*4]=n+1;const x=i%this.blockDims[0],y=Math.floor(i/this.blockDims[0])%this.blockDims[1],z=Math.floor(i/(this.blockDims[0]*this.blockDims[1]));this.blockArray.set([x,y,z,1],n*4);n++;}if(!n)throw Error('No active sparse bricks.');this.blockCount=n;this.allocateGrid(n);this.upload(this.mapTexture,this.mapArray);this.upload(this.blockTexture,this.blockArray);}
 commonFields(){return {uMask:this.mask.textures[0],uPhi:this.field.textures[0]};}
 transfer(){const gl=this.gl;this.clear(this.mask);this.draw('mask',this.mask,{},this.count,gl.MAX);this.clear(this.splat);this.draw('splat',this.splat,{},this.count*24,gl.FUNC_ADD);const fields={uMask:this.mask.textures[0]};this.draw('normalize',this.oldA,{...fields,uInput:this.splat.textures[0],uInput2:this.splat.textures[1]});this.draw('extend',this.oldB,{...fields,uGrid:this.oldA.textures[0],uValid:this.oldA.textures[1]});this.draw('extend',this.oldC,{...fields,uGrid:this.oldB.textures[0],uValid:this.oldB.textures[1]});this.old=this.oldC;}
 levelSet(){const gl=this.gl;this.clear(this.fieldA,[3*this.h,3*this.h,0,0]);this.draw('sdf',this.fieldA,{},this.count*27,gl.MIN);const mask={uMask:this.mask.textures[0]};this.draw('smoothPhi',this.fieldB,{...mask,uPhi:this.fieldA.textures[0],uPass:0});this.draw('smoothPhi',this.fieldC,{...mask,uPhi:this.fieldB.textures[0],uPass:1});this.draw('curvature',this.fieldA,{...mask,uPhi:this.fieldC.textures[0]});this.field=this.fieldA;}
 reduce(input,destination){
  let texture=input,w=input.width,h=input.height;
  for(let i=0;i<this.reduction.length;i++){
   // Write the final scalar directly. A separate scalar copy forces another
   // draw and framebuffer switch for every PCG dot product.
   const target=i===this.reduction.length-1?destination:this.reduction[i];
   this.draw('reduce',target,{uInput:texture,uReduceSize:[w,h]});
   texture=target.textures[0];w=target.width;h=target.height;
  }
  if(!this.reduction.length)this.draw('copy',destination,{uInput:texture});
 }
 externalForces(){this.draw('forces',this.force,{...this.commonFields(),uGrid:this.old.textures[0],uValid:this.old.textures[1]});this.current=this.force;const nu=this.config.kinematicViscosity??0;if(nu<=0){this.viscosityIterations=0;return;}const alpha=nu*this.dt/(this.h*this.h),iterations=Math.min(160,Math.max(16,Math.ceil(16+24*alpha)));for(let i=0;i<iterations;i++){const dst=i%2?this.gridB:this.gridA;this.draw('viscosity',dst,{...this.commonFields(),uGrid:this.current.textures[0],uValid:this.current.textures[1],uForce:this.force.textures[0]});this.current=dst;}this.viscosityIterations=iterations;}
 divergenceStats(){this.draw('divergence',this.dot,{...this.commonFields(),uGrid:this.current.textures[0]});this.reduce(this.dot.textures[0],this.scalarDiv);const v=this.read(this.scalarDiv);return {rms:Math.sqrt(Math.max(0,v[0])/Math.max(1,v[1])),count:v[1],meanAbsolute:v[2]/Math.max(1,v[1])};}
 pressure(){
  const fields={...this.commonFields(),uGrid:this.current.textures[0]};this.draw('matrix',this.matrix,fields);
  const matrix={...this.commonFields(),uCoeff:this.matrix.textures[0],uRhs:this.matrix.textures[1]};
  this.draw('pcgInit',this.pcgInitTarget,matrix);let state=this.pcgInitTarget.textures[0],direction=this.pcgInitTarget.textures[1];
  this.draw('dotState',this.dot,{...matrix,uState:state});this.reduce(this.dot.textures[0],this.scalarOld);
  let rho=this.read(this.scalarOld),initial=rho[2];this.referenceNorm2=initial;
  let iterations=0,restarts=0,relative=initial>0?1:0,trueRelative=relative,converged=false;
  const budget=this.options.pressureIterations,target=this.config.pressureTolerance;
  for(;;){
   let recursiveConverged=relative<=target;
   while(iterations<budget&&!recursiveConverged){
    this.draw('matvec',this.Ad,{...matrix,uDirection:direction});this.draw('dotAd',this.dot,{uAd:this.Ad.textures[0]});this.reduce(this.dot.textures[0],this.scalarDen);
    const nextState=state===this.stateA.textures[0]?this.stateB:this.stateA;
    this.draw('pcgUpdate',nextState,{...matrix,uState:state,uDirection:direction,uAd:this.Ad.textures[0],uScalarOld:this.scalarOld.textures[0],uScalar:this.scalarDen.textures[0]});state=nextState.textures[0];
    this.draw('dotState',this.dot,{...matrix,uState:state});this.reduce(this.dot.textures[0],this.scalarNew);
    const nextDirection=direction===this.directionA.textures[0]?this.directionB:this.directionA;
    this.draw('pcgDirection',nextDirection,{uState:state,uDirection:direction,uScalarOld:this.scalarOld.textures[0],uScalar:this.scalarNew.textures[0]});direction=nextDirection.textures[0];
    [this.scalarOld,this.scalarNew]=[this.scalarNew,this.scalarOld];iterations++;
    if(iterations%8===0||iterations===budget){rho=this.read(this.scalarOld);relative=Math.sqrt(Math.max(0,rho[1])/Math.max(1e-30,initial));recursiveConverged=relative<=target;if(!Number.isFinite(relative))throw Error('Nonfinite sparse GPU pressure residual.');}
   }
   this.draw('trueResidual',this.dot,{...matrix,uState:state});this.reduce(this.dot.textures[0],this.scalarDen);
   const explicit=this.read(this.scalarDen);trueRelative=Math.sqrt(Math.max(0,explicit[0])/Math.max(1e-30,explicit[1]));
   if(!Number.isFinite(trueRelative))throw Error('Nonfinite explicit GPU pressure residual.');
   converged=trueRelative<=target;
   if(converged||iterations>=budget||restarts>=3)break;
   const replacement=state===this.pcgRestartTarget.textures[0]?this.pcgInitTarget:this.pcgRestartTarget;
   this.draw('pcgRestart',replacement,{...matrix,uState:state});state=replacement.textures[0];direction=replacement.textures[1];
   this.draw('dotState',this.dot,{...matrix,uState:state});this.reduce(this.dot.textures[0],this.scalarOld);
   rho=this.read(this.scalarOld);relative=Math.sqrt(Math.max(0,rho[1])/Math.max(1e-30,initial));restarts++;
  }
  this.pressureState=state;this.lastPressure={method:'GPU Jacobi-preconditioned conjugate gradient',iterations,residualReplacements:restarts,relativeResidual:trueRelative,recursiveRelativeResidual:relative,target,converged,initialResidualNorm:Math.sqrt(initial)};
  const dst=this.current===this.gridA?this.gridB:this.gridA;this.draw('project',dst,{...matrix,uState:state,uGrid:this.current.textures[0],uValid:this.current.textures[1]});this.current=dst;return this.lastPressure;
 }

 extendProjected(){for(let i=0;i<2;i++){const dst=this.current===this.gridA?this.gridB:this.gridA;this.draw('extend',dst,{...this.commonFields(),uGrid:this.current.textures[0],uValid:this.current.textures[1]});this.current=dst;}}
 random(){let x=this.randomState;x^=x<<13;x^=x>>>17;x^=x<<5;this.randomState=x>>>0;return this.randomState/4294967296;}
 appendParticles(positions,velocities){
  const add=positions.length/3;if(!Number.isInteger(add)||velocities.length!==positions.length)throw Error('Invalid emitter arrays.');if(!add)return;
  if(this.count+add>(this.config.maxParticles??800000))throw Error('Sparse GPU primary-particle capacity exceeded.');
  if(this.count+add>this.particleCapacity){const old=this.particles,oldSize=this.particleSize.slice(),capacity=nextPow2(this.count+add);this.particleCapacity=capacity;this.particleSize=[1024,Math.ceil(capacity/1024)];const next=[this.target(...this.particleSize,5),this.target(...this.particleSize,5)];this.draw('grow',next[0],{uReduceSize:oldSize});this.particles=next;this.particlePing=0;for(const t of old)this.releaseTarget(t);}
  const gl=this.gl,target=this.particles[this.particlePing];let offset=0;
  while(offset<add){const id=this.count+offset,x=id%this.particleSize[0],y=Math.floor(id/this.particleSize[0]),n=Math.min(add-offset,this.particleSize[0]-x),data=Array.from({length:5},()=>new Float32Array(n*4));
   for(let i=0;i<n;i++){for(let c=0;c<3;c++){const p=positions[(offset+i)*3+c],v=velocities[(offset+i)*3+c];if(!Number.isFinite(p)||!Number.isFinite(v))throw Error('Nonfinite emitter state.');data[0][i*4+c]=p;data[1][i*4+c]=v;}data[0][i*4+3]=data[1][i*4+3]=1;}
   for(let c=0;c<5;c++){gl.bindTexture(gl.TEXTURE_2D,target.textures[c].texture);gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL,false);gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,false);gl.texSubImage2D(gl.TEXTURE_2D,0,x,y,n,1,gl.RGBA,gl.FLOAT,data[c]);}offset+=n;
  }this.count+=add;this.spawned+=add;
 }
 emit(dt){
  const key=this.config.nameKey;if(!['jets','cascade','viscous'].includes(key))return;const p=[],v=[],s=this.h*.5;
  const add=(x,y,z,vx,vy,vz)=>{if(!this.insideSolid(x,y,z,this.h*.12)){p.push(x,y,z);v.push(vx,vy,vz);}};
  if(key==='jets'){const radius=.215,speed=4.3;this.emitCarry+=Math.PI*radius*radius*speed*dt/(s*s*s);const n=Math.floor(this.emitCarry);this.emitCarry-=n;
   for(let e=0;e<2;e++)for(let i=0;i<n;i++){const a=this.random()*2*Math.PI,r=radius*Math.sqrt(this.random());add(e?4.43-this.random()*speed*dt:.37+this.random()*speed*dt,1.35+r*Math.sin(a),1.6+r*Math.cos(a),e?-4.3:4.3,2.5,e?-.1:.1);}
  }else if(key==='cascade'){const speed=1.65;this.emitCarry+=.34*2.25*speed*dt/(s*s*s);const n=Math.floor(this.emitCarry);this.emitCarry-=n;for(let i=0;i<n;i++)add(.24+this.random()*speed*dt,2.12+this.random()*.34,.475+this.random()*2.25,speed,0,0);
  }else{const radius=.067,speed=.72;this.emitCarry+=Math.PI*radius*radius*speed*dt/(s*s*s);const n=Math.floor(this.emitCarry);this.emitCarry-=n;for(let i=0;i<n;i++){const a=this.random()*2*Math.PI,r=radius*Math.sqrt(this.random());add(.8+Math.cos(a)*r+.06*Math.sin(this.time*2),1.035-this.random()*speed*dt,.6+Math.sin(a)*r,.12*Math.cos(this.time*2),-speed,0);}}
  this.appendParticles(new Float32Array(p),new Float32Array(v));
 }
 collideBeforeTransfer(){const next=1-this.particlePing;this.draw('collide',this.particles[next]);this.particlePing=next;}

 updateObstacles(time){this.obstacles.forEach((o,i)=>{o.velocity=[0,0,0];if(o.motion){const m=o.motion,a=m.axis??0,w=2*Math.PI*m.frequency,t=w*time+(m.phase??0);o.center[a]=this.motionBase[i][a]+m.amplitude*Math.sin(t);o.velocity[a]=m.amplitude*w*Math.cos(t);}});}
 step(dt){if(!(dt>0&&dt<=.05))throw Error('Invalid GPU timestep.');const start=performance.now();this.dt=dt;this.beginCompute();try{this.updateObstacles(this.time+dt);this.collideBeforeTransfer();this.emit(dt);this.activate();this.transfer();this.levelSet();this.externalForces();const before=this.divergenceStats();this.pressure();if(!this.lastPressure.converged)throw Error('Sparse GPU pressure target not reached: '+JSON.stringify(this.lastPressure));const after=this.divergenceStats();this.extendProjected();const next=1-this.particlePing;this.draw('advect',this.particles[next],{...this.commonFields(),uGrid:this.current.textures[0],uOldGrid:this.old.textures[0]});this.particlePing=next;this.time+=dt;this.steps++;const error=this.gl.getError();if(error)throw Error('Sparse GPU WebGL error '+error);this.lastMetrics={time:this.time,steps:this.steps,particles:this.count,initialParticles:this.initialCount,spawned:this.spawned,deleted:0,capacityRejected:0,grid:this.gridSize,h:this.h,activeCells:before.count,activeBricks:this.blockCount,allocatedBrickCapacity:this.gridCapacity,allocatedGridTexels:this.atlasSize[0]*this.atlasSize[1],denseGridTexels:this.gridSize.reduce((a,b)=>a*(b+1),1),divergenceBefore:before.rms,divergenceAfter:after.rms,pressure:{...this.lastPressure},viscosityIterations:this.viscosityIterations,colliders:structuredClone(this.obstacles),backend:'sparse WebGL2 GPU compute',gpuPasses:this.passCount,primaryCPUAdvectionSteps:0,dt,wallMs:performance.now()-start};return this.lastMetrics;}finally{this.endCompute();}}
 readState(includeAffine=false,includeGrid=false){this.beginCompute();try{const target=this.particles[this.particlePing],pp=this.read(target,0),vv=this.read(target,1),p=new Float32Array(this.count*3),v=new Float32Array(this.count*3),a=includeAffine?new Float32Array(this.count*9):null;let finite=true,maxSpeed=0,violations=0;for(let i=0;i<this.count;i++){p.set(pp.subarray(i*4,i*4+3),i*3);v.set(vv.subarray(i*4,i*4+3),i*3);for(let c=0;c<3;c++)if(!Number.isFinite(p[i*3+c])||!Number.isFinite(v[i*3+c]))finite=false;maxSpeed=Math.max(maxSpeed,Math.hypot(v[i*3],v[i*3+1],v[i*3+2]));if(this.insideSolid(p[i*3],p[i*3+1],p[i*3+2],-this.h*.001))violations++;}if(a)for(let c=0;c<3;c++){const data=this.read(target,c+2);for(let i=0;i<this.count;i++)a.set(data.subarray(i*4,i*4+3),i*9+c*3);}this.maxSpeed=maxSpeed;const metrics={...this.lastMetrics,finite,maxSpeed,solidViolations:violations,particleVolume:this.count*(this.h*.5)**3};return {positions:p,velocities:v,affine:a,metrics,grid:includeGrid&&this.current?{values:this.read(this.current,0),blocks:this.blockArray.slice(0,this.blockCount*4),atlasSize:this.atlasSize.slice(),atlasColumns:this.atlasColumns}:null};}finally{this.endCompute();}}
 insideSolid(x,y,z,margin=0){const h=this.h,e=this.config.extent;if(x<h+margin||y<h+margin||z<h+margin||x>e[0]-h-margin||y>e[1]-h-margin||z>e[2]-h-margin)return true;for(const o of this.obstacles){if(o.kind==='sphere'&&Math.hypot(x-o.center[0],y-o.center[1],z-o.center[2])<o.radius+margin)return true;if(o.kind==='box'&&Math.abs(x-o.center[0])<o.half[0]+margin&&Math.abs(y-o.center[1])<o.half[1]+margin&&Math.abs(z-o.center[2])<o.half[2]+margin)return true;}return false;}
 particleTelemetry(){this.beginCompute();try{
  const [w,h]=this.particleSize;
  if(!this.statsTargets.length||this.statsTargets[0].width!==w||this.statsTargets[0].height!==h){
   for(const t of this.statsTargets)this.releaseTarget(t);this.statsTargets=[this.target(w,h)];let a=w,b=h;
   while(a>1||b>1){a=Math.ceil(a/2);b=Math.ceil(b/2);this.statsTargets.push(this.target(a,b));}
  }
  this.draw('particleStats',this.statsTargets[0]);
  for(let i=1;i<this.statsTargets.length;i++){const prev=this.statsTargets[i-1];this.draw('reduceStats',this.statsTargets[i],{uInput:prev.textures[0],uReduceSize:[prev.width,prev.height]});}
  const data=this.read(this.statsTargets.at(-1));this.maxSpeed=Math.sqrt(Math.max(0,data[0]));
  this.lastTelemetry={finite:data[1]===0,maxSpeed:this.maxSpeed,solidViolations:data[2],countFromGPU:data[3],particleVolume:this.count*(this.h*.5)**3};return this.lastTelemetry;
 }finally{this.endCompute();}}
 async advance(frameDt=1/48){if(!(frameDt>0&&frameDt<=.25))throw Error('Invalid frame duration.');let remaining=frameDt,substeps=0;const gravity=Math.hypot(...(this.config.gravity??[0,-9.81,0])),sigma=this.config.surfaceTension??0,cap=sigma>0?.4*Math.sqrt((this.config.density??1000)*this.h**3/(Math.PI*sigma)):Infinity;while(remaining>1e-10){const dt=Math.min(remaining,1/90,.45*this.h/Math.max(.1,this.maxSpeed+gravity*remaining),cap);this.step(dt);remaining-=dt;const state=this.particleTelemetry();if(!state.finite||state.solidViolations)throw Error('GPU particle validation failed.');if(++substeps>256)throw Error('GPU CFL budget exceeded.');}return {...this.lastMetrics,...this.lastTelemetry,substeps,primaryReadbackBytes:this.primaryReadbackBytes,telemetryReadbackBytes:this.telemetryReadbackBytes};}
 dispose(){for(const t of [...this.targets])this.releaseTarget(t);for(const t of this.textures)this.gl.deleteTexture(t);this.textures.clear();for(const p of Object.values(this.programs))this.gl.deleteProgram(p.program);this.gl.deleteVertexArray(this.vao);this.endCompute();}
}
global.SparseGPUFLIP=SparseGPUFLIP;
})(globalThis);
