const params=new URLSearchParams(location.search),variant=['01','02','03','shared','material'].includes(params.get('variant'))?params.get('variant'):'01';
if(params.has('capture'))document.body.classList.add('capture');
let renderer,manifest,current=0,playing=false,busy=false;const errors=[];
async function unpack(f){
 const res=await fetch(`cache/${variant}/${String(f).padStart(4,'0')}.mesh.gz`);if(!res.ok)throw Error('Frame unavailable: '+f);
 const buf=await new Response(res.body.pipeThrough(new DecompressionStream('gzip'))).arrayBuffer(),dv=new DataView(buf),nv=dv.getUint32(4,true),nf=dv.getUint32(8,true),nd=dv.getUint32(12,true),nw=dv.getUint32(16,true),np=dv.getUint32(20,true),cw=dv.getUint32(24,true),ch=dv.getUint32(28,true),extent=manifest.config.extent;let off=32;
 function pos(n){const a=new Float32Array(n*3);for(let i=0;i<a.length;i++)a[i]=dv.getUint16(off+i*2,true)/65535*extent[i%3];off+=n*6;return a}
 const positions=pos(nv),normals=new Float32Array(nv*3);for(let i=0;i<normals.length;i++)normals[i]=dv.getInt16(off+i*2,true)/32767;off+=nv*6;
 const foam=new Float32Array(nv);for(let i=0;i<nv;i++)foam[i]=dv.getUint8(off+i)/255;off+=nv;
 const indices=new Uint32Array(nf*3);for(let i=0;i<indices.length;i++)indices[i]=dv.getUint32(off+i*4,true);off+=nf*12;
 const drops=pos(nd),dropRadii=new Float32Array(nd);for(let i=0;i<nd;i++)dropRadii[i]=dv.getFloat32(off+i*4,true);off+=nd*4;
 const white=new Float32Array(nw*6);for(let i=0;i<white.length;i++)white[i]=dv.getFloat32(off+i*4,true);off+=nw*24;const diagnostic=pos(np),caustic=new Uint8Array(buf.slice(off));
 return {positions,normals,indices,foam,drops,dropRadii,white,diagnostic,caustic,causticWidth:cw,causticHeight:ch};
}
async function loadFrame(f){f=Math.max(0,Math.min(manifest.frames.length-1,+f));renderer.setFrame(await unpack(f));current=f;renderer.setMetrics(manifest.frames[f]);renderer.draw(f/(manifest.frames.length-1));document.querySelector('#timeline').value=f;document.querySelector('#status').textContent=(f/(manifest.playbackFps||24)).toFixed(2)+' s';const info=renderer.info();if(info.glError)throw Error('WebGL '+info.glError);return info}
async function init(){manifest=await fetch(`cache/${variant}/manifest.json`).then(r=>r.json());renderer=new LiquidRenderer(document.querySelector('#view'));renderer.setup(manifest.config);renderer.setRasterProfile('repair');renderer.setMode('water');
 renderer.updateCamera=function(){this.camera.position.set(3.3,2.4,4.3);this.target.set(1.95,.72,.9);this.camera.fov=36;this.camera.updateProjectionMatrix();this.camera.lookAt(this.target)};
 if(variant==='shared'||variant==='material'){
 renderer.objects.visible=false;renderer.backgroundFloor.visible=false;renderer.scene.background=new THREE.Color(0x050708);renderer.scene.fog=null;
 const camera=new THREE.PerspectiveCamera(2*Math.atan(1.18125/5.1)*180/Math.PI,16/9,.05,100);renderer.camera=camera;renderer.material.uniforms.uNear.value=.05;renderer.material.uniforms.uFar.value=100;
 renderer.updateCamera=function(){this.camera.position.set(2.1,.76125,6);this.camera.lookAt(2.1,.76125,.9);this.camera.updateProjectionMatrix()};
 }
 if(variant==='material'){
 renderer.material.uniforms.uAbsorption.value.set(.32,.065,.018);
 let shader=renderer.material.fragmentShader;
 shader=shader.replace('vec2(.80,.20),.045','vec2(1.30,.55),.18').replace('vec2(.17,1.15),.05','vec2(.42,1.50),.18').replace('vec2(1.4,.16),.055','vec2(1.8,.38),.16');
 renderer.material.fragmentShader=shader;renderer.material.needsUpdate=true;
 }
 document.querySelector('#timeline').max=manifest.frames.length-1;window.WATER={loadFrame,renderer,manifest,ready:false};await loadFrame(+(params.get('frame')??(params.has('capture')?0:48)));WATER.ready=true;
 window.addEventListener('resize',()=>{renderer.resize(innerWidth,innerHeight);renderer.draw(current/(manifest.frames.length-1))});
 document.querySelector('#timeline').oninput=async e=>{playing=false;await loadFrame(+e.target.value)};document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'Pause':'Play'};
 let last=performance.now();async function tick(now){if(playing&&!busy&&now-last>1000/24){last=now;busy=true;try{await loadFrame((current+1)%manifest.frames.length)}catch(e){playing=false;document.querySelector('#status').textContent=e.message}busy=false}requestAnimationFrame(tick)}requestAnimationFrame(tick);
}init().catch(e=>{window.WATER_ERROR=e.message;document.querySelector('#status').textContent=e.message});
