/* Three.js raster renderer. Water uses a reconstructed volumetric surface,
 * measured front/back depth, Fresnel reflection, and Beer-Lambert attenuation.
 * Screen-space refraction is approximate; this is not a path tracer.
 */
(function(){
'use strict';
const T=THREE;
const WATER_VERTEX=`attribute float foam;varying float vFoam;varying vec3 vWorld;varying vec3 vNormalW;varying vec3 vView;
void main(){vFoam=foam;vec4 w=modelMatrix*vec4(position,1.);vWorld=w.xyz;vNormalW=normalize(mat3(modelMatrix)*normal);vec4 v=viewMatrix*w;vView=v.xyz;gl_Position=projectionMatrix*v;}`;
const ENVIRONMENT=`
float rect(vec2 p,vec2 c,vec2 halfSize,float edge){vec2 d=abs(p-c)-halfSize;return 1.-smoothstep(-edge,edge,max(d.x,d.y));}
vec3 environment(vec3 d){
 vec3 e=mix(vec3(.045,.065,.09),vec3(.35,.42,.48),smoothstep(-.25,.75,d.y));
 if(d.y>0.){vec2 q=d.xz/max(.06,d.y);
 e+=vec3(6.5,7.,7.4)*rect(q,vec2(-.65,-.4),vec2(.85,.24),.06);
 e+=vec3(3.8,4.5,5.)*rect(q,vec2(1.2,.9),vec2(.20,1.4),.05);
 e+=vec3(2.1,2.4,2.6)*rect(q,vec2(.1,1.9),vec2(1.8,.20),.05);}
 float rim=pow(max(0.,dot(d,normalize(vec3(-1.,.12,.2)))),50.);
 e+=rim*vec3(2.2,1.45,.68);return e;
}`;
const WATER_FRAGMENT=`uniform sampler2D tScene,tBack,tDepth;uniform vec2 uResolution;uniform mat4 uViewProjection;uniform float uNear,uFar;uniform vec3 uAbsorption;
varying float vFoam;varying vec3 vWorld;varying vec3 vNormalW;varying vec3 vView;
${ENVIRONMENT}
float linearDepth(float z){return uNear*uFar/(uFar-z*(uFar-uNear));}
void main(){
 vec3 V=normalize(cameraPosition-vWorld),N=normalize(vNormalW);if(dot(N,V)<0.)N=-N;
 vec2 uv=gl_FragCoord.xy/uResolution;float front=-vView.z;
 float back=texture2D(tBack,uv).r;if(back<front)back=front+.035;
 float opaque=linearDepth(texture2D(tDepth,uv).r);
 float path=max(.012,min(back,opaque)-front)*length(vView)/max(.01,front);
 path=clamp(path,.012,5.5);
 vec3 transmissionRay=refract(-V,N,1./1.333);
 vec4 endClip=uViewProjection*vec4(vWorld+transmissionRay*path,1.);
 vec2 refractUV=endClip.xy/max(.001,endClip.w)*.5+.5;
 refractUV=clamp(refractUV,vec2(.002),vec2(.998));
 // Revert samples that would pull foreground opaque objects through the fluid.
 float sampleDepth=linearDepth(texture2D(tDepth,refractUV).r);
 if(sampleDepth<front-.04)refractUV=uv;
 vec3 background=texture2D(tScene,refractUV).rgb;
 vec3 trans=exp(-uAbsorption*path);
 vec3 body=background*trans+vec3(.035,.16,.19)*(1.-trans)*.42;
 float ndv=clamp(dot(N,V),0.,1.);float f0=pow((1.333-1.)/(1.333+1.),2.);
 float F=f0+(1.-f0)*pow(1.-ndv,5.);
 vec3 reflection=environment(reflect(-V,N));
 vec3 col=mix(body,reflection,F);col=mix(col,vec3(.70,.79,.81),pow(clamp(vFoam,0.,.95),1.7)*.32);
 // The normal is geometric, never displaced by animated sine/noise waves.
 gl_FragColor=vec4(col,1.);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`;
const DEPTH_FRAGMENT=`varying vec3 vView;void main(){gl_FragColor=vec4(-vView.z,0.,0.,1.);}`;
const POINT_VERTEX=`attribute float radius;attribute float phase;attribute float opacity;uniform float uScale;varying float vPhase,vOpacity;varying vec3 vColor;
void main(){vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(radius*uScale/max(.08,-p.z),1.2,20.);vPhase=phase;vOpacity=opacity;vColor=color;}`;
const POINT_FRAGMENT=`varying float vPhase,vOpacity;varying vec3 vColor;uniform float uDiagnostic;void main(){vec2 q=gl_PointCoord*2.-1.;float r=dot(q,q);if(r>1.)discard;float edge=smoothstep(1.,.5,r);float light=.45+.55*sqrt(max(0.,1.-r));vec3 col=mix(vec3(.76,.91,.92),vColor,uDiagnostic)*light;
 float alpha=vOpacity*edge*(vPhase>1.5&&vPhase<2.5?.20:.85);if(vPhase>2.5){vec3 N=vec3(q.x,-q.y,sqrt(max(0.,1.-r)));float glint=pow(max(0.,dot(N,normalize(vec3(-.5,.8,.8)))),42.);col=vec3(.10,.22,.25)+vec3(.15,.29,.33)*N.z+vec3(1.2)*glint;}gl_FragColor=vec4(col,alpha);
 #include <tonemapping_fragment>
 #include <colorspace_fragment>
}`;
function makePoints(diagnostic=false){
 const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(new Float32Array(0),3));
 const m=new T.ShaderMaterial({vertexShader:POINT_VERTEX,fragmentShader:POINT_FRAGMENT,uniforms:{uScale:{value:1000},uDiagnostic:{value:diagnostic?1:0}},vertexColors:true,transparent:true,depthWrite:false,depthTest:true,blending:T.NormalBlending});
 const obj=new T.Points(g,m);obj.frustumCulled=false;return obj;
}
function setPoints(object,p,radii,phases,opacities,colors){
 const g=object.geometry;
 g.setAttribute('position',new T.Float32BufferAttribute(p,3));g.setAttribute('radius',new T.Float32BufferAttribute(radii,1));
 g.setAttribute('phase',new T.Float32BufferAttribute(phases,1));g.setAttribute('opacity',new T.Float32BufferAttribute(opacities,1));g.setAttribute('color',new T.Float32BufferAttribute(colors,3));g.setDrawRange(0,p.length/3);
}
function tileTexture(){
 const c=document.createElement('canvas');c.width=c.height=512;const x=c.getContext('2d');x.fillStyle='#455660';x.fillRect(0,0,512,512);
 x.fillStyle='#405059';x.fillRect(1,1,254,254);x.fillRect(257,257,254,254);
 x.strokeStyle='#344650';x.lineWidth=1;for(let i=0;i<512;i+=128){x.beginPath();x.moveTo(i,0);x.lineTo(i,512);x.moveTo(0,i);x.lineTo(512,i);x.stroke();}
 const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.wrapS=t.wrapT=T.RepeatWrapping;t.repeat.set(2.4,1.6);t.anisotropy=4;return t;
}
class LiquidRenderer{
 constructor(canvas){
  this.renderer=new T.WebGLRenderer({canvas,antialias:true,alpha:false,preserveDrawingBuffer:true,powerPreference:'high-performance'});
  this.renderer.setPixelRatio(1);this.renderer.outputColorSpace=T.SRGBColorSpace;this.renderer.toneMapping=T.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1.18;
  this.renderer.setClearColor(0x0b1017,1);this.renderer.shadowMap.enabled=true;this.renderer.shadowMap.type=T.PCFSoftShadowMap;
  this.scene=new T.Scene();this.scene.background=new T.Color(0x0b1017);this.scene.fog=new T.Fog(0x0b1017,12,26);
  this.camera=new T.PerspectiveCamera(38,16/9,.04,50);this.camera.position.set(7.4,4.9,7.7);this.target=new T.Vector3(2.4,.9,1.6);
  this.scene.add(new T.HemisphereLight(0xdaecff,0x52636b,2.2));
  const key=new T.DirectionalLight(0xe8f6ff,3.3);key.position.set(-1,7,4);key.castShadow=true;key.shadow.mapSize.set(1024,1024);key.shadow.camera.left=-6;key.shadow.camera.right=6;key.shadow.camera.top=6;key.shadow.camera.bottom=-6;key.shadow.bias=-.001;key.shadow.normalBias=.02;this.scene.add(key);
  const rim=new T.DirectionalLight(0xffc48a,1.25);rim.position.set(-5,2,-3);this.scene.add(rim);
  this.objects=new T.Group();this.scene.add(this.objects);
  const bg=new T.Mesh(new T.PlaneGeometry(100,100),new T.MeshStandardMaterial({color:0x172029,roughness:.8}));bg.rotation.x=-Math.PI/2;bg.position.y=-.21;bg.receiveShadow=true;this.scene.add(bg);
  this.sceneRT=new T.WebGLRenderTarget(1,1,{type:T.HalfFloatType,depthBuffer:true});this.sceneRT.depthTexture=new T.DepthTexture(1,1,T.UnsignedIntType);
  this.backRT=new T.WebGLRenderTarget(1,1,{type:T.HalfFloatType,depthBuffer:true,minFilter:T.NearestFilter,magFilter:T.NearestFilter});
  this.waterScene=new T.Scene();this.backScene=new T.Scene();
  this.geometry=new T.BufferGeometry();this.geometry.setAttribute('position',new T.Float32BufferAttribute([],3));
  this.material=new T.ShaderMaterial({vertexShader:WATER_VERTEX,fragmentShader:WATER_FRAGMENT,uniforms:{tScene:{value:this.sceneRT.texture},tBack:{value:this.backRT.texture},tDepth:{value:this.sceneRT.depthTexture},uResolution:{value:new T.Vector2(1,1)},uNear:{value:.04},uFar:{value:50},uViewProjection:{value:new T.Matrix4()},uAbsorption:{value:new T.Vector3(.40,.09,.035)}},side:T.FrontSide});
  this.water=new T.Mesh(this.geometry,this.material);this.water.frustumCulled=false;this.waterScene.add(this.water);
  this.back=new T.Mesh(this.geometry,new T.ShaderMaterial({vertexShader:WATER_VERTEX,fragmentShader:DEPTH_FRAGMENT,side:T.BackSide}));this.back.frustumCulled=false;this.backScene.add(this.back);
  this.normalMaterial=new T.MeshNormalMaterial({side:T.DoubleSide});this.wireMaterial=new T.MeshBasicMaterial({color:0x6de5d3,wireframe:true});
  this.white=makePoints();this.particlePoints=makePoints(true);this.whiteScene=new T.Scene();this.whiteScene.add(this.white,this.particlePoints);this.particlePoints.visible=false;
  this.mode='water';this.shot=0;this.frame=0;this.name='breach';this.orbit=null;this.drag=null;this.setupOrbit(canvas);
  this.resize(window.innerWidth,window.innerHeight);
 }
 disposeGroup(){this.objects.traverse(o=>{o.geometry?.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();}});this.objects.clear();}
 box(size,position,color,metal=.0,rough=.45){const o=new T.Mesh(new T.BoxGeometry(...size),new T.MeshStandardMaterial({color,metalness:metal,roughness:rough}));o.position.set(...position);o.castShadow=true;o.receiveShadow=true;this.objects.add(o);return o;}
 setup(config){
  this.config=config;this.name=config.nameKey;this.disposeGroup();const ex=config.extent;
  this.box([ex[0]+.3,.23,ex[2]+.3],[ex[0]/2,-.035,ex[2]/2],0x26323b,.5,.3);
  const floor=this.box([ex[0]-.16,.035,ex[2]-.16],[ex[0]/2,.074,ex[2]/2],0xffffff,.05,.31);floor.material.map=tileTexture();
  for(const z of [.01,ex[2]-.01])this.box([ex[0]+.18,.09,.085],[ex[0]/2,.104,z],0x495b63,.6,.25);
  for(const x of [.01,ex[0]-.01])this.box([.085,.09,ex[2]],[x,.104,ex[2]/2],0x495b63,.6,.25);
  // Deliberate cutaway: the physical tank walls are drawn as thin boundary rails.
  const lines=[];for(const z of [.075,ex[2]-.075]){lines.push(.075,.12,z,.075,2.9,z,ex[0]-.075,.12,z,ex[0]-.075,2.9,z);}
  lines.push(.075,2.9,.075,ex[0]-.075,2.9,.075,.075,2.9,.075,.075,2.9,ex[2]-.075);
  const lg=new T.BufferGeometry();lg.setAttribute('position',new T.Float32BufferAttribute(lines,3));const lo=new T.LineSegments(lg,new T.LineBasicMaterial({color:0x6c8394,transparent:true,opacity:.18}));this.objects.add(lo);
  for(let i=0;i<25;i++){const x=.12+i*(ex[0]-.24)/24;this.box([.012,.006,i%5===0?.11:.04],[x,.154,ex[2]+.015],0xbed6d8,0,.4);}
  for(const o of config.obstacles){
    if(o.kind==='box'){this.box(o.half.map(v=>v*2),o.center,0x47565d,.25,.24);
      this.box([o.half[0]*2+.004,.009,o.half[2]*2+.004],[o.center[0],o.center[1]+o.half[1]+.005,o.center[2]],0x7b8e95,.45,.21);
    }
  }
  if(this.name==='jets')for(const x of [.21,ex[0]-.21]){
    const pipe=new T.Mesh(new T.CylinderGeometry(.27,.27,.33,48,1,true),new T.MeshStandardMaterial({color:0x697c86,metalness:.8,roughness:.23,side:T.DoubleSide}));pipe.rotation.z=Math.PI/2;pipe.position.set(x,1.35,1.6);this.objects.add(pipe);
    const ring=new T.Mesh(new T.TorusGeometry(.254,.036,12,48),new T.MeshStandardMaterial({color:0xa0aeb4,metalness:.9,roughness:.16}));ring.rotation.y=Math.PI/2;ring.position.set(x<2?x+.165:x-.165,1.35,1.6);this.objects.add(ring);
    this.box([.18,1.2,.20],[x,.68,1.6],0x283944,.5,.3);
  }
 }
 resize(w,h){this.width=w;this.height=h;this.renderer.setSize(w,h,false);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();this.sceneRT.setSize(w,h);this.backRT.setSize(w,h);this.material.uniforms.uResolution.value.set(w,h);this.white.material.uniforms.uScale.value=h/Math.tan(this.camera.fov*Math.PI/360);this.particlePoints.material.uniforms.uScale.value=this.white.material.uniforms.uScale.value;}
 setFrame(data){
  const old=this.geometry;this.geometry=new T.BufferGeometry();this.geometry.setAttribute('position',new T.Float32BufferAttribute(data.positions,3));this.geometry.setAttribute('normal',new T.Float32BufferAttribute(data.normals,3));this.geometry.setAttribute('foam',new T.Float32BufferAttribute(data.foam??new Float32Array(data.positions.length/3),1));this.geometry.setIndex(new T.BufferAttribute(data.indices,1));
  this.water.geometry=this.back.geometry=this.geometry;old.dispose();
  const ww=data.white??new Float32Array(0),drops=data.drops??new Float32Array(0),n=ww.length/6+Math.floor(drops.length/3);
  const p=new Float32Array(n*3),r=new Float32Array(n),ph=new Float32Array(n),a=new Float32Array(n),col=new Float32Array(n*3);let m=0;
  for(let q=0;q<ww.length;q+=6,m++){p.set(ww.subarray(q,q+3),m*3);r[m]=ww[q+3]*1.0;ph[m]=ww[q+4];a[m]=ww[q+5]*.45;col.set([.75,.90,.93],m*3);}
  for(let q=0;q<drops.length;q+=3,m++){p.set(drops.subarray(q,q+3),m*3);r[m]=this.config.h*.17;ph[m]=3;a[m]=.8;col.set([.45,.7,.75],m*3);}
  setPoints(this.white,p,r,ph,a,col);
  const dg=data.diagnostic??new Float32Array(0),dn=dg.length/3,dr=new Float32Array(dn).fill(this.config.h*.19),da=new Float32Array(dn).fill(.92),dph=new Float32Array(dn),dc=new Float32Array(dn*3);
  for(let k=0;k<dn;k++){const t=Math.min(1,dg[k*3+1]/2.5);dc.set([.16+.3*t,.48+.45*t,.65+.3*t],k*3);}setPoints(this.particlePoints,dg,dr,dph,da,dc);
  this.latest=data;
 }
 setMode(mode){this.mode=mode;this.particlePoints.visible=mode==='particles';this.white.visible=mode==='water';this.water.visible=mode!=='particles';this.water.material=mode==='normal'?this.normalMaterial:mode==='wire'?this.wireMaterial:this.material;}
 setShot(shot){this.shot=shot;this.orbit=null;}
 updateCamera(progress=0){
  const target=this.target;
  if(this.orbit){const o=this.orbit;target.set(2.4,.85,1.6);this.camera.position.set(target.x+o.r*Math.cos(o.el)*Math.sin(o.az),target.y+o.r*Math.sin(o.el),target.z+o.r*Math.cos(o.el)*Math.cos(o.az));this.camera.lookAt(target);return;}
  const name=this.name;let pos,aim,fov=38;
  if(this.shot===0){pos=[7.5-.35*progress,4.65+.12*progress,7.6+.18*progress];aim=[2.35,.86,1.6];fov=38;}
  else if(this.shot===1){pos=[6.5+.13*progress,3.15+.1*progress,7.0-.25*progress];aim=[2.45,1.02,1.6];fov=40;}
  else if(this.shot===2){pos=[2.45+.15*progress,7.9,3.6];aim=[2.4,.6,1.6];fov=39;}
  else {pos=[6.7,4.7,7.0];aim=[2.4,.85,1.6];fov=39;}
  if(name==='impact'&&this.shot===1){pos=[5.35,2.5,5.75];aim=[2.4,.85,1.6];fov=40;}
  if(name==='jets'&&this.shot===1){pos=[2.6,2.75,8.0];aim=[2.4,.9,1.6];fov=42;}
  if(name==='cascade'&&this.shot===1){pos=[6.5,3.5,5.9];aim=[2.15,1.1,1.6];fov=41;}
  this.camera.position.set(...pos);this.target.set(...aim);this.camera.fov=fov;this.camera.updateProjectionMatrix();this.camera.lookAt(this.target);
 }
 draw(progress=0){
  this.updateCamera(progress);this.camera.updateMatrixWorld();this.material.uniforms.uViewProjection.value.multiplyMatrices(this.camera.projectionMatrix,this.camera.matrixWorldInverse);
  const r=this.renderer;r.autoClear=true;
  r.setRenderTarget(this.sceneRT);r.render(this.scene,this.camera);
  r.setRenderTarget(this.backRT);r.setClearColor(0,1);r.clear();r.render(this.backScene,this.camera);
  r.setRenderTarget(null);r.setClearColor(0x0b1017,1);r.render(this.scene,this.camera);
  r.autoClear=false;r.render(this.waterScene,this.camera);r.render(this.whiteScene,this.camera);r.autoClear=true;
 }
 setupOrbit(canvas){
  canvas.addEventListener('pointerdown',e=>{this.drag=[e.clientX,e.clientY];if(!this.orbit){const d=this.camera.position.clone().sub(this.target);this.orbit={r:d.length(),az:Math.atan2(d.x,d.z),el:Math.asin(d.y/d.length())};}canvas.setPointerCapture(e.pointerId);});
  canvas.addEventListener('pointermove',e=>{if(!this.drag)return;this.orbit.az-=(e.clientX-this.drag[0])*.005;this.orbit.el=Math.max(.03,Math.min(1.53,this.orbit.el+(e.clientY-this.drag[1])*.005));this.drag=[e.clientX,e.clientY];this.draw();});
  canvas.addEventListener('pointerup',()=>this.drag=null);
  canvas.addEventListener('wheel',e=>{e.preventDefault();if(!this.orbit){const d=this.camera.position.clone().sub(this.target);this.orbit={r:d.length(),az:Math.atan2(d.x,d.z),el:Math.asin(d.y/d.length())};}this.orbit.r=Math.max(2.5,Math.min(16,this.orbit.r*Math.exp(e.deltaY*.001)));this.draw();},{passive:false});
 }
 info(){const g=this.renderer.getContext(),ext=g.getExtension('WEBGL_debug_renderer_info');return {backend:`Three.js r${T.REVISION}`,renderer:ext?g.getParameter(ext.UNMASKED_RENDERER_WEBGL):g.getParameter(g.RENDERER),resolution:[this.width,this.height],vertices:this.geometry.attributes.position.count,triangles:(this.geometry.index?.count??0)/3,programs:this.renderer.info.programs.length,glError:g.getError(),mode:this.mode};}
}
window.LiquidRenderer=LiquidRenderer;
})();
