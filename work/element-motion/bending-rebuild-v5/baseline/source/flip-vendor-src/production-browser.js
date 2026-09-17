(()=>{
const __module_0=(()=>{
/** Typed, serializable scene dependency graph. SI units; no executable JSON. */
const clone=x=>JSON.parse(JSON.stringify(x));
const canonical=x=>Array.isArray(x)?'['+x.map(canonical).join(',')+']':x&&typeof x==='object'?'{'+Object.keys(x).sort().map(k=>JSON.stringify(k)+':'+canonical(x[k])).join(',')+'}':JSON.stringify(x);
// Cache routing digest, NOT a cryptographic signature. Canonical input is stored
// alongside the key and MUST also match before any persisted cache is reused.
function cacheDigest(value){const text=canonical(value);let h=14695981039346656037n;for(const b of new TextEncoder().encode(text)){h^=BigInt(b);h=BigInt.asUintN(64,h*1099511628211n);}return h.toString(16).padStart(16,'0');}
const NODE_TYPES={
 source:{inputs:[],output:'configuration'},physics:{inputs:['configuration'],output:'simulation'},
 surface:{inputs:['simulation'],output:'surface'},material:{inputs:[],output:'material'},
 camera:{inputs:[],output:'camera'},lighting:{inputs:[],output:'lighting'},
 render:{inputs:['surface','material','camera','lighting'],output:'frames'},export:{inputs:['surface'],output:'asset'}
};
function finite(x,name,min=-Infinity,max=Infinity){if(!Number.isFinite(x)||x<min||x>max)throw Error(`Invalid ${name}: ${x}`);}
function vector(x,name,n=3){if(!Array.isArray(x)||x.length!==n)throw Error('Invalid '+name);x.forEach(v=>finite(v,name));}
function validateParameters(node){const p=node.parameters??{};
 if(node.type==='source'){
  if(!p.config||typeof p.config.nameKey!=='string')throw Error('Source requires a serializable preset config.');
  finite(p.config.h,'grid spacing',1e-5,100);for(const k of ['nx','ny','nz']){finite(p.config[k],k,3,512);if(!Number.isInteger(p.config[k]))throw Error('Grid dimensions must be integral.');}
  vector(p.config.extent,'extent');if(!Number.isInteger(p.config.maxParticles)||p.config.maxParticles<1||p.config.maxParticles>2000000)throw Error('Particle capacity exceeds implemented bounds.');
 }
 if(node.type==='physics'){
  const permitted=['flip','surfaceTension','kinematicViscosity','pressureTolerance','affine','gravity','frames','frameDt'];
  if(Object.keys(p).some(k=>!permitted.includes(k)))throw Error('Unsupported physics parameter.');
  if(p.flip!==undefined)finite(p.flip,'FLIP fraction',0,1);if(p.surfaceTension!==undefined)finite(p.surfaceTension,'surface tension',0,2);
  if(p.kinematicViscosity!==undefined)finite(p.kinematicViscosity,'kinematic viscosity',0,1);if(p.pressureTolerance!==undefined)finite(p.pressureTolerance,'relative residual',1e-8,.01);
  if(p.gravity!==undefined)vector(p.gravity,'gravity');if(p.affine!==undefined&&typeof p.affine!=='boolean')throw Error('Affine must be boolean.');
  if(p.frames!==undefined){finite(p.frames,'frames',1,10000);if(!Number.isInteger(p.frames))throw Error('Frames must be integral.');}
  if(p.frameDt!==undefined)finite(p.frameDt,'frameDt',1e-5,.05);
 }
 if(node.type==='surface')for(const [key,min,max] of [['spacingFactor',.2,.9],['shapeHistoryWeight',0,.6],['temporalBlend',0,.6]])if(p[key]!==undefined)finite(p[key],key,min,max);
 if(node.type==='material'){finite(p.ior??1.333,'IOR',1,2.5);vector(p.absorption??[.2,.052,.019],'absorption');for(const x of p.absorption??[])finite(x,'absorption',0,100);}
 if(node.type==='lighting')finite(p.exposure??1.04,'exposure',.01,10);
 if(node.type==='camera'){finite(p.shot??0,'camera shot',0,3);if(!Number.isInteger(p.shot??0))throw Error('Camera shot must be integral.');}
}
class SceneGraph{
 constructor(document){this.document=clone(document);this.validate();}
 validate(){const d=this.document;if(d.schema!=='cybr-scene-graph/1'||!Array.isArray(d.nodes)||d.nodes.length>128)throw Error('Unsupported scene graph.');
  this.byId=new Map();for(const node of d.nodes){if(!/^[a-zA-Z][\w-]{0,63}$/.test(node.id)||this.byId.has(node.id)||!NODE_TYPES[node.type])throw Error('Invalid or duplicate node.');this.byId.set(node.id,node);validateParameters(node);}
  for(const node of d.nodes){const spec=NODE_TYPES[node.type],inputs=node.inputs??[];if(inputs.length!==spec.inputs.length)throw Error(`Incorrect ports on ${node.id}`);
   inputs.forEach((id,i)=>{const upstream=this.byId.get(id);if(!upstream||NODE_TYPES[upstream.type].output!==spec.inputs[i])throw Error(`Incompatible connection ${id} → ${node.id}`);});}
  this.order=[];const done=new Set(),active=new Set();const visit=id=>{if(active.has(id))throw Error('Dependency cycle.');if(done.has(id))return;active.add(id);for(const upstream of this.byId.get(id).inputs??[])visit(upstream);active.delete(id);done.add(id);this.order.push(id);};for(const node of d.nodes)visit(node.id);
  if(!d.nodes.some(n=>n.type==='render'))throw Error('Scene needs a render output.');return this;
 }
 signature(id){const n=this.byId.get(id);if(!n)throw Error('Unknown node.');return {type:n.type,parameters:n.parameters??{},upstream:(n.inputs??[]).map(x=>this.signature(x))};}
 keys(){return Object.fromEntries(this.order.map(id=>[id,cacheDigest(this.signature(id))]));}
 patch(id,parameters){const before=this.keys(),doc=clone(this.document),n=doc.nodes.find(n=>n.id===id);if(!n)throw Error('Unknown node.');n.parameters={...n.parameters,...clone(parameters)};const next=new SceneGraph(doc),after=next.keys();this.document=doc;this.validate();return {invalidated:this.order.filter(id=>before[id]!==after[id]),before,after};}
 compile(){const find=t=>this.document.nodes.find(n=>n.type===t),source=find('source'),physics=find('physics');if(!source||!physics)throw Error('A runnable scene requires source and physics nodes.');
  const config=clone(source.parameters.config),p=clone(physics.parameters??{}),frames=p.frames??96,frameDt=p.frameDt??1/48;delete p.frames;delete p.frameDt;Object.assign(config,p);
  config.surfaceOptions=clone(find('surface')?.parameters??{});
  return {config,frames,frameDt,material:clone(find('material')?.parameters??{}),camera:clone(find('camera')?.parameters??{}),lighting:clone(find('lighting')?.parameters??{}),cacheKeys:this.keys(),canonicalInputs:Object.fromEntries(this.order.map(id=>[id,canonical(this.signature(id))]))};
 }
 toJSON(){return clone(this.document);}
}
function createSceneGraph(config){return new SceneGraph({schema:'cybr-scene-graph/1',units:{length:'m',time:'s',mass:'kg',surfaceTension:'N/m',kinematicViscosity:'m²/s'},nodes:[
 {id:'source',type:'source',parameters:{config:clone(config)}},
 {id:'physics',type:'physics',inputs:['source'],parameters:{flip:config.flip,surfaceTension:config.surfaceTension??.072,kinematicViscosity:config.kinematicViscosity??0,pressureTolerance:config.pressureTolerance??1e-5,frames:96,frameDt:1/48}},
 {id:'surface',type:'surface',inputs:['physics'],parameters:{spacingFactor:.43,shapeHistoryWeight:.28,temporalBlend:.30}},
 {id:'material',type:'material',parameters:{ior:1.333,absorption:[.20,.052,.019]}},
 {id:'camera',type:'camera',parameters:{shot:0}}, {id:'lighting',type:'lighting',parameters:{exposure:1.04}},
 {id:'render',type:'render',inputs:['surface','material','camera','lighting'],parameters:{width:1920,height:1080,fps:24}},
 {id:'export',type:'export',inputs:['surface'],parameters:{format:'usda',timeBasis:'physical'}}]});}
function planMemory(config,{width=1920,height=1080,particleCapacity=config.maxParticles??800000,activeBricks=null,surfaceTriangles=500000,budgetBytes=2**30}={}){
 for(const [k,v] of Object.entries({width,height,particleCapacity,surfaceTriangles,budgetBytes}))finite(v,k,1,2**40);
 const grid=(config.nx+1)*(config.ny+1)*(config.nz+1),blocks=activeBricks??Math.ceil((config.nx+1)/8)*Math.ceil((config.ny+1)/8)*Math.ceil((config.nz+1)/8),atlas=blocks*512;
 const parts={cpuParticleArrays:particleCapacity*(3+3+9+6+1)*4,cpuDenseGridArrays:grid*138,multigridPeakAllowance:grid*224,gpuParticlePingPong:particleCapacity*5*4*4*2,gpuGridAndScratch:atlas*36*16,renderTargets:width*height*40,bvhAndSurface:surfaceTriangles*220};
 const subtotal=Object.values(parts).reduce((a,b)=>a+b,0),reserve=Math.ceil(subtotal*.25),total=subtotal+reserve;
 return {parts,reserveBytes:reserve,totalEstimatedBytes:total,budgetBytes,fits:total<=budgetBytes,headroomBytes:budgetBytes-total,estimateNotMeasurement:true,includesBothBackends:true,note:'Conservative planning envelope; driver allocations, browser overhead and allocator fragmentation are not measured.'};
}

return {cacheDigest,NODE_TYPES,SceneGraph,createSceneGraph,planMemory};
})();
globalThis.CYBR_PIPELINE=__module_0;})();