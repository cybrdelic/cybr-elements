/** CYBR FLIP III — progressive dielectric reference integrator.
 * Real triangle/sphere BVH traversal in a Three.js WebGL2 fragment shader.
 * Uses exact Fresnel branch sampling, Beer–Lambert attenuation, next-event
 * environment sampling with an alias table, power-heuristic MIS, diffuse
 * surfaces, Russian roulette and independent pixel/sample random streams.
 * It is deliberately a reference mode: no claim of real-time convergence.
 */
(function(){
'use strict';
const T=THREE;
const VERTEX=`in vec3 position;out vec2 vUV;void main(){vUV=position.xy*.5+.5;gl_Position=vec4(position.xy,0.,1.);}`;
const FRAGMENT=`precision highp float;precision highp int;precision highp sampler2D;
uniform sampler2D tPrevious,tNodes,tPrimitives,tAlias,tMaterials;
uniform ivec2 uNodeSize,uPrimitiveSize;uniform vec2 uResolution;
uniform mat4 uCameraWorld,uInverseProjection;
uniform int uSample,uMaxBounces,uPrimitiveCount;uniform float uIOR,uEpsilon;
uniform vec3 uAbsorption,uBackground;uniform vec4 uFloor;
in vec2 vUV;out vec4 outColor;
${window.CYBR_ENVIRONMENT_GLSL}
const float PI=3.141592653589793;uint seed;
float random(){seed=seed*747796405u+2891336453u;uint word=((seed>>((seed>>28u)+4u))^seed)*277803737u;word=(word>>22u)^word;return (float(word)+.5)/4294967296.;}
vec4 texel(sampler2D t,int index,ivec2 size){return texelFetch(t,ivec2(index%size.x,index/size.x),0);}
float powerHeuristic(float a,float b){return a*a/max(1.e-15,a*a+b*b);}
bool hitBox(vec3 ro,vec3 rd,vec3 lo,vec3 hi,float closest){
 vec3 a=(lo-ro)/rd,b=(hi-ro)/rd;vec3 mn=min(a,b),mx=max(a,b);
 return max(max(mn.x,mn.y),max(mn.z,0.))<=min(min(mx.x,mx.y),min(mx.z,closest));
}
struct Hit{float t;vec3 n;vec3 geometric;float foam;int material;};
bool trace(vec3 ro,vec3 rd,out Hit hit){
 hit.t=1.e20;hit.material=-1;hit.foam=0.;bool found=false;int stack[64];int sp=0;stack[sp++]=0;
 for(int visit=0;visit<4096;visit++){
  if(sp<=0)break;int node=stack[--sp];vec4 a=texel(tNodes,node*2,uNodeSize),b=texel(tNodes,node*2+1,uNodeSize);
  if(!hitBox(ro,rd,a.xyz,b.xyz,hit.t))continue;
  if(a.w>=0.){if(sp<62){stack[sp++]=int(a.w+.5);stack[sp++]=int(b.w+.5);}continue;}
  int first=int(-a.w-.5),count=int(b.w+.5);
  for(int k=0;k<8;k++){
   if(k>=count)break;int q=(first+k)*6;vec4 p0=texel(tPrimitives,q,uPrimitiveSize),p1=texel(tPrimitives,q+1,uPrimitiveSize),p2=texel(tPrimitives,q+2,uPrimitiveSize);
   float distance;vec3 n,gn;float foam=p2.w;
   if(p0.w>0.){
    vec3 oc=ro-p0.xyz;float c=dot(oc,oc)-p0.w*p0.w,bb=dot(oc,rd),disc=bb*bb-c;if(disc<0.)continue;
    float sq=sqrt(disc);distance=-bb-sq;if(distance<uEpsilon)distance=-bb+sq;if(distance<uEpsilon||distance>=hit.t)continue;
    n=normalize(ro+distance*rd-p0.xyz);gn=n;
   }else{
    vec3 e1=p1.xyz-p0.xyz,e2=p2.xyz-p0.xyz,pvec=cross(rd,e2);float det=dot(e1,pvec);if(abs(det)<1.e-12)continue;
    vec3 tvec=ro-p0.xyz;float inv=1./det,u=dot(tvec,pvec)*inv;if(u<0.||u>1.)continue;
    vec3 qvec=cross(tvec,e1);float v=dot(rd,qvec)*inv;if(v<0.||u+v>1.)continue;
    distance=dot(e2,qvec)*inv;if(distance<uEpsilon||distance>=hit.t)continue;
    vec4 n0=texel(tPrimitives,q+3,uPrimitiveSize),n1=texel(tPrimitives,q+4,uPrimitiveSize),n2=texel(tPrimitives,q+5,uPrimitiveSize);
    n=normalize(n0.xyz*(1.-u-v)+n1.xyz*u+n2.xyz*v);gn=normalize(cross(e1,e2));if(dot(n,gn)<0.)n=-n;
    foam=n0.w*(1.-u-v)+n1.w*u+n2.w*v;
   }
   hit.t=distance;hit.n=n;hit.geometric=gn;hit.material=int(p1.w+.5);hit.foam=foam;found=true;
  }
 }
 // Infinite studio floor; the raised tiled plate is part of the triangle BVH.
 if(abs(rd.y)>1.e-8){float d=(uFloor.w-ro.y)/rd.y;if(d>uEpsilon&&d<hit.t){hit.t=d;hit.n=hit.geometric=vec3(0.,1.,0.);hit.material=255;hit.foam=0.;found=true;}}
 return found;
}
float fresnel(float c,float etaI,float etaT){
 float st=etaI/etaT*sqrt(max(0.,1.-c*c));if(st>=1.)return 1.;float ct=sqrt(max(0.,1.-st*st));
 float rs=(etaI*c-etaT*ct)/(etaI*c+etaT*ct),rp=(etaT*c-etaI*ct)/(etaT*c+etaI*ct);return .5*(rs*rs+rp*rp);
}
vec3 cosineDirection(vec3 n){float r=sqrt(random()),a=2.*PI*random();vec3 axis=abs(n.y)<.99?vec3(0.,1.,0.):vec3(1.,0.,0.);vec3 t=normalize(cross(axis,n)),b=cross(n,t);return normalize(t*(r*cos(a))+b*(r*sin(a))+n*sqrt(1.-r*r));}
vec2 environmentUV(vec3 d){float phi=atan(d.z,-d.x);if(phi<0.)phi+=2.*PI;return vec2(phi/(2.*PI),acos(clamp(d.y,-1.,1.))/PI);}
float environmentPdf(vec3 d){vec2 uv=environmentUV(d);ivec2 pixel=clamp(ivec2(uv*vec2(256.,128.)),ivec2(0),ivec2(255,127));float probability=texelFetch(tAlias,pixel,0).z;return probability*32768./(2.*PI*PI*max(1.e-5,sin(uv.y*PI)));}
vec3 sampleEnvironment(out float pdf){
 int i=min(32767,int(random()*32768.));vec4 alias=texelFetch(tAlias,ivec2(i%256,i/256),0);if(random()>alias.x)i=int(alias.y+.5);
 vec2 uv=(vec2(i%256,i/256)+vec2(random(),random()))/vec2(256.,128.);float theta=uv.y*PI,phi=uv.x*2.*PI;
 vec3 d=vec3(-sin(theta)*cos(phi),cos(theta),sin(theta)*sin(phi));pdf=environmentPdf(d);return d;
}
float mediumIOR(ivec3 layers,float glassIOR){return layers.y>0?glassIOR:(layers.z>0?1.:(layers.x>0?uIOR:1.));}
vec3 mediumAbsorption(ivec3 layers){return layers.y>0?vec3(.015,.006,.003):(layers.z>0?vec3(0.):layers.x>0?uAbsorption:vec3(0.));}
vec3 radiance(vec3 ro,vec3 rd){
 vec3 throughput=vec3(1.),result=vec3(0.);bool previousDelta=true;ivec3 media=ivec3(0);float glassIOR=1.5,previousPdf=0.;
 for(int bounce=0;bounce<16;bounce++){
  if(bounce>=uMaxBounces)break;Hit hit;
  if(!trace(ro,rd,hit)){
   float mis=previousDelta?1.:powerHeuristic(previousPdf,environmentPdf(rd));result+=throughput*environment(rd)*mis;break;
  }
  throughput*=exp(-mediumAbsorption(media)*hit.t);
  vec3 point=ro+rd*hit.t,n=hit.n,gn=hit.geometric;bool front=dot(rd,gn)<0.;n=dot(n,rd)>0.?-n:n;
  bool coated=hit.material==0&&random()<clamp(hit.foam*.92,0.,.98);
  float materialIOR=texelFetch(tMaterials,ivec2(hit.material,0),0).a;
  if((hit.material==0||hit.material==2||materialIOR>=1.)&&!coated){
   ivec3 next=media;
   if(hit.material==0)next.x=max(0,next.x+(front?1:-1));
   else if(hit.material==2)next.z=max(0,next.z+(front?1:-1));
   else{next.y=max(0,next.y+(front?1:-1));glassIOR=materialIOR;}
   float ei=mediumIOR(media,glassIOR),et=mediumIOR(next,glassIOR),F=fresnel(clamp(-dot(n,rd),0.,1.),ei,et);
   vec3 refracted=refract(rd,n,ei/et);
   if(random()<F||dot(refracted,refracted)<.01)rd=reflect(rd,n);
   else {rd=normalize(refracted);media=next;throughput*=pow(ei/et,2.);}
   ro=point+rd*uEpsilon*3.;previousDelta=true;
  }else{
   vec3 albedo=coated?vec3(.88):texelFetch(tMaterials,ivec2(hit.material,0),0).rgb;
   if(hit.material==254){float checker=mod(floor(point.x/uFloor.x*9.6)+floor(point.z/uFloor.z*6.4),2.);albedo=mix(vec3(.41,.45,.42),vec3(.56,.59,.54),checker);}
   if(hit.material==255)albedo=uBackground;
   if(dot(gn,rd)>0.)gn=-gn;
   float lightPdf;vec3 wi=sampleEnvironment(lightPdf);float cosine=max(0.,dot(n,wi));
   if(cosine>0.&&lightPdf>0.){
    Hit blocker;if(!trace(point+gn*uEpsilon*3.,wi,blocker)){
     float bsdfPdf=cosine/PI;result+=throughput*albedo*environment(wi)*(bsdfPdf/lightPdf)*powerHeuristic(lightPdf,bsdfPdf);
    }
   }
   rd=cosineDirection(n);if(dot(rd,gn)<0.)rd=reflect(rd,gn);
   previousPdf=max(0.,dot(n,rd))/PI;previousDelta=false;throughput*=albedo;ro=point+gn*uEpsilon*3.;
  }
  if(bounce>=4){float survive=clamp(max(throughput.r,max(throughput.g,throughput.b)),.08,.95);if(random()>survive)break;throughput/=survive;}
 }
 return max(result,vec3(0.));
}
void main(){
 seed=uint(gl_FragCoord.x)*1973u+uint(gl_FragCoord.y)*9277u+uint(uSample+1)*26699u+89173u;
 vec2 uv=(gl_FragCoord.xy+vec2(random(),random())-.5)/uResolution;
 vec4 cameraPoint=uInverseProjection*vec4(uv*2.-1.,1.,1.);vec3 rd=normalize(mat3(uCameraWorld)*(cameraPoint.xyz/cameraPoint.w));vec3 ro=uCameraWorld[3].xyz;
 vec3 value=radiance(ro,rd);vec3 prior=texelFetch(tPrevious,ivec2(gl_FragCoord.xy),0).rgb;
 if(any(isnan(value))||any(isinf(value)))value=vec3(0.);
 outColor=vec4(uSample==0?value:prior+(value-prior)/float(uSample+1),1.);
}`;
const DISPLAY=`precision highp float;uniform sampler2D tImage;uniform float uExposure;in vec2 vUV;out vec4 outColor;
vec3 aces(vec3 x){return clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.,1.);}
void main(){vec3 c=aces(texture(tImage,vUV).rgb*uExposure);c=mix(c*12.92,1.055*pow(c,vec3(1./2.4))-.055,step(vec3(.0031308),c));outColor=vec4(c,1.);}`;
function texture(data,texels){
 const width=Math.min(2048,Math.max(1,texels)),height=Math.max(1,Math.ceil(texels/width));
 const padded=new Float32Array(width*height*4);padded.set(data);
 const t=new T.DataTexture(padded,width,height,T.RGBAFormat,T.FloatType);t.minFilter=t.magFilter=T.NearestFilter;t.needsUpdate=true;return t;
}
function aliasTexture(){
 const n=256*128,weights=new Float64Array(n);let sum=0;
 for(let i=0;i<n;i++){const th=(Math.floor(i/256)+.5)/128*Math.PI,ph=(i%256+.5)/256*Math.PI*2;const r=window.CYBR_ENV_RADIANCE(-Math.sin(th)*Math.cos(ph),Math.cos(th),Math.sin(th)*Math.sin(ph));weights[i]=(r[0]*.2126+r[1]*.7152+r[2]*.0722)*Math.sin(th);sum+=weights[i];}
 const probabilities=Float64Array.from(weights,w=>w/sum),scaled=Float64Array.from(probabilities,w=>w*n),small=[],large=[],data=new Float32Array(n*4);
 for(let i=0;i<n;i++){(scaled[i]<1?small:large).push(i);data[i*4+2]=probabilities[i];}
 while(small.length&&large.length){const s=small.pop(),l=large.pop();data[s*4]=scaled[s];data[s*4+1]=l;scaled[l]-=1-scaled[s];(scaled[l]<1?small:large).push(l);}
 for(const i of [...small,...large]){data[i*4]=1;data[i*4+1]=i;}
 const t=new T.DataTexture(data,256,128,T.RGBAFormat,T.FloatType);t.needsUpdate=true;return t;
}
function buildBVH(data){
 const n=data.length/24,order=new Uint32Array(n),bounds=new Float32Array(n*6),centers=new Float32Array(n*3);
 for(let i=0;i<n;i++){
  order[i]=i;const q=i*24,r=data[q+3];
  for(let a=0;a<3;a++){
   const lo=r>0?data[q+a]-r:Math.min(data[q+a],data[q+4+a],data[q+8+a]);
   const hi=r>0?data[q+a]+r:Math.max(data[q+a],data[q+4+a],data[q+8+a]);
   bounds[i*6+a]=lo-1e-6;bounds[i*6+3+a]=hi+1e-6;centers[i*3+a]=(lo+hi)*.5;
  }
 }
 const nodes=[];
 function partition(start,end,axis,middle){
  let left=start,right=end-1;
  while(left<right){const pivot=centers[order[(left+right)>>1]*3+axis];let i=left,j=right;
   while(i<=j){while(centers[order[i]*3+axis]<pivot)i++;while(centers[order[j]*3+axis]>pivot)j--;if(i<=j){const v=order[i];order[i]=order[j];order[j]=v;i++;j--;}}
   if(middle<=j)right=j;else if(middle>=i)left=i;else break;
  }
 }
 function node(start,end,depth){
  const id=nodes.length;const lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
  for(let i=start;i<end;i++){const q=order[i]*6;for(let a=0;a<3;a++){lo[a]=Math.min(lo[a],bounds[q+a]);hi[a]=Math.max(hi[a],bounds[q+3+a]);}}
  const entry=[...lo,0,...hi,0];nodes.push(entry);
  if(end-start<=8){entry[3]=-start-1;entry[7]=end-start;return id;}
  let axis=0;for(let a=1;a<3;a++)if(hi[a]-lo[a]>hi[axis]-lo[axis])axis=a;
  const middle=(start+end)>>1;partition(start,end,axis,middle);entry[3]=node(start,middle,depth+1);entry[7]=node(middle,end,depth+1);return id;
 }
 node(0,n,0);const sorted=new Float32Array(data.length);for(let i=0;i<n;i++)sorted.set(data.subarray(order[i]*24,order[i]*24+24),i*24);
 return {nodes:Float32Array.from(nodes.flat()),primitives:sorted,nodeCount:nodes.length,primitiveCount:n};
}
class ReferencePathTracer{
 constructor(liquid){
  this.liquid=liquid;this.renderer=liquid.renderer;this.samples=0;this.enabled=false;this.resources=[];
  this.scene=new T.Scene();this.camera=new T.Camera();this.quad=new T.Mesh(new T.PlaneGeometry(2,2));this.quad.frustumCulled=false;this.scene.add(this.quad);
  this.alias=aliasTexture();this.targets=[0,1].map(()=>new T.WebGLRenderTarget(1,1,{type:T.FloatType,depthBuffer:false,minFilter:T.NearestFilter,magFilter:T.NearestFilter}));
  this.uniforms={tPrevious:{value:this.targets[0].texture},tNodes:{value:null},tPrimitives:{value:null},tAlias:{value:this.alias},tMaterials:{value:null},uNodeSize:{value:new T.Vector2()},uPrimitiveSize:{value:new T.Vector2()},uResolution:{value:new T.Vector2()},uCameraWorld:{value:new T.Matrix4()},uInverseProjection:{value:new T.Matrix4()},uSample:{value:0},uMaxBounces:{value:10},uPrimitiveCount:{value:0},uIOR:{value:1.333},uEpsilon:{value:1e-5},uAbsorption:{value:new T.Vector3()},uBackground:{value:new T.Vector3(.025,.032,.040)},uFloor:{value:new T.Vector4()}};
  this.traceMaterial=new T.RawShaderMaterial({glslVersion:T.GLSL3,vertexShader:VERTEX,fragmentShader:FRAGMENT,uniforms:this.uniforms,depthTest:false,depthWrite:false});
  this.displayMaterial=new T.RawShaderMaterial({glslVersion:T.GLSL3,vertexShader:VERTEX,fragmentShader:DISPLAY,uniforms:{tImage:{value:null},uExposure:{value:1.04}},depthTest:false,depthWrite:false});
 }
 build(){
  const started=performance.now(),l=this.liquid,d=l.latest;if(!d?.indices?.length)throw Error('No reconstructed liquid geometry is available for tracing.');
  for(const t of this.resources)t.dispose();this.resources=[];
  let floats=[];
  const appendTriangle=(a,b,c,na,nb,nc,mat,foam=[0,0,0])=>{floats.push(...a,0,...b,mat,...c,0,...na,foam[0],...nb,foam[1],...nc,foam[2]);};
  const p=d.positions,n=d.normals,f=d.foam??new Float32Array(p.length/3),ix=d.indices;
  for(let i=0;i<ix.length;i+=3){const a=ix[i],b=ix[i+1],c=ix[i+2];appendTriangle(p.subarray(a*3,a*3+3),p.subarray(b*3,b*3+3),p.subarray(c*3,c*3+3),n.subarray(a*3,a*3+3),n.subarray(b*3,b*3+3),n.subarray(c*3,c*3+3),0,[f[a],f[b],f[c]]);}
  const appendSphere=(center,radius,mat)=>{floats.push(...center,radius,0,0,0,mat,0,0,0,0,0,1,0,0,0,1,0,0,0,1,0,0);};
  for(let i=0;i<(d.drops?.length??0);i+=3)appendSphere(d.drops.subarray(i,i+3),d.dropRadii?.[i/3]??l.config.h*Math.cbrt(3/(32*Math.PI)),0);
  for(let i=0;i<(d.white?.length??0);i+=6){if(d.white[i+5]<.08)continue;appendSphere(d.white.subarray(i,i+3),d.white[i+3],d.white[i+4]===2?2:d.white[i+4]===1?0:1);}
  const colors=new Float32Array(256*4);colors.set([.88,.91,.91,0],4);let mat=3;
  l.objects.updateMatrixWorld(true);
  l.objects.traverse(o=>{
   if(!o.isMesh||!o.visible)return;const id=o===l.floorMesh?254:Math.min(mat++,253);const color=o.material.color??new T.Color(.3,.3,.3);colors.set([color.r,color.g,color.b,o.material.transmission>0.001?(o.material.ior??1.5):0],id*4);
   const g=o.geometry,pos=g.attributes.position,normal=g.attributes.normal,index=g.index,normalMatrix=new T.Matrix3().getNormalMatrix(o.matrixWorld),num=index?index.count:pos.count;
   const pv=[new T.Vector3(),new T.Vector3(),new T.Vector3()],nv=[new T.Vector3(),new T.Vector3(),new T.Vector3()];
   for(let i=0;i<num;i+=3){for(let j=0;j<3;j++){const k=index?index.getX(i+j):i+j;pv[j].fromBufferAttribute(pos,k).applyMatrix4(o.matrixWorld);nv[j].fromBufferAttribute(normal,k).applyMatrix3(normalMatrix).normalize();}appendTriangle(...pv.map(v=>v.toArray()),...nv.map(v=>v.toArray()),id);}
  });
  const bvh=buildBVH(Float32Array.from(floats));floats=null;
  const nt=texture(bvh.nodes,bvh.nodeCount*2),pt=texture(bvh.primitives,bvh.primitiveCount*6),mt=new T.DataTexture(colors,256,1,T.RGBAFormat,T.FloatType);mt.needsUpdate=true;
  this.resources=[nt,pt,mt];this.uniforms.tNodes.value=nt;this.uniforms.tPrimitives.value=pt;this.uniforms.tMaterials.value=mt;
  this.uniforms.uNodeSize.value.set(nt.image.width,nt.image.height);this.uniforms.uPrimitiveSize.value.set(pt.image.width,pt.image.height);
  this.uniforms.uPrimitiveCount.value=bvh.primitiveCount;this.uniforms.uIOR.value=l.material.uniforms.uIOR.value;this.uniforms.uAbsorption.value.copy(l.material.uniforms.uAbsorption.value);
  this.uniforms.uEpsilon.value=l.config.extent[0]*2e-6;this.uniforms.uFloor.value.set(l.config.extent[0],0,l.config.extent[2],l.backgroundFloor.position.y);
  this.stats={...bvh,nodes:undefined,primitives:undefined,buildMilliseconds:performance.now()-started,integrator:'WebGL2 BVH / nested water-glass-air dielectric / Beer-Lambert / environment NEE + MIS',mediumLimitations:'Outside-camera initialization; overlapping dielectrics share a glass-IOR scalar, not arbitrary priority media',maxBounces:this.uniforms.uMaxBounces.value,opaqueModel:'Lambertian reference; not GGX metal'};
  this.resize(l.width,l.height);return this.stats;
 }
 resize(w,h){for(const t of this.targets)t.setSize(w,h);this.uniforms.uResolution.value.set(w,h);this.samples=0;}
 resetCamera(){this.samples=0;}
 sample(count=1){
  const l=this.liquid,r=this.renderer;l.camera.updateMatrixWorld(true);this.uniforms.uCameraWorld.value.copy(l.camera.matrixWorld);this.uniforms.uInverseProjection.value.copy(l.camera.projectionMatrixInverse);
  for(let i=0;i<count;i++){
   const read=this.targets[this.samples%2],write=this.targets[(this.samples+1)%2];this.uniforms.tPrevious.value=read.texture;this.uniforms.uSample.value=this.samples;
   this.quad.material=this.traceMaterial;r.setRenderTarget(write);r.render(this.scene,this.camera);this.samples++;
  }
  this.quad.material=this.displayMaterial;this.displayMaterial.uniforms.tImage.value=this.targets[this.samples%2].texture;r.setRenderTarget(null);r.render(this.scene,this.camera);
  return {samples:this.samples,...this.stats,glError:r.getContext().getError()};
 }
 dispose(){for(const t of [...this.resources,...this.targets,this.alias])t.dispose();this.traceMaterial.dispose();this.displayMaterial.dispose();this.quad.geometry.dispose();}
}
window.ReferencePathTracer=ReferencePathTracer;window.CYBR_BVH_TRACE=FRAGMENT.slice(FRAGMENT.indexOf('vec4 texel('),FRAGMENT.indexOf('float fresnel('));
})();
