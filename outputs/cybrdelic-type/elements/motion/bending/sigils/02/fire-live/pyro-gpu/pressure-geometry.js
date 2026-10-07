import {objectWGSL} from './objects.js?v=studio-rc-37-repair';
import {pressureShaders} from './shaders.js?v=studio-rc-37-repair';

export function triangleOpenFraction(a,b,c){
 const p=[a,b,c].filter(x=>x>0),n=[a,b,c].filter(x=>x<=0);
 if(p.length===3)return 1;if(p.length===0)return 0;
 if(p.length===1)return p[0]/(p[0]-n[0])*p[0]/(p[0]-n[1]);
 return 1-n[0]/(n[0]-p[0])*n[0]/(n[0]-p[1]);
}
export const apertureWGSL=`
fn triangleOpen(a:f32,b:f32,c:f32)->f32{
 if(a>0.&&b>0.&&c>0.){return 1.;}if(a<=0.&&b<=0.&&c<=0.){return 0.;}
 if(a>0.&&b<=0.&&c<=0.){return a/(a-b)*a/(a-c);}
 if(b>0.&&a<=0.&&c<=0.){return b/(b-a)*b/(b-c);}
 if(c>0.&&a<=0.&&b<=0.){return c/(c-a)*c/(c-b);}
 if(a<=0.){return 1.-a/(a-b)*a/(a-c);}
 if(b<=0.){return 1.-b/(b-a)*b/(b-c);}return 1.-c/(c-a)*c/(c-b);
}
`;
export function pressureStencilWGSL(n,binding=62){return `
@group(0) @binding(${binding}) var faceApertures:texture_3d<f32>;
fn aperture(i:vec3i)->vec3f{return textureLoad(faceApertures,clamp(i,vec3i(0),vec3i(${n})),0).xyz;}
struct PressureStencil{minus:vec3f,plus:vec3f};
fn pressureStencil(i:vec3i)->PressureStencil{
 return PressureStencil(aperture(i),vec3f(aperture(i+vec3i(1,0,0)).x,aperture(i+vec3i(0,1,0)).y,aperture(i+vec3i(0,0,1)).z));
}
fn pressureDiagonal(i:vec3i)->f32{let s=pressureStencil(i);return dot(s.minus+s.plus,vec3f(1));}
`;}
const weightedSum=(sample,i='i',s='st')=>`${s}.plus.x*${sample}(${i}+vec3i(1,0,0))+${s}.minus.x*${sample}(${i}-vec3i(1,0,0))+${s}.plus.y*${sample}(${i}+vec3i(0,1,0))+${s}.minus.y*${sample}(${i}-vec3i(0,1,0))+${s}.plus.z*${sample}(${i}+vec3i(0,0,1))+${s}.minus.z*${sample}(${i}-vec3i(0,0,1))`;
export function geometryPressureShaders(n){
 const base=pressureShaders(n),result={};
 for(const [name,source] of Object.entries(base)){
  if(name==='prolong'){result[name]=source;continue;}
  let code=source+pressureStencilWGSL(n,4);
  code=code.replace('fn sum(i:vec3i)->f32{return ', 'fn sum(i:vec3i)->f32{let st=pressureStencil(i);return ');
  const oldSum='at(i+vec3i(1,0,0))+at(i-vec3i(1,0,0))+at(i+vec3i(0,1,0))+at(i-vec3i(0,1,0))+at(i+vec3i(0,0,1))+at(i-vec3i(0,0,1))';
  code=code.replace(oldSum,weightedSum('at'));
  const oldLocal='localAt(i+vec3i(1,0,0))+localAt(i-vec3i(1,0,0))+localAt(i+vec3i(0,1,0))+localAt(i-vec3i(0,1,0))+localAt(i+vec3i(0,0,1))+localAt(i-vec3i(0,0,1))';
  code=code.replace('let neighbors='+oldLocal,'let st=pressureStencil(i);let neighbors='+weightedSum('localAt'));
  const oldTile='tileAt(t+vec3i(1,0,0))+tileAt(t-vec3i(1,0,0))+tileAt(t+vec3i(0,1,0))+tileAt(t-vec3i(0,1,0))+tileAt(t+vec3i(0,0,1))+tileAt(t-vec3i(0,0,1))';
  code=code.replace('let neighbors='+oldTile,'let st=pressureStencil(i);let neighbors='+weightedSum('tileAt','t'));
  code=code.replaceAll('/6.,.6666667','/max(pressureDiagonal(i),.000001),.6666667').replaceAll('-6.*at(i)','-pressureDiagonal(i)*at(i)');
  if(name==='coarse')code=code.replace('next[lane]=mix(values[lane]', 'next[lane]=select(0.,mix(values[lane]').replace('max(pressureDiagonal(i),.000001),.6666667);workgroupBarrier();','max(pressureDiagonal(i),.000001),.6666667),pressureDiagonal(i)>.000001);workgroupBarrier();');
  result[name]=code;
 }
 return result;
}

