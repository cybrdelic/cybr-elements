/** Deterministic BVH dielectric optics for the Three.js surface pass.
 * Traverses the ACTUAL liquid/solid/droplet triangles and spheres. Refraction,
 * reflection, nested water/glass/bubble IOR transitions and Beer absorption
 * use ray-hit distances. It is NOT an unbiased path tracer: paths are bounded
 * and offscreen opaque lighting uses a studio irradiance approximation.
 */
(function(){'use strict';const T=THREE;
const FRAGMENT=`out vec4 opticsColor;
#define gl_FragColor opticsColor
precision highp float;precision highp int;precision highp sampler2D;
uniform sampler2D tNodes,tPrimitives,tMaterials,tScene,tDepth;
uniform ivec2 uNodeSize,uPrimitiveSize;uniform vec2 uResolution;
uniform mat4 uViewProjection;uniform float uIOR,uEpsilon,uNear,uFar,uScale,uDiagnostic;
uniform vec3 uAbsorption,uBackground;uniform vec4 uFloor;
varying vec3 vWorld,vNormalW,vView;varying float vFoam;
${window.CYBR_ENVIRONMENT_GLSL}
${window.CYBR_BVH_TRACE.replace('visit<4096','visit<768')}
float dielectric(float c,float ei,float et){float st=ei/et*sqrt(max(0.,1.-c*c));if(st>=1.)return 1.;float ct=sqrt(max(0.,1.-st*st));float rs=(ei*c-et*ct)/(ei*c+et*ct),rp=(et*c-ei*ct)/(et*c+ei*ct);return .5*(rs*rs+rp*rp);}
float ior(ivec3 layers,float glass){return layers.y>0?glass:(layers.z>0?1.:(layers.x>0?uIOR:1.));}
vec3 attenuation(ivec3 layers){return layers.y>0?vec3(.015,.006,.003):(layers.z>0?vec3(0.):layers.x>0?uAbsorption:vec3(0.));}
float zLinear(float d){return uNear*uFar/(uFar-d*(uFar-uNear));}
vec3 opaque(Hit hit,vec3 point,vec3 direction){
 vec4 clip=uViewProjection*vec4(point,1.);vec2 uv=clip.xy/clip.w*.5+.5;
 if(clip.w>0.&&all(greaterThan(uv,vec2(.002)))&&all(lessThan(uv,vec2(.998)))){
  float z=-(viewMatrix*vec4(point,1.)).z,visible=zLinear(texture(tDepth,uv).r);
  if(abs(visible-z)<.018*uScale)return texture(tScene,uv).rgb;
 }
 vec3 color=texelFetch(tMaterials,ivec2(hit.material,0),0).rgb,n=dot(hit.n,direction)>0.?-hit.n:hit.n;
 if(hit.material==254){float checker=mod(floor(point.x/uFloor.x*9.6)+floor(point.z/uFloor.z*6.4),2.);color=mix(vec3(.41,.45,.42),vec3(.56,.59,.54),checker);}
 if(hit.material==255)color=uBackground;
 vec3 illumination=vec3(.36,.41,.44)+vec3(.55,.57,.57)*max(0.,dot(n,normalize(vec3(-1.,7.,4.))));
 return color*illumination;
}
vec3 opticalBranch(vec3 ro,vec3 rd,ivec3 layers,out float lengthInWater){
 vec3 result=vec3(0.),weight=vec3(1.);float glass=1.5;lengthInWater=0.;
 for(int bounce=0;bounce<10;bounce++){
  Hit hit;if(!trace(ro,rd,hit)){result+=weight*environment(rd);return result;}
  weight*=exp(-attenuation(layers)*hit.t);if(layers.x>0&&layers.y==0&&layers.z==0)lengthInWater+=hit.t;
  vec3 point=ro+rd*hit.t;float glassIOR=texelFetch(tMaterials,ivec2(hit.material,0),0).a;
  if(hit.material!=0&&hit.material!=2&&glassIOR<1.)return result+weight*opaque(hit,point,rd);
  vec3 n=dot(hit.n,rd)>0.?-hit.n:hit.n;bool front=dot(hit.geometric,rd)<0.;ivec3 next=layers;
  if(hit.material==0)next.x=max(0,next.x+(front?1:-1));else if(hit.material==2)next.z=max(0,next.z+(front?1:-1));else{next.y=max(0,next.y+(front?1:-1));glass=glassIOR;}
  float ei=ior(layers,glass),et=ior(next,glass),F=dielectric(clamp(-dot(n,rd),0.,1.),ei,et);
  vec3 transmitted=refract(rd,n,ei/et),reflected=reflect(rd,n);
  if(dot(transmitted,transmitted)<.01){rd=reflected;ro=point+rd*uEpsilon*5.;continue;}
  // Secondary Fresnel reflection uses the studio environment; the primary
  // reflected and transmitted branches still intersect the complete BVH.
  result+=weight*F*environment(reflected);weight*=1.-F;layers=next;
  rd=normalize(transmitted);ro=point+rd*uEpsilon*5.;
  if(max(weight.r,max(weight.g,weight.b))<.002)return result;
 }
 return result+weight*environment(rd);
}
void main(){
 vec3 V=normalize(cameraPosition-vWorld),N=normalize(vNormalW);bool inside=!gl_FrontFacing;if(dot(N,V)<0.)N=-N;
 float ei=inside?uIOR:1.,et=inside?1.:uIOR,F=dielectric(clamp(dot(N,V),0.,1.),ei,et),d0,d1;
 vec3 reflected=reflect(-V,N),transmitted=refract(-V,N,ei/et),col;
 vec3 reflection=opticalBranch(vWorld+reflected*uEpsilon*5.,reflected,ivec3(inside?1:0,0,0),d0);
 if(dot(transmitted,transmitted)<.01){col=reflection;d1=0.;}
 else col=F*reflection+(1.-F)*opticalBranch(vWorld+transmitted*uEpsilon*5.,transmitted,ivec3(inside?0:1,0,0),d1);
 col=mix(col,vec3(.82,.855,.85)*(.62+.38*max(N.y,0.)),clamp(vFoam,0.,.97)*.90);
 if(uDiagnostic>.5)col=mix(vec3(.015,.03,.06),vec3(.98,.61,.14),clamp(d1/(2.*uScale),0.,1.));
 gl_FragColor=vec4(col,1.);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`;
class GeometryOptics{
 constructor(liquid){this.liquid=liquid;this.reference=new ReferencePathTracer(liquid);this.material=null;this.builtFor=null;}
 build(){const l=this.liquid;if(this.builtFor===l.latest)return this.stats;const stats=this.reference.build(),u=this.reference.uniforms,r=l.material.uniforms;
  if(!this.material){this.material=new T.ShaderMaterial({glslVersion:T.GLSL3,vertexShader:window.CYBR_WATER_VERTEX,fragmentShader:FRAGMENT,uniforms:{
   tNodes:u.tNodes,tPrimitives:u.tPrimitives,tMaterials:u.tMaterials,uNodeSize:u.uNodeSize,uPrimitiveSize:u.uPrimitiveSize,uIOR:r.uIOR,uEpsilon:u.uEpsilon,uAbsorption:r.uAbsorption,uBackground:u.uBackground,uFloor:u.uFloor,
   tScene:r.tScene,tDepth:r.tDepth,uResolution:r.uResolution,uViewProjection:r.uViewProjection,uNear:r.uNear,uFar:r.uFar,uScale:r.uScale,uDiagnostic:r.uDiagnostic},side:T.DoubleSide});}
  this.builtFor=l.latest;this.stats={primitiveCount:stats.primitiveCount,nodeCount:stats.nodeCount,buildMilliseconds:stats.buildMilliseconds,optics:'actual BVH dielectric paths; 10-interface primary rays; secondary environment reflection; opaque irradiance approximate'};return this.stats;
 }
 enable(){this.build();this.liquid.water.material=this.material;return this.stats;}
 dispose(){this.material?.dispose();this.reference.dispose();}
}
window.GeometryOptics=GeometryOptics;
})();
