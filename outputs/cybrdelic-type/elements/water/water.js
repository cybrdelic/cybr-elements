const params=new URLSearchParams(location.search),variant=params.get('variant')==='02'?'02':'01';
if(params.has('capture'))document.body.classList.add('capture');document.querySelector('#sigil').src=`sigil-${variant}.png`;
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
async function loadFrame(f){f=Math.max(0,Math.min(manifest.frames.length-1,+f));renderer.setFrame(await unpack(f));current=f;renderer.setMetrics(manifest.frames[f]);renderer.draw(f/(manifest.frames.length-1));document.querySelector('#timeline').value=f;document.querySelector('#status').textContent=(f/24).toFixed(2)+' s';const info=renderer.info();if(info.glError)throw Error('WebGL '+info.glError);return info}
async function init(){manifest=await fetch(`cache/${variant}/manifest.json`).then(r=>r.json());renderer=new LiquidRenderer(document.querySelector('#view'));renderer.setup(manifest.config);renderer.setRasterProfile('repair');renderer.setMode('water');
 const backdropCanvas=document.createElement('canvas');backdropCanvas.width=512;backdropCanvas.height=512;const bg=backdropCanvas.getContext('2d'),g=bg.createLinearGradient(0,0,512,512);g.addColorStop(0,'#293c48');g.addColorStop(.48,'#82979e');g.addColorStop(1,'#304654');bg.fillStyle=g;bg.fillRect(0,0,512,512);const map=new THREE.CanvasTexture(backdropCanvas);map.colorSpace=THREE.SRGBColorSpace;const wall=new THREE.Mesh(new THREE.PlaneGeometry(12,7),new THREE.MeshBasicMaterial({map}));wall.position.set(2.8,2,.12);renderer.scene.add(wall);
 renderer.updateCamera=function(progress=0){const u=Math.max(0,Math.min(1,(current-94)/64)),ease=u*u*(3-2*u);this.camera.position.set(2.8+.08*ease,3.15+.85*ease,4.65+1.65*ease);this.target.set(2.8,2.15-1.60*ease,.90);this.camera.fov=38;this.camera.updateProjectionMatrix();const fit=Math.max(1,(16/9)/this.camera.aspect);this.camera.position.sub(this.target).multiplyScalar(fit).add(this.target);this.camera.lookAt(this.target)};
 document.querySelector('#timeline').max=manifest.frames.length-1;window.WATER={loadFrame,renderer,manifest,ready:false};await loadFrame(+(params.get('frame')??(params.has('capture')?0:48)));WATER.ready=true;
 window.addEventListener('resize',()=>{renderer.resize(innerWidth,innerHeight);renderer.draw(current/(manifest.frames.length-1))});
 document.querySelector('#timeline').oninput=async e=>{playing=false;await loadFrame(+e.target.value)};document.querySelector('#play').onclick=()=>{playing=!playing;document.querySelector('#play').textContent=playing?'Pause':'Play'};
 let last=performance.now();async function tick(now){if(playing&&!busy&&now-last>1000/24){last=now;busy=true;try{await loadFrame((current+1)%manifest.frames.length)}catch(e){playing=false;document.querySelector('#status').textContent=e.message}busy=false}requestAnimationFrame(tick)}requestAnimationFrame(tick);
}init().catch(e=>{window.WATER_ERROR=e.message;document.querySelector('#status').textContent=e.message});