export function geometryProjectionShaders(shaders,n){
 const weights=pressureStencilWGSL(n);
 let rhs=shaders.rhs+weights,project=shaders.project+weights;
 const raw='(loadV(v,i+vec3i(1,0,0)).x-q.x+loadV(v,i+vec3i(0,1,0)).y-q.y+loadV(v,i+vec3i(0,0,1)).z-q.z)/H';
 rhs=rhs.replace('let div='+raw,'let st=pressureStencil(i);let div=(st.plus.x*loadV(v,i+vec3i(1,0,0)).x-st.minus.x*q.x+st.plus.y*loadV(v,i+vec3i(0,1,0)).y-st.minus.y*q.y+st.plus.z*loadV(v,i+vec3i(0,0,1)).z-st.minus.z*q.z)/H');
 project=project.replace('if(id.y==0u){out.y=0.;}textureStore', 'out=select(vec3f(0),out,aperture(i)>vec3f(.000001));\n if(id.y==0u){out.y=0.;}textureStore');
 // A fully closed cell is outside the pressure graph. A nonzero RHS there
 // has no solution; restricting it creates a spurious global pressure pulse.
 rhs=rhs.replace('textureStore(b,i,vec4f((q.w-div)*H*H));',
  'textureStore(b,i,vec4f(select(0.,(q.w-div)*H*H,pressureDiagonal(i)>.000001)));');
 project=project.replace('vec4f(out,q.w)','vec4f(out,select(0.,q.w,pressureDiagonal(i)>.000001))');
 return {rhs,project};
}

export class GeometryPressure {
 static async create(solver){const p=new GeometryPressure(solver);await p.init();return p;}
 constructor(solver){this.solver=solver;this.resources=[];this.enabled=false;this.stamp='';}
 async init(){
  const s=this.solver,d=s.device;this.control=d.createBuffer({size:16,usage:GPUBufferUsage.UNIFORM|GPUBufferUsage.COPY_DST});this.resources.push(this.control);
  this.weights=s.levels.map(l=>{const t=d.createTexture({label:'fluid-face-apertures-'+l.n,size:[l.n+1,l.n+1,l.n+1],dimension:'3d',format:'rgba16float',usage:GPUTextureUsage.TEXTURE_BINDING|GPUTextureUsage.STORAGE_BINDING});this.resources.push(t);return {t,view:t.createView()};});
  const n=s.N;
  this.build=await s.pipeline(`@group(0) @binding(0) var<uniform> control:vec4u;@group(0) @binding(1) var smp:sampler;
${objectWGSL}
${apertureWGSL}
@group(0) @binding(62) var dst:texture_storage_3d<rgba16float,write>;
fn faceFraction(center:vec3f,a:vec3f,b:vec3f)->f32{
 let p=objectDistance(center-a-b);let q=objectDistance(center+a-b);let r=objectDistance(center+a+b);let t=objectDistance(center-a+b);
 return .5*(triangleOpen(p,q,r)+triangleOpen(p,r,t));
}
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u){
 if(any(id>vec3u(${n}u))||(control.x==0u&&!woodMoved())){return;}
 let h=6./${n}.;let x=vec3f(-3,0,-3)+vec3f(id)*h;
 let a=vec3f(h*.5,0,0);let b=vec3f(0,h*.5,0);let c=vec3f(0,0,h*.5);
 let fx=faceFraction(x+b+c,b,c);let fy=select(faceFraction(x+a+c,a,c),0.,id.y==0u);let fz=faceFraction(x+a+b,a,b);
 textureStore(dst,vec3i(id),vec4f(fx,fy,fz,1));
}`,'geometry-face-apertures');
  this.down=[];
  for(let l=1;l<s.levels.length;l++){
   const size=s.levels[l].n;
   this.down[l]=await s.pipeline(`@group(0) @binding(0) var<uniform> control:vec4u;@group(0) @binding(43) var<storage,read> broken:array<u32>;
@group(0) @binding(2) var fine:texture_3d<f32>;@group(0) @binding(3) var dst:texture_storage_3d<rgba16float,write>;
@compute @workgroup_size(4,4,4) fn main(@builtin(global_invocation_id) id:vec3u){
 if(any(id>vec3u(${size}u))||(control.x==0u&&broken[0]==0u)){return;}let i=vec3i(id)*2;var w=vec3f(0);
 for(var a=0;a<2;a++){for(var b=0;b<2;b++){
  w.x+=textureLoad(fine,clamp(i+vec3i(0,a,b),vec3i(0),vec3i(${size*2})),0).x;
  w.y+=textureLoad(fine,clamp(i+vec3i(a,0,b),vec3i(0),vec3i(${size*2})),0).y;
  w.z+=textureLoad(fine,clamp(i+vec3i(a,b,0),vec3i(0),vec3i(${size*2})),0).z;
 }}textureStore(dst,vec3i(id),vec4f(w*.25,1));
}`,'geometry-restrict-apertures-'+size);
  }
  this.kernels=[];
  for(const level of s.levels){const family={};for(const [name,code] of Object.entries(geometryPressureShaders(level.n)))family[name]=await s.pipeline(code,'pressure-geometry-'+name+'-'+level.n);this.kernels.push(family);}
  const code=geometryProjectionShaders(s.simulationShaderSet(null,false),s.N);
  this.rhs=await s.pipeline(code.rhs,'geometry-pressure-rhs');this.project=await s.pipeline(code.project,'geometry-pressure-project');
  this.measure=await s.makeGeometryMeasure();
 }
 encode(encoder){
  const s=this.solver,stamp=[s.objectId,...s.source,s.effect[1]].join(':');const force=stamp!==this.stamp;this.stamp=stamp;
  s.device.queue.writeBuffer(this.control,0,new Uint32Array([force?1:0,0,0,0]));
  s.dispatch(encoder,this.build,[[0,{buffer:this.control}],[1,s.sampler],...s.objectBindings(),[62,this.weights[0]]],s.N+1);
  const broken=s.objectBindings().find(([slot])=>slot===43);
  for(let l=1;l<s.levels.length;l++)s.dispatch(encoder,this.down[l],[[0,{buffer:this.control}],broken,[2,this.weights[l-1]],[3,this.weights[l]]],s.levels[l].n+1);
 }
 destroy(){for(const r of this.resources)r.destroy();}
}
