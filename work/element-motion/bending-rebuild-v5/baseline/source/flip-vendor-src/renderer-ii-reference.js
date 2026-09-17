/* CYBR FLIP III — Three.js dielectric raster renderer.
 * Front and exit depths come from the evolving particle mesh, not a height field.
 * Refraction is an iterative screen-space approximation; the separate progressive
 * integrator is separately selectable for reference images.
 */
(function(){
'use strict';
const T=THREE;
const WATER_VERTEX=`attribute float foam;varying float vFoam;varying vec3 vWorld,vNormalW,vView;
void main(){vFoam=foam;vec4 w=modelMatrix*vec4(position,1.);vWorld=w.xyz;vNormalW=normalize(mat3(modelMatrix)*normal);vec4 p=viewMatrix*w;vView=p.xyz;gl_Position=projectionMatrix*p;}`;
const ENVIRONMENT=`
float rect(vec2 p,vec2 c,vec2 size,float edge){vec2 d=abs(p-c)-size;return 1.-smoothstep(-edge,edge,max(d.x,d.y));}
vec3 environment(vec3 d){
 vec3 e=mix(vec3(.055,.065,.075),vec3(.40,.45,.48),smoothstep(-.25,.85,d.y));
 if(d.y>0.){vec2 q=d.xz/max(.045,d.y);
 e+=vec3(4.8,5.1,5.3)*rect(q,vec2(-.65,-.4),vec2(.80,.20),.045);
 e+=vec3(2.5,3.3,3.8)*rect(q,vec2(1.2,.9),vec2(.17,1.15),.05);
 e+=vec3(2.8,2.45,1.95)*rect(q,vec2(.1,1.9),vec2(1.4,.16),.055);}
 e+=pow(max(0.,dot(d,normalize(vec3(-1.,.16,.2)))),65.)*vec3(1.4,.86,.37);
 return e;
}`;
const WATER_FRAGMENT=`uniform sampler2D tScene,tBack,tDepth;uniform vec2 uResolution;uniform mat4 uViewProjection;
uniform float uNear,uFar,uIOR,uScale,uDiagnostic,uFloor;uniform vec3 uAbsorption;uniform vec3 uExtent;
varying float vFoam;varying vec3 vWorld,vNormalW,vView;
${ENVIRONMENT}
float linearDepth(float z){return uNear*uFar/(uFar-z*(uFar-uNear));}
float fresnel(float c,float ei,float et){float st=ei/et*sqrt(max(0.,1.-c*c));if(st>=1.)return 1.;float ct=sqrt(1.-st*st);float a=(ei*c-et*ct)/(ei*c+et*ct),b=(et*c-ei*ct)/(et*c+ei*ct);return .5*(a*a+b*b);}
vec2 project(vec3 p){vec4 q=uViewProjection*vec4(p,1.);return q.xy/q.w*.5+.5;}
void main(){
 vec3 V=normalize(cameraPosition-vWorld),N=normalize(vNormalW);if(dot(N,V)<0.)N=-N;
 vec2 uv=gl_FragCoord.xy/uResolution;float front=-vView.z;
 vec4 backSample=texture2D(tBack,uv);float back=backSample.r;
 float sceneDepth=linearDepth(texture2D(tDepth,uv).r);
 float path=max(.002*uScale,min(back>front?back:front+.025*uScale,sceneDepth)-front)*length(vView)/max(.0001,front);
 path=clamp(path,.001*uScale,5.5*uScale);
 vec3 transmissionRay=refract(-V,N,1./uIOR);
 vec3 end=vWorld+transmissionRay*path;
 vec2 endUV=project(end);
 // Two fixed-point corrections locate an exit on the back-depth layer. This
 // avoids the old assumption that the entrance and exit use identical pixels.
 for(int j=0;j<2;j++){
  vec2 q=clamp(endUV,vec2(.001),vec2(.999));vec4 b=texture2D(tBack,q);
  float vd=-(viewMatrix*vec4(end,1.)).z,rayDepth=-(viewMatrix*vec4(transmissionRay,0.)).z;
  if(b.r>front+.001*uScale&&abs(rayDepth)>.1){
   float correction=clamp((b.r-vd)/rayDepth,-path*.4,path*.4);
   path=clamp(path+correction,.001*uScale,5.5*uScale);end=vWorld+transmissionRay*path;endUV=project(end);
  }
 }
 vec3 exitNormal=normalize(texture2D(tBack,clamp(endUV,.002,.998)).gba*2.-1.);
 if(dot(exitNormal,transmissionRay)<0.)exitNormal=-exitNormal;
 vec3 outgoing=refract(transmissionRay,-exitNormal,uIOR);
 bool tir=dot(outgoing,outgoing)<.01;
 if(tir)outgoing=reflect(transmissionRay,exitNormal);
 // Continue the refracted ray toward opaque depth rather than sampling a fixed
 // normal-offset UV. Opaque foreground rejection prevents object pull-through.
 float floorT=(uFloor-end.y)/outgoing.y;
 vec3 opaquePoint=end+outgoing*.12*uScale;
 if(outgoing.y<-.04&&floorT>0.&&floorT<15.*uScale)opaquePoint=end+outgoing*floorT;
 vec2 refractUV=clamp(project(opaquePoint),vec2(.002),vec2(.998));
 float sd=linearDepth(texture2D(tDepth,refractUV).r);
 if(sd<front-.02*uScale)refractUV=uv;
 vec3 background=texture2D(tScene,refractUV).rgb;
 vec3 attenuation=exp(-uAbsorption*path);
 float F=fresnel(clamp(dot(N,V),0.,1.),1.,uIOR);
 vec3 reflection=environment(reflect(-V,N));
 vec3 body=background*attenuation;
 if(tir)body=mix(body,environment(outgoing),.30);
 vec3 col=mix(body,reflection,F);
 float foam=clamp(vFoam,0.,.97);
 col=mix(col,vec3(.82,.855,.85)*(.62+.38*max(N.y,0.)),foam*.90);
 if(uDiagnostic>0.5)col=mix(vec3(.015,.03,.06),vec3(.98,.61,.14),clamp(path/(2.*uScale),0.,1.));
 gl_FragColor=vec4(col,1.);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`;
const DEPTH_FRAGMENT=`varying vec3 vView,vNormalW;void main(){gl_FragColor=vec4(-vView.z,normalize(vNormalW)*.5+.5);}`;
const POINT_VERTEX=`attribute float radius,phase,opacity;uniform float uScale;varying float vPhase,vOpacity;varying vec3 vColor,vCenter;
void main(){vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(2.*radius*uScale/max(.001,-p.z),.65,48.);vPhase=phase;vOpacity=opacity;vColor=color;vCenter=position;}`;
const POINT_FRAGMENT=`varying float vPhase,vOpacity;varying vec3 vColor,vCenter;uniform float uDiagnostic;uniform sampler2D tScene;uniform vec2 uResolution;
${ENVIRONMENT}
void main(){vec2 p=gl_PointCoord*2.-1.;float r2=dot(p,p);if(r2>1.)discard;
 float z=sqrt(max(0.,1.-r2));vec3 n=vec3(p.x,-p.y,z),V=normalize(cameraPosition-vCenter);
 float edge=1.-smoothstep(.65,1.,r2);vec3 col=vec3(.87,.91,.91)*(.68+.32*max(dot(n,normalize(vec3(-.5,.65,.7))),0.));
 float alpha=vOpacity*edge;
 if(vPhase>1.5&&vPhase<2.5){float rim=pow(1.-z,1.3);col=vec3(.48,.63,.66)+vec3(.70)*rim;alpha*=.15+.75*rim;}
 if(vPhase>2.5){
  vec3 nw=normalize((vec4(n,0.)*viewMatrix).xyz);float F=.0204+.9796*pow(1.-z,5.);
  vec3 bg=texture2D(tScene,clamp(gl_FragCoord.xy/uResolution+p*.0012,vec2(.001),vec2(.999))).rgb;
  col=mix(bg,environment(reflect(-V,nw)),F);alpha*=.95;
 }
 if(uDiagnostic>.5){col=vColor;alpha=vOpacity*edge;}
 gl_FragColor=vec4(col,alpha);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`;
function makePoints(diagnostic=false){
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute([],3));
 const m=new T.ShaderMaterial({vertexShader:POINT_VERTEX,fragmentShader:POINT_FRAGMENT,
 uniforms:{uScale:{value:1000},uDiagnostic:{value:diagnostic?1:0},uResolution:{value:new T.Vector2(1,1)},tScene:{value:null}},
 vertexColors:true,transparent:true,depthWrite:false,depthTest:true,blending:T.NormalBlending});
 const o=new T.Points(g,m);o.frustumCulled=false;return o;
}
function setPoints(o,p,r,phase,opacity,color){
 const old=o.geometry,g=new T.BufferGeometry();o.geometry=g;old.dispose();g.setAttribute('position',new T.Float32BufferAttribute(p,3));g.setAttribute('radius',new T.Float32BufferAttribute(r,1));
 g.setAttribute('phase',new T.Float32BufferAttribute(phase,1));g.setAttribute('opacity',new T.Float32BufferAttribute(opacity,1));g.setAttribute('color',new T.Float32BufferAttribute(color,3));g.setDrawRange(0,p.length/3);
}
function tileTexture(){
 const c=document.createElement('canvas');c.width=c.height=512;const x=c.getContext('2d');
 x.fillStyle='#babeb7';x.fillRect(0,0,512,512);
 x.fillStyle='#9da69e';x.fillRect(0,0,256,256);x.fillRect(256,256,256,256);
 x.strokeStyle='#75857c';x.lineWidth=2;for(let i=0;i<=512;i+=128){x.beginPath();x.moveTo(i,0);x.lineTo(i,512);x.moveTo(0,i);x.lineTo(512,i);x.stroke();}
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(2.4,1.6);t.anisotropy=4;return t;
}
function envRadiance(x,y,z){
 const smooth=(a,b,x)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t);};
 const t=smooth(-.25,.85,y),e=[.055+(.40-.055)*t,.065+(.45-.065)*t,.075+(.48-.075)*t];
 if(y>0){const qx=x/Math.max(.045,y),qz=z/Math.max(.045,y);
  for(const [cx,cz,hx,hz,ed,cr,cg,cb] of [[-.65,-.4,.80,.20,.045,4.8,5.1,5.3],[1.2,.9,.17,1.15,.05,2.5,3.3,3.8],[.1,1.9,1.4,.16,.055,2.8,2.45,1.95]]){
   const a=1-smooth(-ed,ed,Math.max(Math.abs(qx-cx)-hx,Math.abs(qz-cz)-hz));e[0]+=a*cr;e[1]+=a*cg;e[2]+=a*cb;
  }
 }
 const l=Math.hypot(-1,.16,.2),rim=Math.pow(Math.max(0,(-x+.16*y+.2*z)/l),65);e[0]+=1.4*rim;e[1]+=.86*rim;e[2]+=.37*rim;return e;
}
function environmentTexture(){
 const w=512,h=256,data=new Float32Array(w*h*4);
 for(let y=0;y<h;y++)for(let x=0;x<w;x++){
  const theta=(y+.5)/h*Math.PI,phi=(x+.5)/w*Math.PI*2;
  const d=[-Math.sin(theta)*Math.cos(phi),Math.cos(theta),Math.sin(theta)*Math.sin(phi)];
  data.set([...envRadiance(...d),1],(y*w+x)*4);
 }
 const t=new T.DataTexture(data,w,h,T.RGBAFormat,T.FloatType);t.mapping=T.EquirectangularReflectionMapping;t.needsUpdate=true;t.minFilter=t.magFilter=T.LinearFilter;return t;
}
class LiquidRenderer{
 constructor(canvas){
  this.renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
  this.renderer.setPixelRatio(1);this.renderer.outputColorSpace=T.SRGBColorSpace;this.renderer.toneMapping=T.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.04;
  this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=T.PCFSoftShadowMap;
  this.scene=new T.Scene();this.scene.background=new T.Color(0x10161d);this.scene.fog=new T.Fog(0x10161d,15,35);
  this.env=environmentTexture();this.scene.environment=this.env;this.scene.environmentIntensity=.7;
  this.camera=new T.PerspectiveCamera(38,16/9,.04,50);this.target=new T.Vector3(2.4,.9,1.6);
  this.scene.add(new T.HemisphereLight(0xe4eff5,0x37423d,.6));
  this.key=new T.DirectionalLight(0xf0f4ef,1.65);this.key.position.set(-1,7,4);this.key.castShadow=true;
  this.key.shadow.mapSize.set(1024,1024);this.key.shadow.bias=-.0003;this.key.shadow.normalBias=.009;
  this.scene.add(this.key,this.key.target);
  const rim=new T.DirectionalLight(0xc6e6f3,.35);rim.position.set(4,3,-4);this.scene.add(rim);
  this.objects=new T.Group();this.scene.add(this.objects);this.colliderMeshes=[];
  const bg=new T.Mesh(new T.PlaneGeometry(100,100),new T.MeshStandardMaterial({color:0x192129,roughness:.9}));bg.rotation.x=-Math.PI/2;bg.position.y=-.21;bg.receiveShadow=true;this.scene.add(bg);this.backgroundFloor=bg;
  this.sceneRT=new T.WebGLRenderTarget(1,1,{type:T.HalfFloatType,depthBuffer:true});this.sceneRT.depthTexture=new T.DepthTexture(1,1,T.UnsignedIntType);
  this.backRT=new T.WebGLRenderTarget(1,1,{type:T.FloatType,depthBuffer:true,minFilter:T.NearestFilter,magFilter:T.NearestFilter});
  this.causticTexture=new T.DataTexture(new Uint8Array(2),1,1,T.RGFormat,T.UnsignedByteType);this.causticTexture.needsUpdate=true;this.causticTexture.minFilter=this.causticTexture.magFilter=T.LinearFilter;
  this.causticUniform={value:this.causticTexture};this.extentUniform={value:new T.Vector3(4.8,3.2,3.2)};
  this.waterScene=new T.Scene();this.backScene=new T.Scene();this.whiteScene=new T.Scene();this.bubbleScene=new T.Scene();
  this.geometry=new T.BufferGeometry();this.geometry.setAttribute('position',new T.Float32BufferAttribute([],3));
  this.material=new T.ShaderMaterial({vertexShader:WATER_VERTEX,fragmentShader:WATER_FRAGMENT,
   uniforms:{tScene:{value:this.sceneRT.texture},tBack:{value:this.backRT.texture},tDepth:{value:this.sceneRT.depthTexture},uResolution:{value:new T.Vector2(1,1)},
   uFloor:{value:.08},uNear:{value:.04},uFar:{value:50},uViewProjection:{value:new T.Matrix4()},uAbsorption:{value:new T.Vector3(.20,.052,.019)},uIOR:{value:1.333},uScale:{value:1},uDiagnostic:{value:0},uExtent:this.extentUniform},side:T.FrontSide});
  this.water=new T.Mesh(this.geometry,this.material);this.water.frustumCulled=false;this.waterScene.add(this.water);
  this.back=new T.Mesh(this.geometry,new T.ShaderMaterial({vertexShader:WATER_VERTEX,fragmentShader:DEPTH_FRAGMENT,side:T.BackSide}));this.back.frustumCulled=false;this.backScene.add(this.back);
  this.normalMaterial=new T.MeshNormalMaterial({side:T.DoubleSide});this.wireMaterial=new T.MeshBasicMaterial({color:0x75d8c3,wireframe:true});
  this.white=makePoints();this.bubbles=makePoints();this.particlePoints=makePoints(true);this.whiteScene.add(this.white,this.particlePoints);this.bubbleScene.add(this.bubbles);
  this.particlePoints.visible=false;this.mode='water';this.shot=0;this.name='breach';this.scale=1;this.orbit=null;this.drag=null;
  this.setupOrbit(canvas);this.resize(innerWidth,innerHeight);
 }
 disposeGroup(){this.objects.traverse(o=>{o.geometry?.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material]){m.map?.dispose();m.dispose();}}});this.objects.clear();}
 box(size,pos,color,metal=0,rough=.5){const o=new T.Mesh(new T.BoxGeometry(...size),new T.MeshStandardMaterial({color,metalness:metal,roughness:rough}));o.position.set(...pos);o.castShadow=true;o.receiveShadow=true;this.objects.add(o);return o;}
 setup(config){
  this.config=config;this.name=config.nameKey;this.disposeGroup();this.colliderMeshes=[];
  const e=config.extent,s=e[0]/4.8;this.scale=s;this.floorY=config.h*1.02;
  this.material.uniforms.uFloor.value=this.floorY;this.extentUniform.value.set(...e);this.material.uniforms.uScale.value=s;
  this.material.uniforms.uAbsorption.value.set(...(this.name==='viscous'?[1.3,3.8,8.0]:[.20,.052,.019]));
  this.material.uniforms.uIOR.value=this.name==='viscous'?1.47:1.333;
  this.camera.near=Math.max(.0005,.04*s);this.camera.far=50*s;this.camera.updateProjectionMatrix();
  this.material.uniforms.uNear.value=this.camera.near;this.material.uniforms.uFar.value=this.camera.far;
  this.backgroundFloor.position.y=-.21*s;
  this.scene.fog.near=15*s;this.scene.fog.far=35*s;
  this.key.position.set(-s,7*s,4*s);this.key.target.position.set(e[0]*.5,0,e[2]*.5);
  const cam=this.key.shadow.camera;cam.left=-6*s;cam.right=6*s;cam.top=6*s;cam.bottom=-6*s;cam.near=.05*s;cam.far=25*s;cam.updateProjectionMatrix();this.key.shadow.normalBias=.009*s;
  this.box([e[0]+.30*s,.24*s,e[2]+.30*s],[e[0]/2,this.floorY-.17*s,e[2]/2],0x17282d,.6,.24);
  const floor=this.box([e[0]-.08*s,.035*s,e[2]-.08*s],[e[0]/2,this.floorY-.018*s,e[2]/2],0xffffff,.03,.48);floor.material.map=tileTexture();this.floorMesh=floor;
  floor.material.onBeforeCompile=shader=>{
   shader.uniforms.tCaustic=this.causticUniform;shader.uniforms.causticExtent=this.extentUniform;
   shader.vertexShader='varying vec3 vCausticWorld;\n'+shader.vertexShader;
   shader.vertexShader=shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvCausticWorld=(modelMatrix*vec4(position,1.)).xyz;');
   shader.fragmentShader='uniform sampler2D tCaustic;uniform vec3 causticExtent;varying vec3 vCausticWorld;\n'+shader.fragmentShader;
   shader.fragmentShader=shader.fragmentShader.replace('#include <map_fragment>',`#include <map_fragment>
    vec2 caustic=texture2D(tCaustic,vCausticWorld.xz/causticExtent.xz).rg;
    float ca=pow(caustic.r*4.,2.);
    diffuseColor.rgb*=mix(1.,.70+min(ca,4.)*.32,caustic.g);`);
  };
  for(const z of [.01*s,e[2]-.01*s])this.box([e[0]+.18*s,.085*s,.065*s],[e[0]/2,.12*s,z],0x3b5054,.85,.18);
  for(const x of [.01*s,e[0]-.01*s])this.box([.065*s,.085*s,e[2]],[x,.12*s,e[2]/2],0x3b5054,.85,.18);
  for(let i=0;i<25;i++)this.box([.010*s,.004*s,(i%5===0?.13:.05)*s],[.12*s+i*(e[0]-.24*s)/24,.145*s,e[2]+.06*s],0xbaccc7,.05,.5);
  for(const o of config.obstacles){
   let mesh;
   if(o.kind==='box')mesh=this.box(o.half.map(x=>x*2),o.center,0x41514e,.42,.21);
   else{mesh=new T.Mesh(new T.SphereGeometry(o.radius,64,40),new T.MeshStandardMaterial({color:0xa1a998,metalness:.8,roughness:.16}));mesh.position.set(...o.center);mesh.castShadow=true;mesh.receiveShadow=true;this.objects.add(mesh);}
   this.colliderMeshes.push(mesh);
  }
  if(this.name==='jets')for(const x of [.21,e[0]-.21]){
   const pipe=new T.Mesh(new T.CylinderGeometry(.264,.264,.33,48,1,true),new T.MeshStandardMaterial({color:0x8a9592,metalness:.95,roughness:.18,side:T.DoubleSide}));pipe.rotation.z=Math.PI/2;pipe.position.set(x,1.35,1.6);this.objects.add(pipe);
   const ring=new T.Mesh(new T.TorusGeometry(.247,.024,12,48),new T.MeshStandardMaterial({color:0xb5c3c2,metalness:.95,roughness:.15}));ring.rotation.y=Math.PI/2;ring.position.set(x<2?x+.165:x-.165,1.35,1.6);this.objects.add(ring);
   this.box([.13,1.2,.16],[x,.67,1.6],0x223532,.8,.25);
  }
  if(this.name==='viscous'){
   const pipe=new T.Mesh(new T.CylinderGeometry(.075,.075,.16,48,1,true),new T.MeshStandardMaterial({color:0xa3aaa5,metalness:.9,roughness:.15,side:T.DoubleSide}));pipe.position.set(.8,1.09,.6);this.objects.add(pipe);
  }
  this.orbit=null;this.updateCamera();
 }
 setMetrics(m){
  this.metrics=m;
  const obstacles=m.colliders??this.config.obstacles;
  obstacles.forEach((o,i)=>{this.colliderMeshes[i]?.position.set(...o.center);});
 }
 resize(w,h){
  this.width=w;this.height=h;this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.sceneRT.setSize(w,h);this.backRT.setSize(w,h);
  this.material.uniforms.uResolution.value.set(w,h);
  for(const o of [this.white,this.bubbles,this.particlePoints]){o.material.uniforms.uScale.value=h/(2*Math.tan(this.camera.fov*Math.PI/360));o.material.uniforms.uResolution.value.set(w,h);o.material.uniforms.tScene.value=this.sceneRT.texture;}
 }
 setFrame(data){
  const old=this.geometry;this.geometry=new T.BufferGeometry();
  this.geometry.setAttribute('position',new T.Float32BufferAttribute(data.positions,3));this.geometry.setAttribute('normal',new T.Float32BufferAttribute(data.normals,3));
  this.geometry.setAttribute('foam',new T.Float32BufferAttribute(data.foam??new Float32Array(data.positions.length/3),1));this.geometry.setIndex(new T.BufferAttribute(data.indices,1));
  this.water.geometry=this.back.geometry=this.geometry;old.dispose();
  if(data.caustic){
   this.causticTexture.dispose();this.causticTexture=new T.DataTexture(data.caustic,data.causticWidth,data.causticHeight,T.RGFormat,T.UnsignedByteType);
   this.causticTexture.minFilter=this.causticTexture.magFilter=T.LinearFilter;this.causticTexture.needsUpdate=true;this.causticUniform.value=this.causticTexture;
  }
  const ww=data.white??new Float32Array(0),drops=data.drops??new Float32Array(0);
  const surface=[],under=[];
  for(let q=0;q<ww.length;q+=6)(ww[q+4]===2?under:surface).push(...ww.subarray(q,q+6));
  const load=(object,values,includeDrops)=>{
   const n=values.length/6+(includeDrops?drops.length/3:0),p=new Float32Array(n*3),r=new Float32Array(n),phase=new Float32Array(n),alpha=new Float32Array(n),colors=new Float32Array(n*3);let m=0;
   for(let q=0;q<values.length;q+=6,m++){
    p.set(values.slice(q,q+3),m*3);r[m]=values[q+3];phase[m]=values[q+4];alpha[m]=values[q+5]*(phase[m]===0?.88:.8);
    colors.set(phase[m]===0?[.25,.95,.65]:phase[m]===1?[1.,.50,.14]:[.25,.6,1.],m*3);
   }
   if(includeDrops)for(let q=0;q<drops.length;q+=3,m++){p.set(drops.subarray(q,q+3),m*3);r[m]=data.dropRadii?.[q/3]??this.config.h*Math.cbrt(3/(32*Math.PI));phase[m]=3;alpha[m]=.96;colors.set([.65,.84,1.],m*3);}
   setPoints(object,p,r,phase,alpha,colors);
  };
  load(this.white,surface,true);load(this.bubbles,under,false);
  const dg=data.diagnostic??new Float32Array(0),n=dg.length/3,r=new Float32Array(n).fill(this.config.h*.17),phase=new Float32Array(n),alpha=new Float32Array(n).fill(.88),color=new Float32Array(n*3);
  for(let i=0;i<n;i++){const a=Math.min(1,dg[i*3+1]/this.config.extent[1]);color.set([.16+.58*a,.50+.38*a,.68+.30*a],i*3);}
  setPoints(this.particlePoints,dg,r,phase,alpha,color);this.latest=data;
 }
 setMode(mode){
  this.mode=mode;this.particlePoints.visible=mode==='particles';this.white.visible=['water','whitewater'].includes(mode);this.bubbles.visible=['water','whitewater'].includes(mode);this.water.visible=mode!=='particles'&&mode!=='whitewater';
  this.water.material=mode==='normal'?this.normalMaterial:mode==='wire'?this.wireMaterial:this.material;
  this.material.uniforms.uDiagnostic.value=mode==='thickness'?1:0;
  this.white.material.uniforms.uDiagnostic.value=this.bubbles.material.uniforms.uDiagnostic.value=mode==='whitewater'?1:0;
 }
 setShot(n){this.shot=n;this.orbit=null;}
 updateCamera(progress=0){
  const s=this.scale,e=this.config?.extent??[4.8,3.2,3.2];
  if(this.orbit){const o=this.orbit;this.target.set(e[0]/2,.80*s,e[2]/2);this.camera.position.set(this.target.x+o.r*Math.cos(o.el)*Math.sin(o.az),this.target.y+o.r*Math.sin(o.el),this.target.z+o.r*Math.cos(o.el)*Math.cos(o.az));this.camera.lookAt(this.target);return;}
  let pos,aim,fov=38;
  if(this.shot===0){pos=[7.25-.28*progress,4.8+.15*progress,7.75];aim=[2.32,.86,1.58];}
  else if(this.shot===1){pos=[6.35+.15*progress,2.7+.08*progress,6.4-.20*progress];aim=[2.4,.80,1.60];fov=40;}
  else if(this.shot===2){pos=[2.35+.12*progress,7.9,3.35];aim=[2.4,.60,1.60];fov=40;}
  else {pos=[-.6,1.4,6.25];aim=[2.40,.75,1.60];fov=44;}
  if(this.name==='impact'&&this.shot===1){pos=[5.1,2.05,5.8];aim=[2.4,.71,1.6];fov=40;}
  if(this.name==='jets'&&this.shot===1){pos=[2.55,2.38,7.5];aim=[2.4,1.0,1.6];fov=42;}
  if(this.name==='cascade'&&this.shot===1){pos=[6.2,3.3,5.2];aim=[2.0,1.15,1.6];fov=42;}
  if(this.name==='capillary'){
   // A 16 cm domain is rendered in centimetres, never enlarged in the physics.
   const target=[.08,.062,.060],dist=this.shot===1?.13:.19;
   this.target.set(...target);this.camera.position.set(target[0]+(this.shot===2?0:dist*.8),target[1]+dist*(this.shot===2?1.1:.35),target[2]+dist*.92);
   this.camera.fov=36;this.camera.updateProjectionMatrix();this.camera.lookAt(this.target);return;
  }
  if(this.name==='viscous'){aim=[2.4,1.35,1.8];if(this.shot===1){pos=[4.6,2.4,5.9];aim=[2.4,.92,1.8];fov=38;}}
  this.camera.position.set(pos[0]*s,pos[1]*s,pos[2]*s);this.target.set(aim[0]*s,aim[1]*s,aim[2]*s);this.camera.fov=fov;this.camera.updateProjectionMatrix();this.camera.lookAt(this.target);
 }
 draw(progress=0){
  this.updateCamera(progress);this.camera.updateMatrixWorld();this.material.uniforms.uViewProjection.value.multiplyMatrices(this.camera.projectionMatrix,this.camera.matrixWorldInverse);
  for(const o of [this.white,this.bubbles,this.particlePoints])o.material.uniforms.uScale.value=this.height/(2*Math.tan(this.camera.fov*Math.PI/360));
  const r=this.renderer;r.autoClear=true;r.setRenderTarget(this.sceneRT);r.render(this.scene,this.camera);
  // Bubble radiance is underneath the dielectric and is attenuated by it.
  r.autoClear=false;this.bubbles.material.uniforms.tScene.value=this.backRT.texture;if(this.mode==='water')r.render(this.bubbleScene,this.camera);r.autoClear=true;
  r.setRenderTarget(this.backRT);r.setClearColor(0,1);r.clear();r.render(this.backScene,this.camera);
  r.setRenderTarget(null);r.setClearColor(0x10161d,1);r.render(this.scene,this.camera);
  r.autoClear=false;r.render(this.waterScene,this.camera);r.render(this.whiteScene,this.camera);if(this.mode==='whitewater')r.render(this.bubbleScene,this.camera);r.autoClear=true;
 }
 setupOrbit(canvas){
  canvas.addEventListener('pointerdown',e=>{this.drag=[e.clientX,e.clientY];if(!this.orbit){const d=this.camera.position.clone().sub(this.target);this.orbit={r:d.length(),az:Math.atan2(d.x,d.z),el:Math.asin(d.y/d.length())};}canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!this.drag)return;this.orbit.az-=(e.clientX-this.drag[0])*.005;this.orbit.el=Math.max(.025,Math.min(1.53,this.orbit.el+(e.clientY-this.drag[1])*.005));this.drag=[e.clientX,e.clientY];this.draw();});
  canvas.addEventListener('pointerup',()=>this.drag=null);
  canvas.addEventListener('wheel',e=>{e.preventDefault();if(!this.orbit){const d=this.camera.position.clone().sub(this.target);this.orbit={r:d.length(),az:Math.atan2(d.x,d.z),el:Math.asin(d.y/d.length())};}this.orbit.r=Math.max(.9*this.scale,Math.min(16*this.scale,this.orbit.r*Math.exp(e.deltaY*.001)));this.draw();},{passive:false});
 }
 info(){const gl=this.renderer.getContext(),ext=gl.getExtension('WEBGL_debug_renderer_info');return {backend:`Three.js r${T.REVISION}`,renderer:ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER),resolution:[this.width,this.height],vertices:this.geometry.attributes.position.count,triangles:(this.geometry.index?.count??0)/3,programs:this.renderer.info.programs.length,glError:gl.getError(),mode:this.mode,build:'CYBR FLIP III'};}
}
window.LiquidRenderer=LiquidRenderer;window.CYBR_ENVIRONMENT_GLSL=ENVIRONMENT;window.CYBR_ENV_RADIANCE=envRadiance;
})();
